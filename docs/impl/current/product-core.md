# Product Core

The project distributes as `ss-track`, imports as `ss_track`, and installs the `ss-track` and
`ss-track-plan` commands. `pyproject.toml` carries the project description and the
[repository](https://github.com/volod/ss-track) URLs.

The `ss_track` package provides a typed `ProjectInfo` value through `project_info()`. It reports the
distribution name, import package, and installed version, with a source-checkout fallback when
distribution metadata is unavailable.

`src/ss_track/cli.py` owns argument parsing. The installed `ss-track info` command logs the same
identity, providing a packaging and executable-path smoke test. No benchmark behavior exists yet;
the [implementation plan](../plan.md) describes the scheduled work.

Run it with:

```bash
make run
```

`tests/test_metadata.py` and `tests/test_cli.py` cover the API and command boundary, and check that
`pyproject.toml` declares the same distribution, command, and package. `make build` creates source
and wheel distributions.
