"""Wire and JSON compatibility of one event package against its frozen descriptor."""

import subprocess
import sys
from pathlib import Path

PROTO_ROOT = Path(__file__).resolve().parent / "proto"
BUF_CONFIG = PROTO_ROOT / "buf.yaml"
PACKAGES = ("analytics", "clock", "frame", "trial", "wire")
PACKAGE_IMPORTS = {
    "analytics": ("analytics.proto", "clock.proto", "contract_options.proto"),
    "clock": ("clock.proto", "contract_options.proto"),
    "frame": ("frame.proto", "contract_options.proto"),
    "trial": ("trial.proto", "clock.proto", "contract_options.proto"),
    "wire": ("wire.proto", "clock.proto", "contract_options.proto"),
}


def buf_executable() -> Path:
    """Return the buf binary installed with the dev extra."""
    path = Path(sys.executable).with_name("buf")
    if not path.is_file():
        raise FileNotFoundError(f"buf is not installed beside {sys.executable}")
    return path


def breaking_findings(candidate: Path, against: Path, config: Path | None = None) -> list[str]:
    """Return ``buf breaking`` failures of ``candidate`` against a frozen image.

    The configured category is ``WIRE_JSON``, so a renamed field, a reused field
    number and a changed ``json_name`` fail, and an added field does not.
    """
    module = candidate if candidate.is_dir() else candidate.parent
    return _command(
        module,
        "breaking",
        str(candidate),
        "--against",
        str(against),
        "--config",
        str(config or BUF_CONFIG),
        "--error-format",
        "text",
    )


def lint_findings(proto_root: Path | None = None) -> list[str]:
    """Return buf lint failures for the event sources."""
    root = proto_root or PROTO_ROOT
    return _command(root, "lint", "--config", str(root / "buf.yaml"))


def format_findings(proto_root: Path | None = None) -> list[str]:
    """Return buf format drift for the event sources."""
    root = proto_root or PROTO_ROOT
    return _command(root, "format", "--diff", "--exit-code")


def _command(cwd: Path, *arguments: str) -> list[str]:
    try:
        buf = buf_executable()
    except FileNotFoundError as error:
        return [str(error)]
    completed = subprocess.run(
        [str(buf), *arguments, "--log-format", "text"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return []
    text = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    return text.splitlines() or [f"buf {' '.join(arguments[:1])} exited {completed.returncode}"]
