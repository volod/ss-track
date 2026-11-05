# Product Core

The project distributes as `ss-track`, imports as `ss_track`, and installs the `ss-track` and
`ss-track-plan` commands. `pyproject.toml` carries the project description and the
[repository](https://github.com/volod/ss-track) URLs.

The `ss_track` package provides a typed `ProjectInfo` value through `project_info()`. It reports the
distribution name, import package, and installed version, with a source-checkout fallback when
distribution metadata is unavailable.

`src/ss_track/cli.py` is the entry point: it builds the root parser and composes the command groups
in `src/ss_track/commands/`, `corpus.py` for `import` and `corpus` and `contracts.py` for
`contracts`. `commands/report.py` turns each result or refusal into one JSON log record and the exit
status (`EXIT_OK` or `EXIT_REFUSED`). `src/ss_track/core/` holds what every package shares:
canonical bytes and seals (`canonical.py`), refusals (`refusal.py`), strict JSON and YAML parsing,
the data root (`paths.py`) and the project identity (`metadata.py`). The installed `ss-track info`
command logs the same identity, providing a packaging and executable-path smoke test. `ss-track
import` and `ss-track corpus build`, `stage`, `verify`, `describe`, `hashes`, `compare` and
`preview` are described under [Corpus](corpus.md), and `ss-track contracts list`, `validate`,
`diff` and `freeze` under [Contracts](contracts.md). No run, evaluation or report behavior
exists yet; the [implementation plan](../plan.md) describes the scheduled work.

Run it with:

```bash
make run
```

`tests/core/test_metadata.py` and `tests/test_cli.py` cover the API and command boundary, and check that
`pyproject.toml` declares the same distribution, command, and package. `make build` creates source
and wheel distributions, and the wheel carries the contract set.

Three modules sit below every domain package, so that none has to import another to reach them:
`ss_track.core.refusal` holds the stable refusal codes, `ss_track.core.canonical` the byte form
every hash and seal covers, and `ss_track.core.strict_yaml` the loader that refuses a repeated key.
