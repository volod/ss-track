# Development Guide

## Setup

Install Git, Make, and uv, then run:

```bash
make bootstrap
make doctor
make run
```

The lockfile is committed. After changing dependencies in `pyproject.toml`, run `make lock` and
include the resulting `uv.lock` change.

## Quality workflows

`make ci` is the required fast gate and is the command GitHub Actions runs on Python 3.12 and 3.13.
It checks formatting, Ruff rules, mypy, complexity, shell scripts, documentation links, specification
and plan integrity, and tests.

`make quality` adds branch coverage, Markdown style, and source/wheel builds. Run it before release
or after changing project infrastructure. `make quality-report` reports files over the 250-line soft
limit without turning cohesion into a numeric failure.

## Direct uv commands

Make targets are the stable workflow. For one-off dependency debugging:

```bash
source scripts/shared/common.sh
apy_load_env
uv <command>
```

This resolves `DATA_DIR`, moves supported tool caches with it, and avoids cross-filesystem link
warnings.

## Runtime artifacts

Write generated data under `$DATA_DIR/<method>/<run-id>/`. Use a stable method name and a unique run
id. Keep fixtures under `tests/` only when they are small, deterministic, safe to publish, and
required for CI.
