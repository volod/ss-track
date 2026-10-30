from pathlib import Path

from agent_py.quality.plan_model import read_registry, read_tasks
from tests.quality._plan_fixture import SPEC, plan_with, task_block, write_project


def test_registry_and_task_metadata_are_parsed(tmp_path: Path) -> None:
    root = write_project(tmp_path)

    registry = read_registry(root / "docs/design/spec.md")
    tasks = read_tasks(root / "docs/impl/plan.md")

    assert [capability.identifier for capability in registry] == ["foundation", "feature"]
    assert registry[0].status == "shipped"
    assert [(task.identifier, task.serves, task.agent_status) for task in tasks] == [
        ("build-feature", "feature", "CLEAR")
    ]


def test_fenced_task_examples_are_not_parsed(tmp_path: Path) -> None:
    plan = plan_with(task_block()) + "\n```markdown\n#### example-task\n```\n"
    root = write_project(tmp_path, plan=plan)

    assert [task.identifier for task in read_tasks(root / "docs/impl/plan.md")] == ["build-feature"]


def test_only_the_capability_registry_table_is_parsed(tmp_path: Path) -> None:
    spec = (
        SPEC
        + """

## Another table

| # | Capability | Status | How it is evaluated | Implementation |
| --- | --- | --- | --- | --- |
| 3 | `ignored` | planned | Other | - |
"""
    )
    root = write_project(tmp_path, spec=spec)

    assert [item.identifier for item in read_registry(root / "docs/design/spec.md")] == [
        "foundation",
        "feature",
    ]
