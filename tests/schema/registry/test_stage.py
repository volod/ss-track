"""Spec section 17.7: one in-place `1.0.0` per contract before release, immutable versions after it."""

import json
import subprocess
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.freeze import freeze_contract
from ss_track.schema.compatibility.history import history_findings
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.contract import DEVELOPMENT, RELEASED
from ss_track.schema.registry.stage import stage_of
from ss_track.schema.registry.store import load_contract_set
from tests.schema.conftest import (
    frame_set_path,
    read_registry,
    release,
    version_entry,
    write_registry,
)


def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _commit(project: Path, message: str) -> None:
    git(project, "add", "contracts")
    git(project, "commit", "-q", "-m", message)


@pytest.fixture
def repository(development_root: Path) -> Path:
    project = development_root.parent
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "user.name", "Contract Test")
    git(project, "config", "user.email", "contract-test@example.invalid")
    _commit(project, "Development contracts")
    git(project, "switch", "-q", "-c", "candidate")
    return project


def _edit_in_place(root: Path) -> Path:
    path = frame_set_path(root)
    schema = json.loads(path.read_bytes()) | {"title": "Edited in place"}
    path.write_text(json.dumps(schema, indent=2) + "\n")
    return path


def _repin(root: Path, path: Path) -> None:
    registry = read_registry(root)
    contract = next(item for item in registry["contracts"] if item["id"] == "frame-set")
    contract["versions"] = [version_entry(path)]
    write_registry(root, registry)


def test_the_shipped_set_is_in_the_development_stage() -> None:
    contracts = load_contract_set()
    assert contracts.stage == DEVELOPMENT
    assert all(
        [frozen.version for frozen in contract.versions] == ["1.0.0"]
        for contract in contracts.contracts
    )


def test_an_edit_in_place_passes_only_with_its_re_pin(development_root: Path) -> None:
    path = _edit_in_place(development_root)
    assert any("frozen file was edited" in item for item in check_contract_set(development_root))

    _repin(development_root, path)

    assert check_contract_set(development_root) == []


def test_a_second_version_is_refused_in_development(development_root: Path) -> None:
    directory = development_root / "record" / "frame-set"
    schema = json.loads((directory / "1.0.0.json").read_bytes())
    schema["$id"] = schema["$id"].replace(":1.0.0", ":1.0.1")
    path = directory / "1.0.1.json"
    path.write_text(json.dumps(schema))
    registry = read_registry(development_root)
    contract = next(item for item in registry["contracts"] if item["id"] == "frame-set")
    contract["versions"].append(version_entry(path, change={"class": "patch", "summary": "x"}))
    write_registry(development_root, registry)

    findings = check_contract_set(development_root)

    assert any("holds one version, 1.0.0; found 1.0.0, 1.0.1" in item for item in findings)
    assert any("change class is initial" in item for item in findings)


def test_freeze_re_pins_the_one_version_in_place(development_root: Path, tmp_path: Path) -> None:
    candidate = tmp_path / "frame-set.json"
    schema = json.loads(frame_set_path(development_root).read_bytes()) | {"title": "Re-pinned"}
    candidate.write_text(json.dumps(schema, indent=2) + "\n")

    result = freeze_contract("record/frame-set", candidate, root=development_root, summary="Edit.")

    assert result.status == "frozen"
    assert frame_set_path(development_root).read_bytes() == candidate.read_bytes()
    assert check_contract_set(development_root) == []
    frozen = load_contract_set(development_root).named("record/frame-set").versions
    assert [(item.version, dict(item.change)) for item in frozen] == [
        ("1.0.0", {"class": "initial", "summary": "Edit."})
    ]


def test_freeze_refuses_any_other_version_in_development(
    development_root: Path, tmp_path: Path
) -> None:
    candidate = tmp_path / "frame-set.json"
    schema = json.loads(frame_set_path(development_root).read_bytes())
    schema["$id"] = schema["$id"].replace(":1.0.0", ":1.1.0")
    candidate.write_text(json.dumps(schema))
    before = (development_root / "registry.yaml").read_bytes()

    with pytest.raises(CorpusRefusal, match=r"holds one version, 1\.0\.0"):
        freeze_contract("record/frame-set", candidate, root=development_root, summary="Edit.")

    assert (development_root / "registry.yaml").read_bytes() == before
    assert not (development_root / "record" / "frame-set" / "1.1.0.json").exists()


def test_history_accepts_a_development_edit_in_place(repository: Path) -> None:
    root = repository / "contracts"
    _repin(root, _edit_in_place(root))
    _commit(repository, "Edit in place")

    assert history_findings(repository, "main") == []


def test_history_compares_a_released_revision_and_refuses_a_return(repository: Path) -> None:
    root = repository / "contracts"
    release(root)
    _commit(repository, "Release")
    assert history_findings(repository, "main") == []
    git(repository, "switch", "-q", "-c", "after-release")
    git(repository, "branch", "-q", "-f", "main", "candidate")

    _repin(root, _edit_in_place(root))
    edited = history_findings(repository, "main")
    assert any("frozen file changed" in item for item in edited)

    git(repository, "checkout", "-q", "--", "contracts")
    registry = read_registry(root)
    registry["stage"] = DEVELOPMENT
    write_registry(root, registry)
    returned = history_findings(repository, "main")
    assert any("cannot return to development" in item for item in returned)


def test_a_registry_written_before_stages_reads_as_development(development_root: Path) -> None:
    registry = read_registry(development_root)
    assert stage_of(development_root) == DEVELOPMENT
    registry.pop("stage")
    write_registry(development_root, registry)
    assert stage_of(development_root) == DEVELOPMENT
    registry["stage"] = RELEASED
    write_registry(development_root, registry)
    assert stage_of(development_root) == RELEASED
