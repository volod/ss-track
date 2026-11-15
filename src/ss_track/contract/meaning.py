"""Semantic checks for frame delivery and module wire events."""

from collections.abc import Callable, Iterable

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

from ss_track.contract.checks import (
    TIMESTAMP_QUALITIES,
    check_box,
    check_clock,
    check_event_ref,
    check_point,
    check_time_base,
    child,
    enum_name,
    flag,
    is_message,
    number_field,
    reject,
    require_non_negative,
    require_sha256,
    require_text,
    require_unit_interval,
    text_field,
)
from ss_track.contract.meaning_records import record_checkers

Checker = Callable[[Message], None]


def check_event(message: Message) -> None:
    """Apply the meaning rules of one message and of every message inside it."""
    checker = _checkers().get(message.DESCRIPTOR.name)
    if checker is not None:
        checker(message)
    for field, value in message.ListFields():
        _visit(field, value)


def wire_checkers() -> dict[str, Checker]:
    """Return the checkers for the frame and wire packages."""
    return {
        "FrameRef": check_frame_ref,
        "ClockTime": check_clock,
        "Box": check_box,
        "Point": check_point,
        "EventRef": check_event_ref,
        "TargetSelection": check_selection,
        "Detection": check_detection,
        "TrackState": check_track,
        "FrameResult": check_frame_result,
        "AdvisoryAction": check_advisory,
        "RunEvent": check_run_event,
    }


def _checkers() -> dict[str, Checker]:
    return wire_checkers() | record_checkers()


def _visit(field: FieldDescriptor, value: object) -> None:
    if not is_message(field):
        return
    if field.is_repeated:
        if isinstance(value, Iterable):
            for item in value:
                if isinstance(item, Message):
                    check_event(item)
        return
    if isinstance(value, Message):
        check_event(value)


def check_frame_ref(message: Message) -> None:
    """Every staged-bundle field keeps its meaning, including transform and content."""
    require_text(text_field(message, "stream_id"), "stream_id")
    require_sha256(text_field(message, "source_sha256"), "source_sha256")
    require_sha256(text_field(message, "bundle_sha256"), "bundle_sha256")
    require_sha256(text_field(message, "sha256"), "sha256")
    require_text(text_field(message, "frame_name"), "frame_name")
    require_text(text_field(message, "pixel_format"), "pixel_format")
    require_text(text_field(message, "transform"), "transform")
    quality = text_field(message, "timestamp_quality")
    if quality not in TIMESTAMP_QUALITIES:
        reject("timestamp_quality must be measured, derived or missing")
    if number_field(message, "width") < 1 or number_field(message, "height") < 1:
        reject("width and height must be positive")
    if message.HasField("time_base"):
        check_time_base(text_field(message, "time_base"))
    if message.HasField("capture_clock_evidence"):
        require_text(text_field(message, "capture_clock_evidence"), "capture_clock_evidence")


def check_selection(message: Message) -> None:
    """A target selection names one frame and one box."""
    _one_frame(message, "a target selection names one frame")
    require_text(text_field(message, "instance_id"), "instance_id")
    if not message.HasField("box"):
        reject("target selection box is missing")


def check_detection(message: Message) -> None:
    """A detection has a class, a class confidence and a box."""
    require_text(text_field(message, "class_id"), "class_id")
    if not message.HasField("class_confidence"):
        reject("class_confidence is missing")
    require_unit_interval(number_field(message, "class_confidence"), "class_confidence")
    if not message.HasField("box"):
        reject("detection box is missing")


def check_track(message: Message) -> None:
    """Measured and predicted tracks carry a box. Lost and abstain may omit one."""
    require_text(text_field(message, "track_id"), "track_id")
    update = enum_name(message, "update")
    if update == "TRACK_UPDATE_UNSPECIFIED":
        reject("track update is missing")
    if not message.HasField("presence_confidence"):
        reject("presence_confidence is missing")
    require_unit_interval(number_field(message, "presence_confidence"), "presence_confidence")
    if update in {"MEASURED", "PREDICTED"} and not message.HasField("box"):
        reject("a measured or predicted track needs a box")


def check_frame_result(message: Message) -> None:
    """A frame result acknowledges one frame. Empty detections are a valid result."""
    _one_frame(message, "a frame result acknowledges one frame")


def check_advisory(message: Message) -> None:
    """An advisory action names one frame. Its confidence is optional."""
    _one_frame(message, "an advisory action names one frame")
    kind = enum_name(message, "kind")
    if kind == "ADVISORY_KIND_UNSPECIFIED":
        reject("advisory kind is missing")
    if kind in {"CENTER", "HOLD"}:
        require_text(text_field(message, "instance_id"), "instance_id")
    if not message.HasField("horizon_seconds"):
        reject("horizon_seconds is missing")
    require_non_negative(number_field(message, "horizon_seconds"), "horizon_seconds")
    if message.HasField("action_confidence"):
        require_unit_interval(number_field(message, "action_confidence"), "action_confidence")
    require_text(text_field(message, "reason"), "reason")


def check_run_event(message: Message) -> None:
    """A run event has a code and a reason."""
    if not message.HasField("ref"):
        reject("run event needs an event ref")
    if enum_name(message, "code") == "RUN_CODE_UNSPECIFIED":
        reject("run event code is missing")
    require_text(text_field(message, "reason"), "reason")


def _one_frame(message: Message, reason: str) -> None:
    if not message.HasField("ref") or flag(child(message, "ref"), "unframed"):
        reject(reason)
