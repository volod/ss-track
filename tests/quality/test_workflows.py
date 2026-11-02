"""The arm64 job is what keeps a cross-architecture claim true, so its shape is checked here."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / ".github" / "workflows" / "arm64-reproducibility.yml"
_MAKE_TARGET = re.compile(r"\bmake ([a-z0-9-]+)")


@pytest.fixture(scope="module")
def jobs() -> dict[str, Any]:
    workflow: dict[str, Any] = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]


def _commands(job: dict[str, Any]) -> list[str]:
    return [step["run"] for step in job["steps"] if "run" in step]


def _position(commands: list[str], fragment: str) -> int:
    return next(index for index, command in enumerate(commands) if fragment in command)


def test_one_job_runs_on_each_architecture(jobs: dict[str, Any]) -> None:
    assert jobs["x86-64"]["runs-on"] == "ubuntu-24.04"
    assert jobs["arm64"]["runs-on"] == "ubuntu-24.04-arm"


def test_arm64_refuses_a_runner_that_is_not_arm64_before_anything_else_counts(
    jobs: dict[str, Any],
) -> None:
    commands = _commands(jobs["arm64"])

    assert _position(commands, "uname -m") < _position(commands, "fixed-corpus-stage")
    assert any('test "$(uname -m)" = aarch64' in command for command in commands)


def test_arm64_runs_the_golden_tests_and_compares_the_two_hosts(jobs: dict[str, Any]) -> None:
    commands = _commands(jobs["arm64"])

    assert "make test" in commands
    assert _position(commands, "fixed-corpus-stage") < _position(commands, "fixed-corpus-compare")


def test_only_x86_64_writes_sources_so_both_hosts_read_the_same_bytes(
    jobs: dict[str, Any],
) -> None:
    assert any("fixed-corpus-sources" in command for command in _commands(jobs["x86-64"]))
    assert not any("fixed-corpus-sources" in command for command in _commands(jobs["arm64"]))
    assert jobs["arm64"]["needs"] == "x86-64"


def test_a_failed_comparison_still_keeps_its_record(jobs: dict[str, Any]) -> None:
    kept = next(step for step in jobs["arm64"]["steps"] if step.get("if") == "always()")

    assert "hash-comparison.json" in kept["with"]["path"]


def test_every_make_target_the_workflow_calls_exists(jobs: dict[str, Any]) -> None:
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    commands = [command for job in jobs.values() for command in _commands(job)]
    targets = {name for command in commands for name in _MAKE_TARGET.findall(command)}

    assert targets
    assert all(re.search(rf"^{name}:", makefile, re.MULTILINE) for name in targets)
