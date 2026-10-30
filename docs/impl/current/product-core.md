# Product Core

The initial `agent_py` package provides a typed `ProjectInfo` value through `project_info()`. It
reports the distribution name, import package, and installed version, with a source-checkout
fallback when distribution metadata is unavailable.

`src/agent_py/cli.py` owns argument parsing. The installed `agent-py info` command logs the same
identity, providing a packaging and executable-path smoke test without choosing a business-domain
framework.

Run it with:

```bash
make run
```

`tests/test_metadata.py` and `tests/test_cli.py` cover the API and command boundary. `make build`
creates source and wheel distributions.
