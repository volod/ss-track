# Agent Python Project

A copy-ready Python project skeleton for teams that want coding agents to work from one set of
rules, one product specification, and one forward implementation plan.

The repository is usable before customization: it installs an `agent-py` command, includes a
small typed package, and ships tests plus documentation-integrity checks. Rename the distribution,
package, and product language when starting a real project; the planning and quality infrastructure
is designed to stay.

## Quick start

Requirements: Git, Make, and [uv](https://docs.astral.sh/uv/).

```bash
cp -R <skeleton-dir> <new-project-dir>
cd <new-project-dir>
git init
make bootstrap
make run
make ci
```

`make bootstrap` creates `.venv` from the committed lockfile. `make run` exercises the starter CLI.
`make ci` runs the same required checks as GitHub Actions.

## Customize the project

Make these edits as one initial change:

1. Change the name, description, authors, URLs, and script entry in `pyproject.toml`.
2. Rename `src/agent_py/` and update imports, the mypy path, and tests.
3. Replace the starter product identity in `src/agent_py/metadata.py`.
4. Rewrite the purpose, scope, boundaries, and success criteria in `docs/design/spec.md`.
5. Update the capability registry without deleting the lifecycle and integrity rules.
6. Replace the generic copyright line in `LICENSE` if your organization requires it.
7. Run `make lock` and `make quality`.

Do not put product work directly into the plan before the specification describes its capability
and evaluation. The workflow is explained in
[Planning workflow](docs/guide/planning-workflow.md).

## Daily commands

| Command | Purpose |
| --- | --- |
| `make help` | List supported workflows |
| `make bootstrap` | Create or update the locked development environment |
| `make run` | Run the starter CLI |
| `make test` | Run the unit test suite |
| `make coverage` | Run tests with the coverage gate |
| `make format` | Apply Ruff formatting |
| `make ci` | Run required local and CI checks |
| `make quality` | Run CI checks, coverage, Markdown lint, and package build |
| `make plan-status` | Count tasks and show the next agent and human work |
| `make lint-spec-plan` | Check the capability registry against the plan |
| `make lint-doc-links` | Check relative Markdown files and anchors |
| `make quality-report` | Report files over the soft size limit |

Use Make targets for repeatable workflows. Direct `uv` debugging should first source
`scripts/shared/common.sh` and run `apy_load_env` so cache and link behavior follows `.env`.

## Documentation model

```text
docs/design/spec.md        what the product must do and how each capability is evaluated
          |
          v
docs/impl/plan.md          only work that remains, ordered by capability
          |
          v
docs/impl/current.md       index of behavior that exists now
```

The specification is living, not a fixed scope fence. A newly discovered product need enters the
specification first, including its boundary and negative-result rule. It then receives a `planned`
registry row and plan tasks. When the capability lands, its implementation moves out of the plan
and into the narrowest current-state page, and the registry row becomes `shipped`.

## Agent support

`AGENTS.md` is the canonical policy. `CLAUDE.md`, `GEMINI.md`, `.codex`, and the Cursor rule are
thin adapters that point to it. Keeping substantive rules in one file prevents tool-specific drift.

## Layout

```text
src/agent_py/              production package
tests/                     unit and governance tests
docs/design/               product specification
docs/impl/plan.md          forward-only work
docs/impl/current/         delivered behavior
docs/guide/                contributor workflows
scripts/shared/            shared shell environment helpers
.github/workflows/         required CI
```

Runtime output belongs under `$DATA_DIR/<method>/<run-id>/`, which defaults to `.data/` and is
ignored by Git.

## License

MIT. See [LICENSE](LICENSE).
