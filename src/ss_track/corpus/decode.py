"""The canonical decoder and the one full-decode inspection of a source.

Default FFmpeg behavior is unsafe for evidence: it conceals damaged macroblocks, returns a short
read as a clean end of file, and invents timestamps a file never stored. The policy below turns
those into visible failures, and `inspect_media` treats every remaining signal as one.
"""

import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

import av
import av.container
import av.logging
import av.video
from av.video.codeccontext import VideoCodecContext

from ss_track.corpus.integrity import matroska_segment_end
from ss_track.corpus.pixels import (
    CONVERSION_FLAGS,
    OUTPUT_PIXEL_FORMAT,
    ColorTags,
    bits_per_component,
    color_tags,
)
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode

POLICY_REVISION = 3
_FORMAT_OPTIONS = {"fflags": "nofillin", "err_detect": "explode"}
_CODEC_OPTIONS = {"err_detect": "explode", "flags": "bitexact", "idct": "simple"}
_THREAD_COUNT = 1
_MATROSKA_FORMAT = "matroska"
FRAME_COUNT_CHECK = "frame_count"
SEGMENT_SIZE_CHECK = "matroska_segment_size"

type FfmpegLog = list[tuple[int, str, str]]
type FrameConsumer = Callable[[int, av.VideoFrame], None]


@dataclass(frozen=True, slots=True)
class DecodePolicy:
    """Everything that can change which frames, or which pixels, a source decodes to."""

    decoder: str
    decoder_version: str
    ffmpeg_version: str
    format_options: Mapping[str, str] = field(default_factory=lambda: dict(_FORMAT_OPTIONS))
    codec_options: Mapping[str, str] = field(default_factory=lambda: dict(_CODEC_OPTIONS))
    thread_count: int = _THREAD_COUNT
    output_pixel_format: str = OUTPUT_PIXEL_FORMAT
    conversion_flags: str = CONVERSION_FLAGS
    revision: int = POLICY_REVISION

    def as_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form stored in manifests."""
        record: dict[str, JsonValue] = asdict(self)
        return record


def current_decode_policy() -> DecodePolicy:
    """Return the policy of the installed, pinned decoder."""
    return DecodePolicy(
        decoder="pyav", decoder_version=av.__version__, ffmpeg_version=av.ffmpeg_version_info
    )


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


def _damaged(reason: str, frames_decoded: int) -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.SOURCE_DAMAGED,
        f"source is truncated or corrupt: {reason}",
        {"reason": reason, "frames_decoded": frames_decoded},
    )


def _ignore_frame(_: int, __: av.VideoFrame) -> None:
    """Inspection needs only the account of each frame, not its pixels."""


def inspect_media(
    path: Path, policy: DecodePolicy, on_frame: FrameConsumer = _ignore_frame
) -> MediaInspection:
    """Decode every frame strictly, or refuse with the evidence of why that failed.

    `on_frame` receives each accepted frame with its zero-based index, so anything built from the
    pixels passes the same checks. A refusal can come after earlier frames were delivered, so a
    consumer must keep its output unpublished until this returns.
    """
    with _ffmpeg_errors() as logs:
        try:
            container = av.open(os.fspath(path), options=dict(policy.format_options))
        except av.FFmpegError as error:
            raise CorpusRefusal(
                RefusalCode.SOURCE_UNREADABLE, f"cannot open media: {error.strerror}"
            ) from error
        with container:
            return _inspect_container(path, container, policy, logs, on_frame)


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
) -> MediaInspection:
    streams = container.streams.video
    if not streams:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "media has no video stream")
    stream = streams[0]
    context = _configured_context(stream, policy)
    decoded = _Decoded()
    try:
        _decode_all(container, stream, logs, decoded, on_frame)
    except av.FFmpegError as error:
        raise _damaged(_last_log(logs) or str(error.strerror), len(decoded.pts)) from error
    checks = _frame_count_checks(stream.frames, decoded)
    if _MATROSKA_FORMAT in container.format.name:
        checks += _matroska_checks(path, len(decoded.pts))
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
        completeness_checks=checks,
    )


def _decode_all(
    container: av.container.InputContainer,
    stream: av.video.VideoStream,
    logs: FfmpegLog,
    decoded: _Decoded,
    on_frame: FrameConsumer,
) -> None:
    """Account for every packet, stopping at the first sign of damage."""
    for packet in container.demux(stream):
        if packet.is_corrupt:
            raise _damaged("demuxer flagged a corrupt packet", len(decoded.pts))
        decoded.discarded += packet.is_discard
        for frame in packet.decode():
            if frame.is_corrupt:
                raise _damaged("decoder flagged a corrupt frame", len(decoded.pts))
            _require_one_shape(frame, decoded)
            decoded.interlaced += frame.interlaced_frame
            on_frame(len(decoded.pts), frame)
            decoded.pts.append(frame.pts)
        if logs:
            raise _damaged(_last_log(logs), len(decoded.pts))
    if logs:
        raise _damaged(_last_log(logs), len(decoded.pts))


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


def _frame_count_checks(declared_frames: int, decoded: _Decoded) -> tuple[str, ...]:
    """Compare against the container's own frame count, when it stores one.

    An edit list can mark stored samples as never presented. They are present in the file, so
    they count toward the total without becoming frames of the sequence.
    """
    if declared_frames <= 0:
        return ()
    accounted = len(decoded.pts) + decoded.discarded
    if accounted < declared_frames:
        raise _damaged(f"container declares {declared_frames} frames", len(decoded.pts))
    return (FRAME_COUNT_CHECK,) if accounted == declared_frames else ()


def _matroska_checks(path: Path, decoded_frames: int) -> tuple[str, ...]:
    """Compare the file against the segment length written in its own header."""
    segment_end = matroska_segment_end(path)
    if segment_end is None:
        return ()
    size = path.stat().st_size
    if size < segment_end:
        raise _damaged(f"segment ends at byte {segment_end}, file has {size}", decoded_frames)
    return (SEGMENT_SIZE_CHECK,)


def _last_log(logs: FfmpegLog) -> str:
    return logs[-1][2].strip() if logs else ""
