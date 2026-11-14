"""Test workflow selects an installed sibling only when the operator has not chosen one."""

import os
import subprocess
from pathlib import Path

COMMON = Path(__file__).resolve().parents[2] / "scripts/shared/common.sh"


def _test_env(root: Path, explicit: str | None = None) -> str:
    environ = os.environ.copy()
    for name in ("SST_PERCEPTION_PYTHON", "DATA_DIR", "PROJECT_ROOT", "UV_LINK_MODE"):
        environ.pop(name, None)
    environ["PROJECT_ROOT"] = str(root)
    environ["DATA_DIR"] = "local-data"
    if explicit is not None:
        environ["SST_PERCEPTION_PYTHON"] = explicit
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; sst_load_test_env; printf "%s" "${SST_PERCEPTION_PYTHON:-}"',
            "bash",
            str(COMMON),
        ],
        env=environ,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def test_uses_cached_interpreter_without_overriding_operator(tmp_path: Path) -> None:
    python = tmp_path / "local-data/cache/ss-perception-probes/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="ascii")
    python.chmod(0o755)
    assert _test_env(tmp_path) == str(python)
    assert _test_env(tmp_path, "chosen-python") == "chosen-python"
    python.unlink()
    assert _test_env(tmp_path) == ""
