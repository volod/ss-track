"""Shared fixtures for the unlinked-version listing tests."""

from pathlib import Path

from ss_track.corpus import ImportResult
from tests.corpus.conftest import place_of


def place(
    source: ImportResult,
    other: str,
    other_group: str,
    other_split: str,
    this: str,
    group: str,
    split: str,
) -> dict[str, object]:
    """Return one listing entry, `from` the other version and `to` the one being built."""
    return {
        "source_sha256": source.source_sha256,
        "from": place_of(other, other_group, other_split),
        "to": place_of(this, group, split),
    }


def plant(data_root: Path, corpus_id: str, text: str) -> Path:
    """Write one corpus manifest that no builder produced."""
    path = data_root / "corpus" / corpus_id / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")
    return path
