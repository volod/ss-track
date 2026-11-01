"""Runtime artifact locations, honoring `DATA_DIR` from the environment and `.env`."""

import os
from collections.abc import Mapping
from pathlib import Path

from ss_track.quality.project_root import discover_project_root

DATA_DIR_VARIABLE = "DATA_DIR"
DEFAULT_DATA_DIR = ".data"
_ENV_FILE = ".env"
_EXPORT_PREFIX = "export "


def _read_env_file(path: Path) -> str | None:
    """Return the last `DATA_DIR` assignment in a `.env` file, as sourcing it would."""
    if not path.is_file():
        return None
    found: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.strip().removeprefix(_EXPORT_PREFIX).partition("=")
        if separator and name.strip() == DATA_DIR_VARIABLE:
            found = value.strip().strip("\"'")
    return found


def _project_root(start: Path | None) -> Path | None:
    try:
        return discover_project_root(start)
    except FileNotFoundError:
        return None


def resolve_data_root(
    environment: Mapping[str, str] | None = None, start: Path | None = None
) -> Path:
    """Return `DATA_DIR` from the environment, then `.env`, then the project default."""
    values = os.environ if environment is None else environment
    project_root = _project_root(start)
    base = project_root or (start or Path.cwd()).resolve()
    configured = values.get(DATA_DIR_VARIABLE) or _read_env_file(base / _ENV_FILE)
    return base / (configured or DEFAULT_DATA_DIR)
