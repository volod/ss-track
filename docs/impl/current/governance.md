# Governance

## One rules source

`AGENTS.md` carries the shared development, documentation, task, and completion rules. `CLAUDE.md`,
`GEMINI.md`, `.codex`, and `.cursor/rules/project-rules.mdc` are deliberately thin adapters. A rule
change therefore has one canonical edit.

## Product state transition

`docs/design/spec.md` owns capabilities, boundaries, evaluations, and registry order.
`docs/impl/plan.md` owns only work that remains and separates independent agent work from
human-gated acceptance. This current tree owns available behavior and durable results.

`src/agent_py/quality/plan_integrity.py` parses the registry and plan. It rejects unknown or
misfiled capabilities, missing task fields, status-lane mismatches, missing evaluations or current
links, out-of-order groups, required tasks after optional tasks, malformed ids, and historical plan
language. `agent-py-plan` and `make plan-status` reuse the same parsed model to report counts and
the next task in each lane.

The template plan starts with `personalize-template-project`, and the repository-level plan-summary
test ensures it remains the first agent task after a repository is created from the template.

`src/agent_py/quality/doc_links.py` checks repository documentation before a Git commit is required.
It validates relative file targets and generated heading anchors while ignoring fenced examples and
external URLs.

The failure cases and the repository-wide assertions live under `tests/quality/`. The operating
workflow and full task template live in
[Planning workflow](../../guide/planning-workflow.md).

Documentation category directories use singular names: `design/`, `guide/`, and `impl/`. Page names
remain specific to their content, and each category `README.md` file provides its local index.
