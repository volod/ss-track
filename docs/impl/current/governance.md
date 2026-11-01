# Governance

## One rules source

`AGENTS.md` carries the shared development, documentation, task, and completion rules. `CLAUDE.md`,
`GEMINI.md`, `.codex`, and `.cursor/rules/project-rules.mdc` are deliberately thin adapters. A rule
change therefore has one canonical edit.

## Product state transition

`docs/design/spec.md` owns capabilities, boundaries, evaluations, and registry order.
`docs/impl/plan.md` owns only work that remains and separates independent agent work from
human-gated acceptance. This current tree owns available behavior and durable results.
`docs/impl/records/` keeps each started task's verbatim text, implementation notes and acceptance
evidence after it leaves the plan. Current-state pages link records; the plan never does. A record
schedules nothing: each follow-up reaches the specification and the text of an open task in the same
change, or the record says why it was dropped.

`src/ss_track/quality/plan_integrity.py` parses the registry and plan. It rejects unknown or
misfiled capabilities, missing task fields, status-lane mismatches, missing evaluations or current
links, out-of-order groups, required tasks after optional tasks, malformed ids, and historical plan
language. `ss-track-plan` and `make plan-status` reuse the same parsed model to report counts and
the first task by priority in each lane. The current parser reads only the first line of each field;
it does not evaluate dependency readiness. Read the full task dependencies before starting work.

A repository-level plan-summary test verifies that the checked-in plan renders a valid summary.

`src/ss_track/quality/doc_links.py` checks repository documentation before a Git commit is required.
It validates relative file targets and generated heading anchors while ignoring fenced examples and
external URLs.

The failure cases and the repository-wide assertions live under `tests/quality/`. The operating
workflow and full task template live in
[Planning workflow](../../guide/planning-workflow.md).

Documentation category directories use singular names: `design/`, `guide/`, and `impl/`. Page names
remain specific to their content, and each category `README.md` file provides its local index.
