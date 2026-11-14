"""Read the imported source records that a corpus version builds on and pins.

A corpus states the rights its sources had when it was built, so every use re-reads the record
and refuses one that changed, and a build or a decode also checks the stored bytes again.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.kinds import SOURCE_MANIFEST
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.sources.identity import require_stored_source
from ss_track.corpus.sources.terms import changed_terms
from ss_track.corpus.storage.layout import MANIFEST_NAME, replaced_record_path, source_directory


@dataclass(frozen=True, slots=True)
class VerifiedSource:
    """A source record whose stored bytes were hashed again just now, and where they are."""

    record: dict[str, JsonValue]
    stored: Path

    @property
    def sequence(self) -> dict[str, Any]:
        """Return what the import's decode established."""
        return source_sequence(self.record)


def load_source_record(source_sha256: str, data_root: Path) -> dict[str, JsonValue]:
    """Read one imported source's record, refusing a source that was never imported."""
    manifest_path = source_directory(data_root, source_sha256) / MANIFEST_NAME
    if not manifest_path.is_file():
        raise CorpusRefusal(
            RefusalCode.SOURCE_NOT_IMPORTED,
            "the corpus names a source that has not been imported",
            {"source_sha256": source_sha256},
        )
    return read_sealed(manifest_path, SOURCE_MANIFEST)


def source_sequence(record: Mapping[str, JsonValue]) -> dict[str, Any]:
    """Return a source record's `sequence`, refusing a record that holds none."""
    sequence = record.get("sequence")
    if not isinstance(sequence, dict):
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "source record has no sequence section",
            {"record": MANIFEST_NAME},
        )
    return sequence


def require_source_record(stream: Mapping[str, Any], data_root: Path) -> None:
    """Refuse a stream whose source was re-imported, because the corpus states its old rights."""
    manifest = load_source_record(stream["source_sha256"], data_root)
    if manifest[SEAL_FIELD] != stream["source_manifest_sha256"]:
        raise CorpusRefusal(
            RefusalCode.SOURCE_RECORD_CHANGED,
            "this source's record changed after the corpus was built; build a new corpus version",
            {
                "stream_id": stream["stream_id"],
                "source_sha256": stream["source_sha256"],
                "corpus_source_manifest_sha256": stream["source_manifest_sha256"],
                "source_manifest_sha256": manifest[SEAL_FIELD],
                "changed_terms": list(changed_terms(stream, manifest)),
            },
        )


def load_verified_source(source_sha256: str, data_root: Path) -> VerifiedSource:
    """Load a source record only if both the record and the stored bytes are still intact."""
    record = load_source_record(source_sha256, data_root)
    stored = require_stored_source(
        source_directory(data_root, source_sha256),
        record,
        mismatch=RefusalCode.SOURCE_HASH_MISMATCH,
    )
    return VerifiedSource(record, stored)


def pinned_source_record(source_sha256: str, seal: str, data_root: Path) -> dict[str, JsonValue]:
    """Read the source record a corpus version pinned, which an amendment may since have replaced.

    A replaced record is kept under its seal, so what a version rests on stays readable.
    """
    current = load_source_record(source_sha256, data_root)
    if current[SEAL_FIELD] == seal:
        return current
    replaced = replaced_record_path(source_directory(data_root, source_sha256), seal)
    if not replaced.is_file():
        raise CorpusRefusal(
            RefusalCode.SOURCE_RECORD_CHANGED,
            "the source record this corpus version pinned is no longer kept",
            {"source_sha256": source_sha256, "source_manifest_sha256": seal},
        )
    return read_sealed(replaced, SOURCE_MANIFEST)
