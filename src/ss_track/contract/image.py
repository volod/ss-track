"""Frozen event descriptor sets: identity, fingerprints and package checks.

The bytes under ``contracts/event/<id>/<version>.binpb`` are the descriptor set
``buf breaking`` compares. JSON Schema fingerprints do not apply to them.
"""

import re
from collections.abc import Iterable

from google.protobuf import descriptor_pb2
from google.protobuf.message import DecodeError

from ss_track.contract.image_shape import digest, meaning_record, structure_record

_BARE_PACKAGES = frozenset({"google.protobuf", "ss_track.contract.v1"})
_URN = re.compile(
    r"^urn:ss-track:contract:event:"
    r"([a-z0-9]+(?:-[a-z0-9]+)*):((?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2})$"
)
_MESSAGE = 4  # FileDescriptorProto.message_type
_FIELD = 2  # DescriptorProto.field
_URN_FIELD = 50001


def parse_set(payload: bytes) -> descriptor_pb2.FileDescriptorSet:
    """Parse one descriptor set, refusing bytes that are not one."""
    parsed = descriptor_pb2.FileDescriptorSet()
    try:
        parsed.ParseFromString(payload)
    except DecodeError as error:
        raise ValueError(f"descriptor set cannot be read: {error}") from error
    if not parsed.file:
        raise ValueError("descriptor set contains no files")
    return parsed


def _urn_of(item: descriptor_pb2.FileDescriptorProto) -> str:
    """Read the custom file option from its wire field. Generated options omit it."""
    if not item.HasField("options"):
        return ""
    return _option(item.options.SerializeToString(), _URN_FIELD)


def _option(payload: bytes, field_number: int) -> str:
    target = (field_number << 3) | 2
    index = 0
    size = len(payload)
    while index < size:
        key, index = _varint(payload, index)
        wire = key & 7
        if wire == 0:
            _, index = _varint(payload, index)
        elif wire == 1:
            index += 8
        elif wire == 5:
            index += 4
        elif wire == 2:
            length, index = _varint(payload, index)
            chunk = payload[index : index + length]
            index += length
            if key == target:
                try:
                    return chunk.decode()
                except UnicodeDecodeError as error:
                    raise ValueError("contract URN is not text") from error
        else:
            return ""
    return ""


def _varint(payload: bytes, index: int) -> tuple[int, int]:
    value = 0
    shift = 0
    try:
        while True:
            byte = payload[index]
            index += 1
            value |= (byte & 0x7F) << shift
            if byte < 128:
                return value, index
            shift += 7
    except IndexError as error:
        raise ValueError("descriptor options are truncated") from error


def package_urn(payload: bytes, package: str) -> str:
    """Return the contract URN declared by ``<package>.proto``."""
    parsed = parse_set(payload)
    found = [_urn_of(item) for item in parsed.file if item.name == f"{package}.proto"]
    if len(found) != 1 or not found[0]:
        raise ValueError(f"{package} descriptor has no contract URN")
    return found[0]


def fingerprints(payload: bytes, urn: str) -> tuple[str, str]:
    """Return structure and meaning hashes of the file that declares ``urn``."""
    own = _own_file(payload, urn)
    return digest(structure_record(own)), digest(meaning_record(own))


def top_field_comments(payload: bytes, urn: str) -> dict[str, str]:
    """Return leading comments of top-level fields, keyed ``Message.field``."""
    own = _own_file(payload, urn)
    locations = {
        tuple(location.path): (location.leading_comments or location.trailing_comments).strip()
        for location in own.source_code_info.location
    }
    comments = {}
    for message_index, message in enumerate(own.message_type):
        for field_index, field in enumerate(message.field):
            text = locations.get((_MESSAGE, message_index, _FIELD, field_index), "")
            if text:
                comments[f"{message.name}.{field.name}"] = text
    return comments


def event_version_findings(
    payload: bytes, urn: str, structure: str, meaning: str, known_urns: set[str]
) -> list[str]:
    """Check one frozen descriptor against its URN, package and fingerprints."""
    try:
        parsed = parse_set(payload)
        findings = _identity_findings(parsed, urn, known_urns)
    except ValueError as error:
        return [str(error)]
    if findings:
        return findings
    try:
        found_structure, found_meaning = fingerprints(payload, urn)
    except ValueError as error:
        return [str(error)]
    if found_structure != structure:
        findings.append(
            f"structure fingerprint is stale: registry {structure}, file {found_structure}"
        )
    if found_meaning != meaning:
        findings.append(f"meaning fingerprint is stale: registry {meaning}, file {found_meaning}")
    return findings


def _identity_findings(
    parsed: descriptor_pb2.FileDescriptorSet, urn: str, known_urns: set[str]
) -> list[str]:
    findings = []
    matched = 0
    for item in parsed.file:
        declared = _urn_of(item)
        if item.package in _BARE_PACKAGES:
            if declared:
                findings.append(f"{item.name} is not an event package and declares {declared}")
            continue
        findings.extend(_event_file(item, declared, urn, known_urns))
        matched += int(declared == urn)
    if matched != 1:
        findings.append(f"{urn} is declared by {matched} files")
    return findings


def _event_file(
    item: descriptor_pb2.FileDescriptorProto, declared: str, urn: str, known_urns: set[str]
) -> list[str]:
    match = _URN.fullmatch(declared)
    if match is None:
        return [f"{item.name} contract URN is {declared or 'missing'}"]
    contract_id, version = match.group(1), match.group(2)
    major = version.split(".", 1)[0]
    package = f"ss_track.event.{contract_id.replace('-', '_')}.v{major}"
    findings = []
    if item.package != package:
        findings.append(f"{item.name} package is {item.package}, expected {package}")
    if declared not in known_urns:
        findings.append(f"{item.name} URN {declared} is not a frozen event version")
    if declared == urn:
        findings.extend(_json_names(item))
    return findings


def _json_names(item: descriptor_pb2.FileDescriptorProto) -> list[str]:
    findings = []
    for message in _messages(item.message_type):
        for field in message.field:
            if field.json_name != field.name:
                findings.append(
                    f"{message.name}.{field.name} json_name is {field.json_name or 'unset'}"
                )
    return findings


def _own_file(payload: bytes, urn: str) -> descriptor_pb2.FileDescriptorProto:
    parsed = parse_set(payload)
    found = [item for item in parsed.file if _urn_of(item) == urn]
    if len(found) != 1:
        raise ValueError(f"{urn} is declared by {len(found)} files")
    if not found[0].package.startswith("ss_track.event."):
        raise ValueError(f"{urn} is not an event package")
    return found[0]


def _messages(
    messages: Iterable[descriptor_pb2.DescriptorProto],
) -> Iterable[descriptor_pb2.DescriptorProto]:
    for message in messages:
        yield message
        yield from _messages(message.nested_type)
