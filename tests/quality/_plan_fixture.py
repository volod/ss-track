from pathlib import Path

SPEC = """# Design

## Capability Registry

| # | Capability | Status | How it is evaluated | Implementation |
| --- | --- | --- | --- | --- |
| 1 | `foundation` | shipped | Fresh setup passes | [Foundation](../impl/current.md) |
| 2 | `feature` | planned | Fixture behavior passes | - |
"""


def task_block(
    identifier: str = "build-feature",
    *,
    capability: str = "feature",
    status: str = "CLEAR",
    optional: bool = False,
    effort: str | None = None,
) -> str:
    suffix = " (optional)" if optional else ""
    effort_field = f"- Effort: {effort}\n" if effort else ""
    return f"""#### {identifier}{suffix}

Describe future product behavior.

- Serves: `{capability}` -- [Feature](../design/spec.md#feature)
- Agent status: {status}
{effort_field}- Dependencies: none.
- User-visible outcome: A user can exercise the feature.
- Scope boundary: The fixture path only; deployment is outside scope.
- Data and artifact paths: `tests/fixtures/` only.
- Execution path: Add a module and deterministic tests.
- Acceptance gates: `make ci` passes or the negative result is recorded.
- Documentation target: [Current state](current.md).
"""


def audit_block(capability: str = "feature") -> str:
    return task_block(f"{capability}-audit", capability=capability, optional=True, effort="high")


def plan_with(*blocks: str, human_blocks: tuple[str, ...] = (), audit: bool = True) -> str:
    """Return a plan whose agent group ends with its audit unless a test removes it."""
    closed = (*blocks, audit_block()) if blocks and audit else blocks
    agent_content = "\n".join(closed) if closed else "No open agent tasks."
    human_content = "\n".join(human_blocks) if human_blocks else "No open human tasks."
    return f"""# Plan

## Agent Implementation Tasks

### Feature -- `feature`

{agent_content}

## Human-Assisted Tasks

### Feature -- `feature`

{human_content}
"""


def write_project(root: Path, *, spec: str = SPEC, plan: str | None = None) -> Path:
    (root / "docs/design").mkdir(parents=True)
    (root / "docs/impl").mkdir(parents=True)
    (root / "docs/design/spec.md").write_text(spec, encoding="utf-8")
    resolved_plan = plan if plan is not None else plan_with(task_block())
    (root / "docs/impl/plan.md").write_text(resolved_plan, encoding="utf-8")
    return root
