# AGENTS.md project rules

This file is the canonical instruction source for every coding agent in this repository. Tool-
specific files must link here and keep only integration-specific routing.

## Development guardrails

- **Git:** Do not commit, push, rewrite history, or revert user changes unless explicitly asked.
- **Scope:** Preserve unrelated work. Diagnose without changing code when the request is diagnostic.
- **Python:** Support Python 3.12 or newer. Use `uv`, `uv.lock`, and `pyproject.toml` for dependency
  management. Use Make targets for standard workflows. Before a direct `uv` command, source
  `scripts/shared/common.sh` and run `sst_load_env`.
- **Typing:** Keep production code fully typed. Do not add `from __future__ import annotations`.
- **Paths:** Never hardcode machine-specific absolute paths. Resolve from the project root and
  honor `.env` and `DATA_DIR`.
- **Secrets:** Never commit credentials or include them in logs, tests, fixtures, or documentation.
- **Dependencies:** Add the smallest justified dependency. Update `uv.lock` in the same change.
- **Contracts:** A new interchangeable format adds its contract under `contracts/` in the same change.
  See the [authoring guide](docs/guide/authoring-contracts.md).

## Code organization

- Production Python lives under `src/ss_track/`; tests mirror it under `tests/`.
- `src/ss_track/cli.py` is the only module in the package root: the entry point and root parser.
  Each command group lives in `src/ss_track/commands/`, with `commands/report.py` for the one JSON
  record every command reports. Shared primitives live in `src/ss_track/core/`, and each area
  package groups its modules into subpackages by responsibility. Domain behavior belongs in focused
  modules, not in CLI handlers or top-level shell scripts.
- Prefer cohesive modules and functions with small interfaces. Reuse existing code and avoid
  parallel implementations of one rule.
- Aim to keep tracked Python and shell files at or below about 250 lines. Split only at a clear
  functional seam; cohesion is more important than the number.
- Use named constants instead of unexplained literals and `logging` instead of `print()` in
  production code.
- Runtime output belongs under `$DATA_DIR/<method>/<run-id>/`, never inside `src/`.
- Reproducible bytes a command leaves in the data root, such as staged frames, downloads, caches,
  scratch or host-specific environments, are removable only through a registered `ss-track data
  clean` kind with its restore path. A task that first writes a new kind registers it with the
  shared registry in `src/ss_track/core/clean_kinds.py` from its owning area, with a test, in the
  same change, and a plan task
  that will create one says so in its acceptance gates.
- Shared shell behavior belongs in `scripts/shared/common.sh`. Every tracked shell function must
  use the `sst_` prefix because sourced functions share one namespace.

## Tests and quality

- Add or update tests with every behavior change. A bug fix includes a failing regression case.
- Keep tests deterministic and network-free unless a task explicitly declares an external run.
- `make ci` is the required gate: format check, lint, typing, tests, complexity, shell lint,
  documentation links, spec-plan integrity, and frozen contracts.
- `make quality` adds coverage, Markdown lint, and a package build. Fix findings at their source;
  do not weaken checks to fit new code.
- Use `make format` to apply formatting. Fix Markdown findings by hand.

## Documentation lifecycle

`docs/impl/plan.md` is FORWARD-ONLY: it contains only work that remains. Delivered behavior lives
under `docs/impl/current/`, indexed by `docs/impl/current.md`. Product behavior and boundaries live
in `docs/design/spec.md`. What happened to a finished task lives in `docs/impl/records/`.

