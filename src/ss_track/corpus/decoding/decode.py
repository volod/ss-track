"""The one full-decode inspection of a source, under the canonical decode policy.

Default FFmpeg behavior is unsafe for evidence: it conceals damaged macroblocks, returns a short
read as a clean end of file, and invents timestamps a file never stored. The policy in
`corpus.decoding.decode_policy` turns those into visible failures, and `inspect_media` treats every remaining
signal as one.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import av
import av.container
import av.logging
import av.video
from av.video.codeccontext import VideoCodecContext

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.decoding import deadline
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from ss_track.corpus.decoding.integrity import completeness_checks, damaged
from ss_track.corpus.decoding.pixels import ColorTags, bits_per_component, color_tags
from ss_track.corpus.decoding.streams import open_media, select_video_stream

type FfmpegLog = list[tuple[int, str, str]]
type FrameConsumer = Callable[[int, av.VideoFrame], None]


@dataclass(frozen=True, slots=True)
class MediaInspection:
    """What a complete strict decode established about a source."""

    container: str
    codec: str
    original_width: int
    original_height: int
    decoded_width: int
    decoded_height: int
    source_pixel_format: str
    source_bits_per_component: int
    color: ColorTags
    display_rotation_degrees: int
    interlaced_frames: int
    time_base: str | None
    pts: tuple[int | None, ...]
    discarded_frames: int
    video_stream_count: int
    video_stream_index: int
    completeness_checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _FrameShape:
    width: int
    height: int
    pixel_format: str
    rotation: int
    color: ColorTags

    def __str__(self) -> str:
        layout = f"{self.width}x{self.height} {self.pixel_format} rotated {self.rotation}"
        return f"{layout} color {self.color}"


@dataclass(slots=True)
class _Decoded:
    """Running account of one decode, in presentation order."""

    pts: list[int | None] = field(default_factory=list)
    shape: _FrameShape | None = None
    discarded: int = 0
    interlaced: int = 0


@contextmanager
def _ffmpeg_errors() -> Iterator[FfmpegLog]:
    """Capture FFmpeg's error log, the only signal for some damage that still yields a frame."""
    level = av.logging.get_level()
    skip_repeated = av.logging.get_skip_repeated()
    # The repeat filter would drop a second identical error and defer its count to a later file.
    av.logging.set_skip_repeated(False)
    av.logging.set_level(av.logging.ERROR)
    try:
        with av.logging.Capture(local=True) as logs:
            yield logs
    finally:
        av.logging.set_level(level)
        av.logging.set_skip_repeated(skip_repeated)


def _ignore_frame(_: int, __: av.VideoFrame) -> None:
    """Inspection needs only the account of each frame, not its pixels."""


def inspect_media(
    path: Path,
    policy: DecodePolicy,
    on_frame: FrameConsumer = _ignore_frame,
    *,
    video_stream_index: int | None = None,
    clock: deadline.Clock | None = None,
    decode_limit_seconds: float = deadline.DECODE_LIMIT_SECONDS,
) -> MediaInspection:
    """Decode one video stream strictly, or refuse with the evidence of why that failed.

    `video_stream_index` counts video streams from zero. Omit it only when the container has one.
    `on_frame` receives each accepted frame with its zero-based index. A refusal can come after
    earlier frames were delivered, so a consumer must keep its output unpublished until this
    returns.
    The decode loop stops once `clock` runs past `decode_limit_seconds`. The default clock is
    monotonic time and the default limit is the declared bound.
    """
    chosen_clock = deadline.decode_clock if clock is None else clock
    with _ffmpeg_errors() as logs, open_media(path, policy.format_options) as container:
        return _inspect_container(
            path,
            container,
            policy,
            logs,
            on_frame,
            video_stream_index,
            chosen_clock,
            decode_limit_seconds,
        )


