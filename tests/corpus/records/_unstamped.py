"""A sealed record placed where no ss-track command wrote it, as older code or a copy would leave."""

from pathlib import Path

from tests.schema.conftest import KEPT_FRAME_SET


def place_record(path: Path) -> Path:
    """Write a real sealed record at `path`, creating its folder, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(KEPT_FRAME_SET.read_bytes())
    return path
