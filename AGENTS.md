# AGENTS.md project rules

This file is the canonical instruction source for every coding agent in this repository. Tool-
specific files must link here and keep only integration-specific routing.

## Development guardrails

- **Git:** Do not commit, push, rewrite history, or revert user changes unless explicitly asked.
- **Scope:** Preserve unrelated work. Diagnose without changing code when the request is diagnostic.
- **Python:** Support Python 3.12 or newer. Use `uv`, `uv.lock`, and `pyproject.toml` for dependency
  management. Use Make targets for standard workflows. Before a direct `uv` command, source
  `scripts/shared/common.sh` and run `apy_load_env`.
- **Typing:** Keep production code fully typed. Do not add `from __future__ import annotations`.
- **Paths:** Never hardcode machine-specific absolute paths. Resolve from the project root and
  honor `.env` and `DATA_DIR`.
- **Secrets:** Never commit credentials or include them in logs, tests, fixtures, or documentation.
- **Dependencies:** Add the smallest justified dependency. Update `uv.lock` in the same change.

## Code organization

- Production Python lives under `src/agent_py/`; tests mirror it under `tests/`.
- `src/agent_py/cli.py` owns command parsing. Domain behavior belongs in focused modules, not in
  CLI handlers or top-level shell scripts.
- Prefer cohesive modules and functions with small interfaces. Reuse existing code and avoid
  parallel implementations of one rule.
- Aim to keep tracked Python and shell files at or below about 250 lines. Split only at a clear
  functional seam; cohesion is more important than the number.
- Use named constants instead of unexplained literals and `logging` instead of `print()` in
  production code.
- Runtime output belongs under `$DATA_DIR/<method>/<run-id>/`, never inside `src/`.
- Shared shell behavior belongs in `scripts/shared/common.sh`. Every tracked shell function must
  use the `apy_` prefix because sourced functions share one namespace.

## Tests and quality

- Add or update tests with every behavior change. A bug fix includes a failing regression case.
- Keep tests deterministic and network-free unless a task explicitly declares an external run.
- `make ci` is the required gate: format check, lint, typing, tests, complexity, shell lint,
  documentation links, and spec-plan integrity.
- `make quality` adds coverage, Markdown lint, and a package build. Fix findings at their source;
  do not weaken checks to fit new code.
- Use `make format` to apply formatting. Fix Markdown findings by hand.

## Documentation lifecycle

`docs/impl/plan.md` is FORWARD-ONLY: it contains only work that remains. Delivered behavior lives
under `docs/impl/current/`, indexed by `docs/impl/current.md`. Product behavior and boundaries live
in `docs/design/spec.md`.

After every product or developer-facing change, before reporting completion:

1. Record what exists in the narrowest current-state page: behavior, modules, commands, tests,
   verification, and result.
2. Remove the completed task from `docs/impl/plan.md`; retain only residual future work.
3. Route anything surfaced during implementation exactly once:
   - a chore: do it now when necessary, otherwise drop it;
   - an audit of the work just produced: perform it as part of completion, then drop it;
   - more work for a registered capability: add a future task, optional when it is a refinement;
   - a new product capability: use the lifecycle below before creating a task.
4. Update current-doc indexes when adding a page and run `make lint-doc-links`.
5. Compare plan task counts before and after and state which capabilities moved.

Do not put completion notes, dates, measurements, or history in the plan. A plan task may use one
line to link a prerequisite fact in current docs without restating it.

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
work that changes downstream inputs, required work before `(optional)`, and cheaper deterministic
work before expensive runs. A capability with only optional refinements may move below capabilities
with required work by reordering the registry once the product priority changes.

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
- optional tasks follow required tasks within their own group.

Fix document disagreements when `make lint-spec-plan` fails. Do not loosen the checker.

## Completion discipline

Before declaring work complete, run the relevant tests and `make ci`, update current docs, remove
finished plan scope, and inspect `git status`. Confirm that only intended files changed and that no
process, port, temporary scaffold, or external resource started by the work remains active. Runtime
artifacts under `DATA_DIR` are evidence, not temporary files; retain them unless the task explicitly
says otherwise.

Use ASCII in code, logs, comments, documentation, and generated output.
