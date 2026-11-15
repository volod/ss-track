"""Structure and meaning of one event file, independent of its descriptor bytes."""

from google.protobuf import descriptor_pb2

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import JsonValue


def structure_record(own: descriptor_pb2.FileDescriptorProto) -> dict[str, JsonValue]:
    """Return the field numbers, types, labels and JSON names of one event file."""
    return {
        "package": own.package,
        "messages": [_message(item) for item in own.message_type],
        "enums": [_enum(item) for item in own.enum_type],
    }


def meaning_record(own: descriptor_pb2.FileDescriptorProto) -> dict[str, JsonValue]:
    """Return the source comments of one event file."""
    return {"comments": _comments(own)}


def digest(value: dict[str, JsonValue]) -> str:
    """Return the canonical hash of one fingerprint record."""
    return sha256_bytes(canonical_json(value))


def _message(message: descriptor_pb2.DescriptorProto) -> dict[str, JsonValue]:
    return {
        "name": message.name,
        "fields": [_field(field) for field in message.field],
        "oneofs": [item.name for item in message.oneof_decl],
        "enums": [_enum(item) for item in message.enum_type],
        "messages": [_message(item) for item in message.nested_type],
    }


def _field(field: descriptor_pb2.FieldDescriptorProto) -> dict[str, JsonValue]:
    record: dict[str, JsonValue] = {
        "name": field.name,
        "number": field.number,
        "label": int(field.label),
        "type": int(field.type),
        "type_name": field.type_name,
        "json_name": field.json_name,
        "proto3_optional": field.proto3_optional,
    }
    if field.HasField("oneof_index"):
        record["oneof_index"] = field.oneof_index
    return record


def _enum(enum: descriptor_pb2.EnumDescriptorProto) -> dict[str, JsonValue]:
    values: list[JsonValue] = [{"name": item.name, "number": item.number} for item in enum.value]
    return {"name": enum.name, "values": values}


def _comments(own: descriptor_pb2.FileDescriptorProto) -> list[JsonValue]:
    comments: list[JsonValue] = []
    for location in own.source_code_info.location:
        text = (location.leading_comments or location.trailing_comments).strip()
        if not text:
            continue
        comments.append({"path": ".".join(str(part) for part in location.path), "text": text})
    return comments
