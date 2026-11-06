"""Read the imported source records that a corpus version builds on and pins.

A corpus states the rights its sources had when it was built, so every use re-reads the record
and refuses one that changed, and a build or a decode also checks the stored bytes again.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.sources.identity import require_stored_source
from ss_track.corpus.sources.importer import MANIFEST_NAME, SOURCE_MANIFEST, source_directory
from ss_track.corpus.sources.terms import changed_terms


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


def load_verified_source(source_sha256: str, data_root: Path) -> dict[str, JsonValue]:
    """Load a source record only if both the record and the stored bytes are still intact."""
    manifest = load_source_record(source_sha256, data_root)
    require_stored_source(
        source_directory(data_root, source_sha256),
        manifest,
        mismatch=RefusalCode.SOURCE_HASH_MISMATCH,
    )
    return manifest
