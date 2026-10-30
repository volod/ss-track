"""Summarize the forward plan and identify the next work in each lane."""

import argparse
import logging
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from agent_py.quality.plan_integrity import PLAN_DOC, SPEC_DOC, integrity_findings
from agent_py.quality.plan_model import (
    AGENT_SECTION,
    HUMAN_SECTION,
    Task,
    read_registry,
    read_tasks,
)
from agent_py.quality.project_root import discover_project_root

_LOG = logging.getLogger(__name__)


def _next_task(tasks: list[Task], section: str, capability_order: dict[str, int]) -> Task | None:
    eligible = [task for task in tasks if task.section == section]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda task: (
            capability_order.get(task.group, len(capability_order)),
            task.optional,
            tasks.index(task),
        ),
    )


def summary_lines(project_root: Path) -> list[str]:
    """Render a compact status summary after validating the plan."""
    findings = integrity_findings(project_root)
    if findings:
        return ["plan is invalid; run make lint-spec-plan"]

    capabilities = read_registry(project_root / SPEC_DOC)
    tasks = read_tasks(project_root / PLAN_DOC)
    capability_order = {
        capability.identifier: number for number, capability in enumerate(capabilities)
    }
    status_counts = Counter(task.agent_status for task in tasks)
    lines = [
        f"tasks: {len(tasks)}",
        f"agent lane: {sum(task.section == AGENT_SECTION for task in tasks)}",
        f"human lane: {sum(task.section == HUMAN_SECTION for task in tasks)}",
    ]
    if status_counts:
        rendered = ", ".join(
            f"{status}={count}" for status, count in sorted(status_counts.items()) if status
        )
        lines.append(f"statuses: {rendered}")
    for label, section in (("next agent", AGENT_SECTION), ("next human", HUMAN_SECTION)):
        task = _next_task(tasks, section, capability_order)
        if task is None:
            lines.append(f"{label}: none")
        else:
            optional = " (optional)" if task.optional else ""
            lines.append(f"{label}: {task.identifier}{optional} [{task.group}]")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    """Print plan status for maintainers and agents."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="summarize the forward implementation plan")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.root.resolve() if args.root else discover_project_root()
    findings = integrity_findings(root)
    for line in summary_lines(root):
        _LOG.info("%s", line)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
