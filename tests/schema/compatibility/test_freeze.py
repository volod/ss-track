"""Freeze refuses invalid candidates without publishing bytes or registry pins."""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.freeze import diff_contract, freeze_contract
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.store import load_contract_set
from tests.schema.conftest import Register, contract_schema, read_registry


@pytest.fixture
def candidate(tmp_path: Path, register: Register) -> Path:
    schema = contract_schema("result", "test", "1.0.0")
    register(schema)
    schema["$id"] = "urn:ss-track:contract:result:test:1.1.0"
    schema["properties"]["new"] = {"type": ["string", "null"], "description": "Absent when unused."}
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(schema))
    return path


def _edit(path: Path, **fields: Any) -> None:
    schema = json.loads(path.read_bytes()) | fields
    path.write_text(json.dumps(schema))


def _freeze(root: Path, path: Path, **options: Any) -> None:
    freeze_contract("result/test", path, root=root, summary="Test change.", **options)


def test_diff_is_read_only_and_freeze_creates_valid_pins(
    contract_root: Path, candidate: Path
) -> None:
    before = (contract_root / "registry.yaml").read_bytes()
    result = diff_contract("result/test", candidate, contract_root)
    assert result.to_record()["required_bump"] == "minor"
    assert result.changes[0].pointer == "/properties/new"
    assert (contract_root / "registry.yaml").read_bytes() == before
    _freeze(contract_root, candidate)
    assert check_contract_set(contract_root) == []
    assert (contract_root / "result/test/1.1.0.json").read_bytes() == candidate.read_bytes()
    frozen = load_contract_set(contract_root).named("result/test").versions[-1]
    assert frozen.change == {"class": "minor", "summary": "Test change."}


@pytest.mark.parametrize("version", ["1.0.0", "0.9.0", "1.0.1", "1.1.1", "2.1.0"])
def test_wrong_bumps_leave_no_trace(contract_root: Path, candidate: Path, version: str) -> None:
    _edit(candidate, **{"$id": f"urn:ss-track:contract:result:test:{version}"})
    before = (contract_root / "registry.yaml").read_bytes()
    files = sorted(path.relative_to(contract_root) for path in contract_root.rglob("*"))
    with pytest.raises(CorpusRefusal):
        _freeze(contract_root, candidate)
    assert (contract_root / "registry.yaml").read_bytes() == before
    assert sorted(path.relative_to(contract_root) for path in contract_root.rglob("*")) == files
    assert not list(contract_root.parent.glob(".freeze-*"))


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"migration": "Use a new record."},
        {"disposition": "facts"},
        {"migration": " ", "disposition": "facts"},
    ],
)
def test_major_needs_both_migration_and_disposition(
    contract_root: Path, candidate: Path, options: dict[str, str]
) -> None:
    _edit(candidate, **{"$id": "urn:ss-track:contract:result:test:2.0.0", "required": ["new"]})
    with pytest.raises(CorpusRefusal, match="migration text and a disposition"):
        _freeze(contract_root, candidate, **options)


@pytest.mark.parametrize("disposition", ["view", "facts", "retired"])
def test_major_records_predecessor_disposition(
    contract_root: Path, candidate: Path, disposition: str
) -> None:
    _edit(candidate, **{"$id": "urn:ss-track:contract:result:test:2.0.0", "required": ["new"]})
    _freeze(
        contract_root,
        candidate,
        migration="Rebuild or inspect the old result.",
        disposition=disposition,
    )
    change = load_contract_set(contract_root).named("result/test").versions[-1].change
    assert change["disposition"] == disposition
    assert check_contract_set(contract_root) == []


def test_semantic_change_cannot_hide_under_minor(contract_root: Path, candidate: Path) -> None:
    _freeze(contract_root, candidate)
    _edit(
        candidate,
        **{
            "$id": "urn:ss-track:contract:result:test:1.2.0",
            "properties": {"name": {"type": "number", "description": "Different meaning."}},
        },
    )
    with pytest.raises(CorpusRefusal, match="requires major"):
        _freeze(contract_root, candidate)


