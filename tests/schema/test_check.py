"""`make lint-contracts`: the shipped set passes, and each way of breaking one is caught."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ss_track.schema.check import check_contract_set, main
from tests.schema.conftest import (
    CONTRACTS,
    SHA256_REF,
    Register,
    contract_schema,
    frame_set_path,
    read_registry,
    version_entry,
    versioned_schema,
    write_registry,
)

_FRAME_SET = "record/frame-set 1.0.0"


def _frame_set_entry(registry: dict[str, Any]) -> dict[str, Any]:
    contract = next(item for item in registry["contracts"] if item["id"] == "frame-set")
    entry: dict[str, Any] = contract["versions"][0]
    return entry


def test_the_shipped_set_passes() -> None:
    assert check_contract_set(CONTRACTS) == []


def test_the_private_copy_passes_before_a_test_damages_it(contract_root: Path) -> None:
    assert check_contract_set(contract_root) == []


def test_an_edited_frozen_file_fails(contract_root: Path) -> None:
    path = frame_set_path(contract_root)
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["properties"]["bundles"]["minItems"] = 2
    path.write_text(json.dumps(schema), encoding="utf-8")

    findings = check_contract_set(contract_root)

    assert any(item.startswith(f"{_FRAME_SET}: frozen file was edited") for item in findings)
    assert any("structure fingerprint is stale" in item for item in findings)


def test_an_edited_description_fails_on_meaning_alone(contract_root: Path) -> None:
    path = frame_set_path(contract_root)
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["properties"]["bundles"]["description"] = "Something else."
    path.write_text(json.dumps(schema), encoding="utf-8")

    findings = check_contract_set(contract_root)

    assert any("meaning fingerprint is stale" in item for item in findings)
    assert not any("structure fingerprint is stale" in item for item in findings)


def test_a_formatting_edit_of_a_frozen_file_fails_with_its_fingerprints_intact(
    contract_root: Path,
) -> None:
    path = frame_set_path(contract_root)
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert "frozen file was edited" in findings[0]


@pytest.mark.parametrize("fingerprint", ["structure", "meaning"])
def test_a_stale_fingerprint_fails(contract_root: Path, fingerprint: str) -> None:
    registry = read_registry(contract_root)
    _frame_set_entry(registry)["fingerprints"][fingerprint] = "0" * 64
    write_registry(contract_root, registry)

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert f"{fingerprint} fingerprint is stale" in findings[0]
    assert findings[0].startswith(_FRAME_SET)


def test_a_finding_gives_the_value_an_author_needs(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    entry = _frame_set_entry(registry)
    pinned = entry["fingerprints"]["structure"]
    entry["fingerprints"]["structure"] = "0" * 64
    write_registry(contract_root, registry)

    assert pinned in check_contract_set(contract_root)[0]


def test_a_file_the_registry_does_not_list_fails(contract_root: Path) -> None:
    stray = contract_root / "record" / "frame-set" / "1.1.0.json"
    stray.write_text(frame_set_path(contract_root).read_text(encoding="utf-8"), encoding="utf-8")

    assert check_contract_set(contract_root) == [
        "record/frame-set/1.1.0.json: not listed in the registry"
    ]


def test_a_listed_file_that_is_missing_fails(contract_root: Path) -> None:
    frame_set_path(contract_root).unlink()

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert findings[0].startswith(f"{_FRAME_SET}: cannot read the file")


def test_a_frozen_file_that_is_not_json_fails(contract_root: Path) -> None:
    frame_set_path(contract_root).write_text("{", encoding="utf-8")

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert "cannot read" in findings[0]


def test_a_registry_that_breaks_its_schema_fails(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    registry["contracts"][0]["surprise"] = True
    write_registry(contract_root, registry)

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert "surprise" in findings[0]


@pytest.mark.parametrize("field", ["version", "file_sha256", "fingerprints", "change"])
def test_a_version_entry_is_complete(contract_root: Path, field: str) -> None:
    registry = read_registry(contract_root)
    del _frame_set_entry(registry)[field]
    write_registry(contract_root, registry)

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert field in findings[0]


def test_a_repeated_key_in_the_registry_fails(contract_root: Path) -> None:
    path = contract_root / "registry.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "schema_version: 1\n", encoding="utf-8")

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert "duplicate key" in findings[0]


def test_a_missing_registry_fails(contract_root: Path) -> None:
    (contract_root / "registry.yaml").unlink()

    assert "cannot read registry.yaml" in check_contract_set(contract_root)[0]


def test_a_repeated_contract_fails(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    registry["contracts"].insert(0, registry["contracts"][0])
    write_registry(contract_root, registry)

    assert "registry contracts are repeated or out of family and id order" in (
        check_contract_set(contract_root)
    )


def test_contracts_out_of_order_fail(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    registry["contracts"].reverse()
    write_registry(contract_root, registry)

    assert "registry contracts are repeated or out of family and id order" in (
        check_contract_set(contract_root)
    )


def test_versions_are_held_to_numeric_order(contract_root: Path) -> None:
    directory = contract_root / "shared" / "types"
    source = directory / "1.0.0.json"
    registry = read_registry(contract_root)
    types = next(item for item in registry["contracts"] if item["id"] == "types")
    entries = []
    for version in ("10.0.0", "9.0.0"):
        schema = json.loads(source.read_text(encoding="utf-8"))
        schema["$id"] = f"urn:ss-track:contract:shared:types:{version}"
        path = directory / f"{version}.json"
        path.write_text(json.dumps(schema), encoding="utf-8")
        entries.append(version_entry(path))
    types["versions"] = [types["versions"][0], *entries]
    write_registry(contract_root, registry)
    assert check_contract_set(contract_root) == [
        "shared/types: versions are repeated or out of order"
    ]

    types["versions"] = [types["versions"][0], *reversed(entries)]
    write_registry(contract_root, registry)
    assert check_contract_set(contract_root) == []


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
    _frame_set_entry(registry)["change"] = change
    write_registry(contract_root, registry)

    assert missing in check_contract_set(contract_root)[0]


def test_the_gate_exits_by_its_findings(
    contract_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    assert main(["--root", str(contract_root)]) == 0
    assert "[contracts] 0 finding(s)" in caplog.text

    frame_set_path(contract_root).write_text("{}", encoding="utf-8")

    assert main(["--root", str(contract_root)]) == 1
    assert "ERROR:" in caplog.text


def test_the_gate_defaults_to_the_set_that_ships(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    assert main([]) == 0
