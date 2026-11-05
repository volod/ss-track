"""Choose the one video stream a recording names.

The index is a fact of the source, not of the shared decode policy. A corpus pins one policy for
every source, and putting the index in that policy would make a second camera look like a new
decoder.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import av

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

VIDEO_STREAM_INDEX = "video_stream_index"


@dataclass(frozen=True, slots=True)
class _VideoStream:
    """One video stream, as an operator needs it named in a refusal."""

    index: int
    container_index: int
    codec: str
    width: int
    height: int

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "index": self.index,
            "container_index": self.container_index,
            "codec": self.codec,
            "width": self.width,
            "height": self.height,
        }


def recorded_video_stream_index(sequence: Mapping[str, Any]) -> int:
    """Return the video stream a source record decoded. Absence means the first."""
    value = sequence.get(VIDEO_STREAM_INDEX, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "source record video_stream_index is not a stream index",
        )
    return cast(int, value)


def select_video_stream(
    streams: Sequence[av.video.VideoStream], index: int | None
) -> tuple[av.video.VideoStream, int]:
    """Return the named video stream and its index, or refuse an unnamed choice.

    `index` counts video streams from zero. Omit it only when the container has one video stream.
    """
    if not streams:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "media has no video stream")
    if index is None:
        if len(streams) == 1:
            return streams[0], 0
        raise _unspecified(streams, None)
    if index < 0 or index >= len(streams):
        raise _unspecified(streams, index)
    return streams[index], index


def _unspecified(streams: Sequence[av.video.VideoStream], index: int | None) -> CorpusRefusal:
    described = tuple(_describe(position, stream) for position, stream in enumerate(streams))
    listed: list[JsonValue] = [item.to_record() for item in described]
    count = len(described)
    if index is None:
        message = f"container has {count} video streams; declare source.{VIDEO_STREAM_INDEX}"
    else:
        message = f"source.{VIDEO_STREAM_INDEX} {index} is not a video stream in this container"
    details: dict[str, JsonValue] = {"video_streams": listed}
    if index is not None:
        details[VIDEO_STREAM_INDEX] = index
    return CorpusRefusal(RefusalCode.VIDEO_STREAM_UNSPECIFIED, message, details)


def _describe(position: int, stream: av.video.VideoStream) -> _VideoStream:
    context = stream.codec_context
    width = 0 if context is None else context.width
    height = 0 if context is None else context.height
    return _VideoStream(
        position, _container_index(stream, position), _codec_name(stream), width, height
    )


def _container_index(stream: av.video.VideoStream, position: int) -> int:
    found = getattr(stream, "index", position)
    if isinstance(found, bool) or not isinstance(found, int):
        return position
    return found


def _codec_name(stream: av.video.VideoStream) -> str:
    context = stream.codec_context
    codec = None if context is None else context.codec
    name = None if codec is None else codec.name
    if isinstance(name, str) and name:
        return name
    return "unknown"
