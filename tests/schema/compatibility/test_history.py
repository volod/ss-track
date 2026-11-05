"""Real isolated Git histories expose edited-and-repinned contracts and missing baselines."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ss_track.schema.compatibility.history import history_findings
from ss_track.schema.registry.check import check_contract_set
from tests.schema.conftest import frame_set_path, read_registry, version_entry, write_registry


def git(project: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def repository(contract_root: Path) -> Path:
    project = contract_root.parent
    git(project, "init", "-b", "main")
    git(project, "config", "user.name", "Contract Test")
    git(project, "config", "user.email", "contract-test@example.invalid")
    git(project, "add", "contracts")
    git(project, "commit", "-m", "Baseline contracts")
    return project


def test_unchanged_history_passes(repository: Path) -> None:
    assert history_findings(repository, "main") == []


@pytest.mark.parametrize("committed", [False, True])
def test_edited_file_and_updated_pins_fail_against_merge_base(
    repository: Path, committed: bool
) -> None:
    git(repository, "switch", "-c", "candidate")
    root = repository / "contracts"
    path = frame_set_path(root)
    schema = json.loads(path.read_bytes()) | {"title": "Edited after freezing"}
    path.write_text(json.dumps(schema))
    registry = read_registry(root)
    contract = next(item for item in registry["contracts"] if item["id"] == "frame-set")
    contract["versions"] = [version_entry(path)]
    write_registry(root, registry)
    assert check_contract_set(root) == []
    if committed:
        git(repository, "add", "contracts")
        git(repository, "commit", "-m", "Repinned frozen bytes")
    findings = history_findings(repository, "main")
    assert any("frozen file changed" in finding for finding in findings)
    assert any("frozen registry entry changed" in finding for finding in findings)


def test_deleted_contract_and_log_rewrite_fail(repository: Path) -> None:
    root = repository / "contracts"
    registry = read_registry(root)
    registry["contracts"] = [item for item in registry["contracts"] if item["id"] != "frame-set"]
    write_registry(root, registry)
    shutil.rmtree(root / "record/frame-set")
    assert any("changed or removed" in finding for finding in history_findings(repository, "main"))


def test_missing_reference_and_shallow_history_fail_closed(
    repository: Path, tmp_path: Path
) -> None:
    assert any(
        "cannot check contract history" in x for x in history_findings(repository, "missing")
    )
    clone = tmp_path / "shallow"
    git(tmp_path, "clone", "--depth=1", repository.as_uri(), str(clone))
    assert any("full checkout" in x for x in history_findings(clone, "main"))


def test_manually_registered_wrong_bump_fails(repository: Path) -> None:
    root = repository / "contracts"
    source = frame_set_path(root)
    schema = json.loads(source.read_bytes())
    schema["$id"] = schema["$id"].replace("1.0.0", "1.0.1")
    schema["properties"]["added"] = {"type": "string", "description": "Optional."}
    path = source.with_name("1.0.1.json")
    path.write_text(json.dumps(schema))
    registry = read_registry(root)
    contract = next(item for item in registry["contracts"] if item["id"] == "frame-set")
    contract["versions"].append(
        version_entry(path, change={"class": "patch", "summary": "Wrong bump."})
    )
    write_registry(root, registry)
    assert check_contract_set(root) == []
    assert any("requires minor" in x for x in history_findings(repository, "main"))


def test_ci_has_history_and_explicit_event_baseline() -> None:
    import yaml

    from tests.schema.conftest import PROJECT_ROOT

    workflow = yaml.safe_load((PROJECT_ROOT / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["quality"]["steps"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"]["fetch-depth"] == 0
    check = next(step for step in steps if "ci-github" in step.get("run", ""))
    assert "github.event.pull_request.base.sha" in check["env"]["CONTRACT_BASE_REF"]
    assert "github.event.before" in check["env"]["CONTRACT_BASE_REF"]
