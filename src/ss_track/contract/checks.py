"""Field meanings the protobuf type system does not state."""

import re
from typing import NoReturn

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIME_BASE = re.compile(r"^-?[0-9]+/[1-9][0-9]*$")
_DATE = re.compile(r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])$")
TIMESTAMP_QUALITIES = frozenset({"measured", "derived", "missing"})


def reject(reason: str, **details: JsonValue) -> NoReturn:
    """Reject one event with a reason a caller can show."""
    raise CorpusRefusal(RefusalCode.RECORD_INVALID, reason, details or None)


def text_field(message: Message, name: str) -> str:
    """Return a string field."""
    value = getattr(message, name)
    if not isinstance(value, str):
        reject(f"{name} must be text")
    return value


def number_field(message: Message, name: str) -> float:
    """Return a numeric field."""
    value = getattr(message, name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        reject(f"{name} must be a number")
    return float(value)


def child(message: Message, name: str) -> Message:
    """Return a singular message field."""
    value = getattr(message, name)
    if not isinstance(value, Message):
        reject(f"{name} must be a message")
    return value


def flag(message: Message, name: str) -> bool:
    """Return a boolean field."""
    value = getattr(message, name)
    if not isinstance(value, bool):
        reject(f"{name} must be a boolean")
    return value


def require_text(value: str, label: str) -> None:
    """Refuse blank text and text that is only padding."""
    if not value or value.strip() != value:
        reject(f"{label} must be non-blank text")


def require_sha256(value: str, label: str) -> None:
    """Refuse a digest that is not 64 lowercase hex characters."""
    if _SHA256.fullmatch(value) is None:
        reject(f"{label} must be a SHA-256 hex digest")


def require_unit_interval(value: float, label: str) -> None:
    """Refuse a confidence outside the closed unit interval."""
    if not 0.0 <= value <= 1.0:
        reject(f"{label} must be between 0 and 1")


def require_non_negative(value: float, label: str) -> None:
    """Refuse a negative quantity."""
    if value < 0:
        reject(f"{label} must be non-negative")


def enum_name(message: Message, field: str) -> str:
    """Return the JSON name of an enum field, refusing a number the schema lacks."""
    number = getattr(message, field)
    if isinstance(number, bool) or not isinstance(number, int):
        reject(f"{field} must be an enum")
    enum = message.DESCRIPTOR.fields_by_name[field].enum_type
    if enum is None:
        reject(f"{field} must be an enum")
    found = enum.values_by_number.get(number)
    if found is None:
        reject(f"{field} has an unknown value")
    return str(found.name)


def check_clock(message: Message) -> None:
    """A clock value names its domain, source and uncertainty. Media PTS is not capture."""
    domain = enum_name(message, "domain")
    if domain == "CLOCK_DOMAIN_UNSPECIFIED":
        reject("clock domain is missing")
    require_text(text_field(message, "source"), "clock source")
    if domain == "MEDIA_PTS" and text_field(message, "source") == "capture":
        reject("media PTS is media time, not capture time")
    if message.HasField("time_base"):
        check_time_base(text_field(message, "time_base"))
    if not message.HasField("uncertainty_seconds"):
        reject("clock uncertainty is missing")
    require_non_negative(number_field(message, "uncertainty_seconds"), "clock uncertainty")


def check_box(message: Message) -> None:
    """A box is a positive half-open extent in a named image space."""
    require_text(text_field(message, "space"), "box space")
    width = number_field(message, "width")
    height = number_field(message, "height")
    if width <= 0 or height <= 0:
        reject("box width and height must be positive half-open extents")


def check_point(message: Message) -> None:
    """A point carries pixel coordinates and a non-negative uncertainty."""
    require_text(text_field(message, "space"), "point space")
    if not message.HasField("uncertainty"):
        reject("point uncertainty is missing")
    require_non_negative(number_field(message, "uncertainty"), "point uncertainty")


def check_event_ref(message: Message) -> None:
    """One stable id, and either one source frame or an explicit unframed interval."""
    require_text(text_field(message, "event_id"), "event_id")
    if flag(message, "unframed"):
        _unframed(message)
        return
    _framed(message)


def check_time_base(value: str) -> None:
    """Refuse a time base that is not a rational numerator/denominator."""
    if _TIME_BASE.fullmatch(value) is None:
        reject("time_base must be a rational numerator/denominator")


def check_date(value: str) -> None:
    """Refuse a check date that is not a calendar day."""
    if _DATE.fullmatch(value) is None:
        reject("checked_on must be a YYYY-MM-DD date")


def same_clock_order(start: Message, end: Message) -> None:
    """Refuse an interval that does not advance when both ends share a clock."""
    if enum_name(start, "domain") != enum_name(end, "domain"):
        return
    if text_field(start, "time_base") != text_field(end, "time_base"):
        return
    if number_field(end, "ticks") <= number_field(start, "ticks"):
        reject("interval end must be after its start")


def _framed(message: Message) -> None:
    require_text(text_field(message, "stream_id"), "stream_id")
    require_sha256(text_field(message, "bundle_sha256"), "bundle_sha256")
    if not message.HasField("frame_index"):
        reject("a framed event needs frame_index")
    if message.HasField("interval_start") or message.HasField("interval_end"):
        reject("a framed event does not also carry an interval")


def _unframed(message: Message) -> None:
    if text_field(message, "stream_id") or text_field(message, "bundle_sha256"):
        reject("an unframed event has no source frame")
    if message.HasField("frame_index"):
        reject("an unframed event has no source frame")
    if not message.HasField("interval_start") or not message.HasField("interval_end"):
        reject("an unframed event needs an interval")


def is_message(field: FieldDescriptor) -> bool:
    """Say whether a field holds a message rather than a scalar."""
    return field.type == FieldDescriptor.TYPE_MESSAGE
