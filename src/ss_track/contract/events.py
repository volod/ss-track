"""Parse one protobuf-JSON JSON Lines stream of a named event."""

import json
from typing import cast

from google.protobuf.json_format import MessageToDict, ParseDict, ParseError
from google.protobuf.message import Message

from ss_track.contract.checks import reject
from ss_track.contract.meaning import check_event
from ss_track.core.refusal import CorpusRefusal, JsonValue
from ss_track.core.strict_json import finite_float, reject_constant, unique_object

_TYPES: dict[str, type[Message]] | None = None


def message_names() -> tuple[str, ...]:
    """Return the event messages a line may name."""
    return tuple(sorted(_types()))


def parse_message(line: str, message_name: str) -> Message:
    """Parse one JSON object as ``message_name``, or reject it with a reason."""
    body = _object(line)
    message = _types()[message_name]() if message_name in _types() else None
    if message is None:
        reject(f"unknown event {message_name}")
    try:
        ParseDict(body, message, ignore_unknown_fields=False)
    except ParseError as error:
        reject(str(error))
    check_event(message)
    return message


def parse_json_lines(text: str, message_name: str) -> list[dict[str, JsonValue]]:
    """Parse every non-blank line. A bad line names its number and the reason."""
    parsed = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed.append(event_dict(parse_message(line, message_name)))
        except CorpusRefusal as refusal:
            details: dict[str, JsonValue] = {"line": number, **refusal.details}
            raise CorpusRefusal(
                refusal.code, f"line {number}: {refusal.message}", details
            ) from refusal
    return parsed


def event_dict(message: Message) -> dict[str, JsonValue]:
    """Return the protobuf-JSON object, using each field's ``json_name``."""
    loaded = json.loads(event_line(message))
    if not isinstance(loaded, dict):
        reject("event JSON must be an object")
    return cast(dict[str, JsonValue], loaded)


def event_line(message: Message) -> str:
    """Return one canonical JSON line for a message that has already been checked."""
    return json.dumps(
        MessageToDict(message),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _object(line: str) -> dict[str, JsonValue]:
    try:
        value = json.loads(
            line,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except json.JSONDecodeError as error:
        reject(f"malformed JSON: {error.msg}")
    except ValueError as error:
        reject(str(error))
    if not isinstance(value, dict):
        reject("an event line must be a JSON object")
    return cast(dict[str, JsonValue], value)


def _types() -> dict[str, type[Message]]:
    global _TYPES
    if _TYPES is None:
        _TYPES = _load_types()
    return _TYPES


def _load_types() -> dict[str, type[Message]]:
    from ss_track.contract.gen import analytics_pb2, clock_pb2, frame_pb2, trial_pb2, wire_pb2

    found: dict[str, type[Message]] = {}
    modules = (analytics_pb2, clock_pb2, frame_pb2, trial_pb2, wire_pb2)
    for module in modules:
        for name in module.DESCRIPTOR.message_types_by_name:
            if name in found:
                raise RuntimeError(f"duplicate event message {name}")
            found[name] = getattr(module, name)
    return found
