"""`make lint-contracts`: identity, dialect, references, stamps, drafts and majors of each file."""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.schema.registry.check import check_contract_set
from tests.schema.conftest import (
    SHA256_REF,
    Register,
    contract_schema,
    frame_set_entry,
    read_registry,
    version_entry,
    versioned_schema,
    write_registry,
)


def test_a_file_under_another_identity_fails(contract_root: Path, register: Register) -> None:
    schema = versioned_schema("declaration", "placed", "1.0.0")
    path = register(schema)
    schema["$id"] = "urn:ss-track:contract:declaration:other:1.0.0"
    path.write_text(json.dumps(schema), encoding="utf-8")
    registry = read_registry(contract_root)
    entry = next(item for item in registry["contracts"] if item["id"] == "placed")
    entry["versions"] = [version_entry(path, version="1.0.0")]
    write_registry(contract_root, registry)

    findings = check_contract_set(contract_root)

    assert any("$id is" in item and "expected" in item for item in findings)


def test_a_frozen_file_outside_the_dialect_fails(contract_root: Path, register: Register) -> None:
    schema = versioned_schema("declaration", "wide", "1.0.0")
    schema["additionalProperties"] = True
    register(schema)

    findings = check_contract_set(contract_root)

    assert any(item.startswith("declaration/wide 1.0.0:") for item in findings)


def test_a_dangling_local_reference_fails(contract_root: Path, register: Register) -> None:
    schema = versioned_schema("declaration", "dangling", "1.0.0")
    schema["properties"]["name"] = {"$ref": "#/$defs/nothing", "description": "A."}
    register(schema)

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert "resolves to nothing" in findings[0]


@pytest.mark.parametrize(
    "reference",
    [
        "urn:ss-track:contract:shared:types:9.0.0#/$defs/sha256",
        "urn:ss-track:contract:shared:types:1.0.0#/$defs/nothing",
    ],
)
def test_a_dangling_reference_to_another_contract_fails(
    contract_root: Path, register: Register, reference: str
) -> None:
    schema = versioned_schema("declaration", "dangling", "1.0.0")
    schema["properties"]["name"] = {"$ref": reference, "description": "A."}
    register(schema)

    assert any(reference in item for item in check_contract_set(contract_root))


def test_a_reference_to_a_frozen_definition_resolves(
    contract_root: Path, register: Register
) -> None:
    schema = versioned_schema("declaration", "linked", "1.0.0")
    schema["properties"]["name"] = {"$ref": SHA256_REF, "description": "A."}
    register(schema)

    assert check_contract_set(contract_root) == []


def test_a_declaration_stamps_its_major(contract_root: Path, register: Register) -> None:
    schema = versioned_schema("declaration", "stamped", "2.0.0")
    schema["properties"]["schema_version"]["const"] = 1
    register(schema)

    assert any("must be the integer const 2" in x for x in check_contract_set(contract_root))


def test_a_declaration_with_no_stamp_fails(contract_root: Path, register: Register) -> None:
    register(contract_schema("declaration", "bare", "1.0.0"))

    assert any("schema_version" in item for item in check_contract_set(contract_root))


def test_a_stamp_with_no_type_fails(contract_root: Path, register: Register) -> None:
    schema = versioned_schema("declaration", "loose", "1.0.0")
    del schema["properties"]["schema_version"]["type"]
    register(schema)

    assert any("schema_version" in item for item in check_contract_set(contract_root))


def _record_schema(**fields: object) -> dict[str, Any]:
    schema = versioned_schema("record", "held", "1.0.0")
    kind = {"type": "string", "const": "ss-track.held", "description": "Names this format."}
    seal = {"$ref": SHA256_REF, "description": "Seal."}
    schema["properties"] |= {"kind": kind, "manifest_sha256": seal}
    return schema | {"required": ["kind", "schema_version", "manifest_sha256"]} | fields


def test_a_complete_record_passes(contract_root: Path, register: Register) -> None:
    register(_record_schema())

    assert check_contract_set(contract_root) == []


def test_a_record_requires_its_seal(contract_root: Path, register: Register) -> None:
    register(_record_schema(required=["kind", "schema_version"]))

    assert any("must require manifest_sha256" in x for x in check_contract_set(contract_root))


def test_a_record_states_its_kind_as_a_const(contract_root: Path, register: Register) -> None:
    schema = _record_schema()
    del schema["properties"]["kind"]["const"]
    register(schema)

    assert any("state its kind" in item for item in check_contract_set(contract_root))


def test_a_draft_states_why_and_needs_no_version(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    draft = {
        "family": "record",
        "id": "z-draft",
        "owner": "data-contracts",
        "status": "draft",
        "description": "Not yet stated.",
        "reason": "The dialect cannot state it.",
        "versions": [],
    }
    registry["contracts"].append(draft)
    registry["contracts"].sort(key=lambda item: (item["family"], item["id"]))
    write_registry(contract_root, registry)
    assert check_contract_set(contract_root) == []

    del draft["reason"]
    write_registry(contract_root, registry)
    assert "reason" in check_contract_set(contract_root)[0]


@pytest.mark.parametrize("status", ["active", "deprecated", "retired"])
def test_a_contract_past_draft_has_a_version(contract_root: Path, status: str) -> None:
    registry = read_registry(contract_root)
    registry["contracts"][0] |= {"status": status, "versions": []}
    write_registry(contract_root, registry)

    assert check_contract_set(contract_root)


@pytest.mark.parametrize("missing", ["migration", "disposition"])
def test_a_major_states_its_migration_and_disposition(contract_root: Path, missing: str) -> None:
    registry = read_registry(contract_root)
    change = {
        "class": "major",
        "summary": "Changed.",
        "migration": "Rebuild.",
        "disposition": "facts",
    }
    del change[missing]
    frame_set_entry(registry)["change"] = change
    write_registry(contract_root, registry)

    assert missing in check_contract_set(contract_root)[0]


def test_dangling_annotation_fails_contract_gate(contract_root: Path, register: Register) -> None:
    schema = versioned_schema("declaration", "dangling", "1.0.0")
    schema["properties"]["name"] = {
        "type": "string",
        "description": "A.",
        "x-references": "record/frame-bundle#/properties/missing",
    }
    register(schema)
    assert any(
        "x-references" in item and "resolves to nothing" in item
        for item in check_contract_set(contract_root)
    )
