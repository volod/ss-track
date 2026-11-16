"""Round-trip the staged bundle ``FrameRef`` through its event message."""

from google.protobuf.message import Message

from ss_track.contract.events import event_line, parse_message
from ss_track.contract.meaning import check_event
from ss_track.corpus.bundles.frames import FrameRef


def frame_ref_line(ref: FrameRef) -> str:
    """Return the protobuf-JSON line of one staged frame reference."""
    message = _fill(ref)
    check_event(message)
    return event_line(message)


def frame_ref_from_line(line: str) -> FrameRef:
    """Read one frame reference, rejecting a line that breaks the event schema."""
    return _read(parse_message(line, "FrameRef"))


def _fill(ref: FrameRef) -> Message:
    from ss_track.contract.gen import frame_pb2

    message = frame_pb2.FrameRef(
        stream_id=ref.stream_id,
        source_sha256=ref.source_sha256,
        frame_index=ref.frame_index,
        content_frame_index=ref.content_frame_index,
        timestamp_quality=ref.timestamp_quality,
        width=ref.width,
        height=ref.height,
        pixel_format=ref.pixel_format,
        transform=ref.transform,
        bundle_sha256=ref.bundle_sha256,
        frame_name=ref.frame_name,
        sha256=ref.sha256,
    )
    if ref.pts is not None:
        message.pts = ref.pts
    if ref.time_base is not None:
        message.time_base = ref.time_base
    if ref.capture_clock_evidence is not None:
        message.capture_clock_evidence = ref.capture_clock_evidence
    if not isinstance(message, Message):
        raise TypeError("FrameRef")
    return message


def _read(message: Message) -> FrameRef:
    return FrameRef(
        stream_id=_text(message, "stream_id"),
        source_sha256=_text(message, "source_sha256"),
        frame_index=_count(message, "frame_index"),
        content_frame_index=_count(message, "content_frame_index"),
        pts=_optional_count(message, "pts"),
        time_base=_optional_text(message, "time_base"),
        timestamp_quality=_text(message, "timestamp_quality"),
        capture_clock_evidence=_optional_text(message, "capture_clock_evidence"),
        width=_count(message, "width"),
        height=_count(message, "height"),
        pixel_format=_text(message, "pixel_format"),
        transform=_text(message, "transform"),
        bundle_sha256=_text(message, "bundle_sha256"),
        frame_name=_text(message, "frame_name"),
        sha256=_text(message, "sha256"),
    )


def _text(message: Message, name: str) -> str:
    value = getattr(message, name)
    if not isinstance(value, str):
        raise TypeError(name)
    return value


def _count(message: Message, name: str) -> int:
    value = getattr(message, name)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TypeError(name)


def _optional_text(message: Message, name: str) -> str | None:
    if not message.HasField(name):
        return None
    return _text(message, name)


def _optional_count(message: Message, name: str) -> int | None:
    if not message.HasField(name):
        return None
    return _count(message, name)
