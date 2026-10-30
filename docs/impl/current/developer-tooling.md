# Developer Tooling

## Environment

`pyproject.toml` declares Python 3.12+ package metadata and a `dev` extra. `uv.lock` fixes the full
resolution. `make bootstrap` installs the locked environment; direct uv investigations use
`scripts/shared/common.sh` so `DATA_DIR`, caches, and adaptive link mode have one implementation.

## Quality gates

The Makefile exposes individual checks and two composed workflows:

- `make ci` runs formatting, linting, typing, Radon and cognitive complexity, shell parsing and
  ShellCheck, documentation links, spec-plan integrity, and deterministic tests.
- `make quality` adds branch coverage, Markdown lint, and source/wheel builds.

GitHub Actions runs `make ci-github`, an explicit alias of the same required gate, on Python 3.12
and 3.13 after `uv sync --locked --extra dev`.

Tests under `tests/quality/` exercise failure cases for the documentation checks rather than only
asserting the repository passes. `make quality-report` reports source and shell files over the
250-line soft limit.

## Artifact paths

`.env.example` declares `DATA_DIR=.data`. Relative values resolve against the project root. Runtime
results use `$DATA_DIR/<method>/<run-id>/`; Ruff, mypy, pytest, and complexipy caches stay below the
same root. `.gitignore` excludes runtime artifacts, local environments, secrets, caches, and root
build outputs without hiding same-named source subpackages.
