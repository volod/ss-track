"""Real sealed records, each written by the code of the commit in its name."""

import re
from pathlib import Path

from ss_track.corpus.records.kinds import (
    CORPUS_MANIFEST,
    FRAME_BUNDLE,
    FRAME_SET,
    HASH_COMPARISON,
    SOURCE_MANIFEST,
    STAGED_HASHES,
    RecordFormat,
)

RECORDS = Path(__file__).parent / "kept_records"


def kept_record(name: str) -> bytes:
    """Return one kept record's exact bytes."""
    return (RECORDS / name).read_bytes()


def place_record(name: str, path: Path) -> Path:
    """Put a kept record where a data root would hold it, byte for byte."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(kept_record(name))
    return path


KEPT_NAME = re.compile(r"(?P<format>[a-z-]+)-schema-(?P<major>\d+)-(?P<commit>[0-9a-f]{7})\.json")
KEPT_FORMATS = {
    "bundle": FRAME_BUNDLE,
    "corpus": CORPUS_MANIFEST,
    "frame-set": FRAME_SET,
    "hash-comparison": HASH_COMPARISON,
    "source": SOURCE_MANIFEST,
    "staged-hashes": STAGED_HASHES,
}
KEPT_NAMES = sorted(path.name for path in RECORDS.glob("*.json"))


def major_of(name: str) -> int:
    match = KEPT_NAME.fullmatch(name)
    assert match is not None
    return int(match["major"])


def format_of(name: str) -> RecordFormat:
    match = KEPT_NAME.fullmatch(name)
    assert match is not None
    return KEPT_FORMATS[match["format"]]
