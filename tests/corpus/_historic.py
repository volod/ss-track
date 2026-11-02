"""Real sealed records, each written by the code of the commit in its name."""

from pathlib import Path

RECORDS = Path(__file__).parent / "records"


def kept_record(name: str) -> bytes:
    """Return one kept record's exact bytes."""
    return (RECORDS / name).read_bytes()


def place_record(name: str, path: Path) -> Path:
    """Put a kept record where a data root would hold it, byte for byte."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(kept_record(name))
    return path