def _configured_context(stream: av.video.VideoStream, policy: DecodePolicy) -> VideoCodecContext:
    """Apply the policy to a stream, which has no context if its headers were lost."""
    context: VideoCodecContext | None = stream.codec_context
    if context is None:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "video stream has no decodable header")
    context.options = dict(policy.codec_options)
    context.thread_count = policy.thread_count
    return context


def _inspect_container(
    path: Path,
    container: av.container.InputContainer,
    policy: DecodePolicy,
    logs: FfmpegLog,
    on_frame: FrameConsumer,
    video_stream_index: int | None,
    clock: deadline.Clock,
    decode_limit_seconds: float,
) -> MediaInspection:
    streams = container.streams.video
    stream, selected = select_video_stream(streams, video_stream_index)
    context = _configured_context(stream, policy)
    decoded = _Decoded()
    try:
        _decode_all(container, stream, logs, decoded, on_frame, clock, decode_limit_seconds)
    except av.FFmpegError as error:
        raise damaged(_last_log(logs) or str(error.strerror), len(decoded.pts)) from error
    checks = completeness_checks(
        path, container.format.name, stream.frames, decoded.pts, decoded.discarded
    )
    shape = decoded.shape
    if shape is None:
        raise CorpusRefusal(RefusalCode.SOURCE_NO_FRAMES, "media decoded to no frames")
    return MediaInspection(
        container=container.format.name,
        codec=context.codec.name,
        original_width=context.width,
        original_height=context.height,
        decoded_width=shape.width,
        decoded_height=shape.height,
        source_pixel_format=shape.pixel_format,
        source_bits_per_component=bits_per_component(shape.pixel_format),
        color=shape.color,
        display_rotation_degrees=shape.rotation,
        interlaced_frames=decoded.interlaced,
        time_base=None if stream.time_base is None else str(stream.time_base),
        pts=tuple(decoded.pts),
        discarded_frames=decoded.discarded,
        video_stream_count=len(streams),
        video_stream_index=selected,
        completeness_checks=checks,
    )


def _decode_all(
    container: av.container.InputContainer,
    stream: av.video.VideoStream,
    logs: FfmpegLog,
    decoded: _Decoded,
    on_frame: FrameConsumer,
    clock: deadline.Clock,
    decode_limit_seconds: float,
) -> None:
    """Account for every packet, stopping at damage or the declared time limit."""
    bound = deadline.DecodeDeadline(decode_limit_seconds, clock)
    for packet in container.demux(stream):
        if packet.is_corrupt:
            raise damaged("demuxer flagged a corrupt packet", len(decoded.pts))
        bound.check(len(decoded.pts))
        decoded.discarded += packet.is_discard
        for frame in packet.decode():
            bound.check(len(decoded.pts))
            if frame.is_corrupt:
                raise damaged("decoder flagged a corrupt frame", len(decoded.pts))
            _require_one_shape(frame, decoded)
            decoded.interlaced += frame.interlaced_frame
            on_frame(len(decoded.pts), frame)
            decoded.pts.append(frame.pts)
            bound.check(len(decoded.pts))
        if logs:
            raise damaged(_last_log(logs), len(decoded.pts))
    bound.check(len(decoded.pts))
    if logs:
        raise damaged(_last_log(logs), len(decoded.pts))


def _require_one_shape(frame: av.VideoFrame, decoded: _Decoded) -> None:
    """Keep the single recorded format true of every frame, not only the first."""
    shape = _FrameShape(
        frame.width, frame.height, frame.format.name, frame.rotation, color_tags(frame)
    )
    if decoded.shape is None:
        decoded.shape = shape
    elif shape != decoded.shape:
        raise CorpusRefusal(
            RefusalCode.SOURCE_FORMAT_CHANGED,
            "frame format changes within the stream",
            {
                "frame_index": len(decoded.pts),
                "first": str(decoded.shape),
                "found": str(shape),
            },
        )


def _last_log(logs: FfmpegLog) -> str:
    return logs[-1][2].strip() if logs else ""