When starting a task from the plan, create its record first: copy `docs/impl/records/template.md`
using the [naming rules](docs/guide/planning-workflow.md#record-file-naming), add it to the records
index, and paste the task block verbatim. A plan task cannot leave the plan without a record, because
the record is the only place its text survives.

After every product or developer-facing change, before reporting completion:

1. Update the narrowest current-state page with available behavior, interfaces, module locations,
   and verification methods. Retain measured findings when they inform implementation decisions.
2. Close the task record with its implementation notes, acceptance evidence, audit handoff and plan
   counts, and link it from the current-state page. Set `accepted` only when every gate has passed.
3. Remove the completed task from `docs/impl/plan.md`; retain only residual future work.
4. Route everything surfaced during implementation exactly once, in the same change:
   - a chore: do it now when necessary, otherwise drop it;
   - an audit of the work just produced: perform it as part of completion, then drop it;
   - a bug or an improvement not fixed in this change: report it and add or amend a plan task that
     states it (see [Findings](#findings));
   - more work for a registered capability, including a gap, limitation, risk or follow-up: amend the
     open task that owns it so its text states the work, or add a future task, optional when it is a
     refinement;
   - a new product capability: use the lifecycle below before creating a task.
5. Update current-doc indexes when adding a page and run `make lint-doc-links`.

The specification is living, and improving the product is part of every task. When a deep dive
reveals a gap, a wrong boundary, a risk or a directly usable feature, amend the specification and add
plan tasks in the same change, without waiting to be asked. Writing a concrete task is never a
separate session.

A note in a task record is not routing. Every audit handoff entry and every limitation that affects a
result must reach an open task whose text states it, or be recorded as dropped with its reason.
"No plan task exists" is not a valid owner, and an owner task that does not mention the item loses it.

### Findings

A bug or an improvement is never dropped. When it is not fixed in the change that found it:

- Report it in the task record's audit handoff and in the completion report to the user.
- Give it a plan task with a proper description: the observed behavior and the expected one, a
  minimal reproduction or the evidence, its impact, the fix or the improvement to make, and
  acceptance gates that prove it. Amending an open task is enough only when that task's text then
  states all of this.
- A bug's task is required, never `(optional)`. An improvement's task is `(optional)` when it is a
  refinement.
- A bug in a third-party package is fixed here in the same change, because this project does not
  control third-party packages: a check, a wrapper or a patch around the faulty behavior, never a
  fork or vendored copy. Add a test that fails once the pinned release no longer shows the bug,
  with a message saying to remove the workaround. Such a bug is not reported upstream and gets no
  plan task.

Only a chore, an observation that needs no work, or a finding fixed in the same change, including a
third-party bug behind a workaround, may be dropped, each with its reason.

Keep current-state documentation focused on current contracts, constraints, rationale, and actionable
limitations. Do not retain task-count snapshots, migration narratives, completed audit logs, or
routine check results there; the task record holds them. Update existing descriptions in place
instead of appending completion history. A closed record is history and is not rewritten later.

Do not put completion notes, dates, measurements, history, or record links in the plan. A plan task
may use one line to link a prerequisite fact in current docs without restating it. Removing a task
also updates every task that depended on it: drop the dependency, or replace it when the dependent
still needs work that the removed task did not finish.

## Product capability lifecycle

The specification is living. It may grow when implementation reveals a real product need, but no
capability may reach `src/` or the plan without a specification section describing it.

For a new capability, in order:

1. State the operator or domain problem, not an internal artifact preference.
2. Amend the owning specification section and state what the capability does not do.
3. Declare the evaluation, acceptance signal, and valid negative result before implementation.
4. Add a `planned` row to the capability registry.
5. Add tasks under that capability in registry order, each with a `Serves` line.
6. Implement it, document it under current state, remove its tasks, and mark the row `shipped` with
   an implementation link.

If an existing capability is the wrong shape, amend its specification instead of working around it
in code.

## Task differentiation and ordering

The plan has two lanes:

- **Agent Implementation Tasks:** deterministic work an agent can finish independently. Use
  `CLEAR` or `RUN NEEDED`.
- **Human-Assisted Tasks:** acceptance requires human judgment, authorization, private access, or
  spending authority. Use `BLOCKED BY HUMAN` or `HUMAN-GATED`.

`RESEARCH` is an additional task marker, not an execution status. It means the implementation path
is unknown and a negative result is acceptable.

Order capability groups exactly as the registry. Within each group: hard dependencies first, then
work that changes downstream inputs, required work before `(optional)`, cheaper deterministic work
before expensive runs, and the group's audit last. A capability with only optional refinements may
move below capabilities with required work by reordering the registry once the product priority
changes.

Every capability group in the Agent lane ends with its audit, `<capability-id>-audit (optional)`, a
scheduled review of the whole group at `Effort: high`. A new task in that group goes above it. The
`(optional)` marker sets its order and does not make it skippable. The per-change audit in the
documentation lifecycle still runs at every completion. The
[group audit rules](docs/guide/planning-workflow.md#group-audits) state what it covers.

Every task must include: `Serves`, `Agent status`, `Dependencies`, `User-visible outcome`, `Scope
boundary`, `Data and artifact paths`, `Execution path`, `Acceptance gates`, and `Documentation
target`. `make lint-spec-plan` enforces this structure.

## Specification and plan integrity

The capability registry and implementation plan are two views of one product. Keep these invariants:

- every task serves a real capability and sits under that capability's group;
- every planned capability has open work;
- every shipped capability links to current-state documentation;
- every capability declares an evaluation;
- capability groups follow registry order in both plan lanes;
- optional tasks follow required tasks within their own group;
- every capability group in the Agent lane ends with its audit task.

Fix document disagreements when `make lint-spec-plan` fails. Do not loosen the checker.

## Completion discipline

Before declaring work complete, run the relevant tests and `make ci`, update current docs, close the
task record, remove finished plan scope, and inspect `git status`. Confirm that only intended files
changed and that no process, port, temporary scaffold, or external resource started by the work
remains active. Runtime artifacts under `DATA_DIR` are evidence, not temporary files; retain them
unless the task explicitly says otherwise.

Use ASCII in code, logs, comments, documentation, and generated output.
