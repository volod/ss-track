# Developer Tooling

## Environment

`pyproject.toml` declares Python 3.12+ package metadata and a `dev` extra. `setuptools` is in that
extra so a test can build the wheel with no network. `uv.lock` fixes the full resolution.
`make bootstrap` installs the locked environment; direct uv investigations use
`scripts/shared/common.sh` so `DATA_DIR`, caches, and adaptive link mode have one implementation.

## Quality gates

The Makefile exposes individual checks and two composed workflows:

- `make ci` runs formatting, linting, typing, Radon and cognitive complexity, shell parsing and
  ShellCheck, documentation links, spec-plan integrity, [frozen contracts](contracts.md#the-gate), and
  the lightweight test group.
- `make quality` adds branch coverage over both test groups, Markdown lint, and source/wheel builds.

Tests are two groups, selected by the `external` marker in `tests/grouping.py`. `make test-light`
runs tests with no external artifact dependency: they do not copy or recheck the shipped contract
set, rebuild a Git history of that set, or start the optional sibling interpreter or Croissant
package. `make test-external` runs the tests that do. `make test` runs both groups. The contract
gate still runs once inside `make ci` as `make lint-contracts`. The tests that repeat that check on
a private copy, and the real sibling-release probes, belong to the external group. The
[task record](../records/0061-adhoc-lightweight-ci-tests.md) holds the measured boundary.

GitHub Actions runs `make ci-github`, an explicit alias of `make ci`, on Python 3.12 and 3.13 after
`uv sync --locked --extra dev`. It fetches full history for the contract evolution gate and passes
the pull-request base SHA or the push before SHA as `CONTRACT_BASE_REF`. Local `make lint-contracts`
defaults to `origin/main`; set `CONTRACT_BASE_REF=<ref>` for another review base. A missing ref or
shallow checkout fails instead of silently skipping immutability checks.

`.github/workflows/arm64-reproducibility.yml` runs on the same events. Its `x86-64` job writes the
fixed corpus sources once with `make fixed-corpus-sources`, stages them with
`make fixed-corpus-stage` and uploads both the sources and its hashes. Its `arm64` job, on
`ubuntu-24.04-arm`, refuses any other machine, runs `make test` (both groups), stages the same
sources, and runs `make fixed-corpus-compare`, which fails the job on any difference.
`hash-comparison.json` is uploaded
whatever the result. That job installs the locked environment without `shellcheck-py`, which has no
arm64 Linux wheel, because it runs no shell gate. `DATA_DIR` is `ci-data` there because an artifact
upload skips hidden paths such as `.data`. `tests/quality/test_workflows.py` pins the workflow's shape.
The [corpus page](corpus.md#across-hosts) states what the comparison means.

Tests under `tests/quality/` exercise failure cases for the documentation checks rather than only
asserting the repository passes. `make quality-report` reports source and shell files over the
250-line soft limit.

## Artifact paths

`.env.example` declares `DATA_DIR=.data` and documents the optional `ORG_ARTIFACTS_DIR`, which no
code reads. Relative values resolve against the project root. Runtime
results use `$DATA_DIR/<method>/<run-id>/`; Ruff, mypy, pytest, and complexipy caches stay below the
same root. `.gitignore` excludes runtime artifacts, local environments, secrets, caches, and root
build outputs without hiding same-named source subpackages.