def test_new_contract_requires_owner_and_freezes_initial(
    contract_root: Path, tmp_path: Path
) -> None:
    path = tmp_path / "new.json"
    path.write_text(json.dumps(contract_schema("result", "new", "1.0.0")))
    with pytest.raises(CorpusRefusal, match="owner"):
        freeze_contract("result/new", path, root=contract_root, summary="Initial.")
    freeze_contract(
        "result/new", path, root=contract_root, summary="Initial.", owner="data-contracts"
    )
    assert check_contract_set(contract_root) == []


@pytest.mark.parametrize(
    "payload",
    ["[]", "{", '{"type":"string","type":"number"}', '{"minimum":NaN}', '{"minimum":1e999}'],
)
def test_malformed_candidate_is_a_refusal(
    contract_root: Path, candidate: Path, payload: str
) -> None:
    candidate.write_text(payload)
    with pytest.raises(CorpusRefusal):
        _freeze(contract_root, candidate)


def test_bad_reference_and_wrong_identity_refuse(contract_root: Path, candidate: Path) -> None:
    _edit(candidate, properties={"bad": {"$ref": "#/$defs/missing", "description": "Missing."}})
    with pytest.raises(CorpusRefusal, match="resolves to nothing"):
        _freeze(contract_root, candidate)
    _edit(candidate, **{"$id": "urn:ss-track:contract:result:elsewhere:1.1.0"})
    with pytest.raises(CorpusRefusal, match=r"candidate \$id"):
        _freeze(contract_root, candidate)


def test_cli_diff_and_freeze_emit_contracted_results(
    contract_root: Path, candidate: Path, caplog: pytest.LogCaptureFixture
) -> None:
    args = ["result/test", "--file", str(candidate), "--root", str(contract_root)]
    caplog.set_level("INFO")
    assert main(["contracts", "diff", *args]) == 0
    assert json.loads(caplog.records[-1].message)["status"] == "diffed"
    assert main(["contracts", "freeze", *args, "--summary", "CLI change."]) == 0
    assert json.loads(caplog.records[-1].message)["status"] == "frozen"
    assert main(["contracts", "freeze", *args, "--summary", "Overwrite."]) == 1
    assert json.loads(caplog.records[-1].message)["code"] == "CONTRACT_SET_INVALID"


def test_precreated_candidate_can_be_registered(contract_root: Path, candidate: Path) -> None:
    target = contract_root / "result/test/1.1.0.json"
    target.write_bytes(candidate.read_bytes())
    _freeze(contract_root, target)
    assert check_contract_set(contract_root) == []


def test_registry_replace_failure_rolls_back_new_file(
    contract_root: Path, candidate: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = read_registry(contract_root)

    def fail(*args: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("os.replace", fail)
    with pytest.raises(OSError, match="simulated"):
        _freeze(contract_root, candidate)
    assert read_registry(contract_root) == before
    assert not (contract_root / "result/test/1.1.0.json").exists()
    assert not list(contract_root.glob(".registry-*"))


def test_conflicting_destination_and_stale_registry_preserve_other_work(
    contract_root: Path,
    candidate: Path,
) -> None:
    from ss_track.schema.compatibility.publishing import publish

    target = contract_root / "result/test/1.1.0.json"
    target.write_bytes(b"another author's candidate")
    original = (contract_root / "registry.yaml").read_bytes()
    with pytest.raises(CorpusRefusal, match="different bytes"):
        _freeze(contract_root, candidate)
    assert target.read_bytes() == b"another author's candidate"
    assert (contract_root / "registry.yaml").read_bytes() == original
    target.unlink()
    with pytest.raises(CorpusRefusal, match="registry changed"):
        publish(
            contract_root,
            Path("result/test/1.1.0.json"),
            candidate.read_bytes(),
            original,
            b"stale",
        )
    assert not target.exists()
    assert (contract_root / "registry.yaml").read_bytes() == original


def test_freeze_preserves_registry_permissions(contract_root: Path, candidate: Path) -> None:
    registry = contract_root / "registry.yaml"
    registry.chmod(0o640)
    _freeze(contract_root, candidate)
    assert registry.stat().st_mode & 0o777 == 0o640
