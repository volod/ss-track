"""`make lint-contracts`: the shipped set passes, and a broken frozen file or registry is caught."""

import json
import logging
from pathlib import Path

import pytest

from ss_track.schema.registry.check import check_contract_set, main
from tests.schema.conftest import (
    CONTRACTS,
    frame_set_entry,
    frame_set_path,
    read_registry,
    version_entry,
    write_registry,
)

_FRAME_SET = "record/frame-set 1.0.0"


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
    frame_set_entry(registry)["fingerprints"][fingerprint] = "0" * 64
    write_registry(contract_root, registry)

    findings = check_contract_set(contract_root)

    assert len(findings) == 1
    assert f"{fingerprint} fingerprint is stale" in findings[0]
    assert findings[0].startswith(_FRAME_SET)


def test_a_finding_gives_the_value_an_author_needs(contract_root: Path) -> None:
    registry = read_registry(contract_root)
    entry = frame_set_entry(registry)
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
    del frame_set_entry(registry)[field]
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
