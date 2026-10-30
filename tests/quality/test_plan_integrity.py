from pathlib import Path

import pytest

from agent_py.quality.plan_integrity import integrity_findings, main
from tests.quality._plan_fixture import SPEC, plan_with, task_block, write_project

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_repository_specification_and_plan_agree() -> None:
    assert integrity_findings(PROJECT_ROOT) == []


def test_a_healthy_planned_capability_and_task_agree(tmp_path: Path) -> None:
    assert integrity_findings(write_project(tmp_path)) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("- Serves: `feature`", "- Serves: `unknown`", "unregistered capability"),
        ("- Agent status: CLEAR", "- Agent status:", "Agent Status"),
        ("- Acceptance gates:", "- Other gates:", "Acceptance Gates"),
    ],
)
def test_invalid_task_metadata_is_named(
    tmp_path: Path,
    old: str,
    new: str,
    expected: str,
) -> None:
    plan = plan_with(task_block()).replace(old, new)

    findings = integrity_findings(write_project(tmp_path, plan=plan))

    assert any(expected in finding for finding in findings)


def test_human_status_in_the_agent_lane_is_rejected(tmp_path: Path) -> None:
    plan = plan_with(task_block(status="HUMAN-GATED"))

    findings = integrity_findings(write_project(tmp_path, plan=plan))

    assert any("invalid in 'Agent Implementation Tasks'" in finding for finding in findings)


def test_clear_status_in_the_human_lane_is_rejected(tmp_path: Path) -> None:
    human = task_block(identifier="review-feature", status="CLEAR")
    plan = plan_with(human_blocks=(human,))

    findings = integrity_findings(write_project(tmp_path, plan=plan))

    assert any("invalid in 'Human-Assisted Tasks'" in finding for finding in findings)


def test_required_work_cannot_follow_optional_work(tmp_path: Path) -> None:
    optional = task_block(identifier="nice-to-have", optional=True)
    required = task_block(identifier="required-work")
    plan = plan_with(optional, required)

    findings = integrity_findings(write_project(tmp_path, plan=plan))

    assert any("follows optional work" in finding for finding in findings)


def test_planned_capability_requires_a_task(tmp_path: Path) -> None:
    plan = plan_with()

    findings = integrity_findings(write_project(tmp_path, plan=plan))

    assert any("planned but no forward task" in finding for finding in findings)


def test_shipped_capability_requires_a_current_link(tmp_path: Path) -> None:
    spec = SPEC.replace("[Foundation](../impl/current.md)", "none")

    findings = integrity_findings(write_project(tmp_path, spec=spec))

    assert any("no current-documentation link" in finding for finding in findings)


def test_forward_plan_rejects_history_and_dates(tmp_path: Path) -> None:
    plan = plan_with(task_block()).replace(
        "Describe future product behavior.",
        "DONE on 2026-01-01.",
    )

    findings = integrity_findings(write_project(tmp_path, plan=plan))

    assert any("history or a date" in finding for finding in findings)


def test_malformed_task_heading_is_reported(tmp_path: Path) -> None:
    plan = plan_with(task_block()).replace("#### build-feature", "#### Build feature")

    findings = integrity_findings(write_project(tmp_path, plan=plan))

    assert any("malformed task heading" in finding for finding in findings)


def test_missing_documents_are_reported(tmp_path: Path) -> None:
    assert integrity_findings(tmp_path) == [
        "missing required document: docs/design/spec.md",
        "missing required document: docs/impl/plan.md",
    ]


def test_main_returns_failure_for_invalid_documents(tmp_path: Path) -> None:
    write_project(tmp_path, plan=plan_with())

    assert main(["--root", str(tmp_path)]) == 1
