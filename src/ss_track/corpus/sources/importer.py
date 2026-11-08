"""`ss-track import`: turn one declared recording into an immutable, hashed source record.

Imports take one shared lock on the data root's imports while their scratch exists. An import that
finds no other holder first removes the scratch a killed import left, so a copy of a source that
never reached its record does not stay on disk.
"""

import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.declaration import (
    RecordingDeclaration,
    load_recording_declaration,
)
from ss_track.corpus.decoding.decode import MediaInspection, inspect_media
from ss_track.corpus.decoding.decode_policy import DecodePolicy, current_decode_policy
from ss_track.corpus.records.kinds import SOURCE_MANIFEST
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.sources.identity import (
    addressed_identity,
    require_stored_source,
    source_identity,
)
from ss_track.corpus.sources.source_file import copy_declared_source, require_regular_file
from ss_track.corpus.sources.source_record import changed_facts, declared_terms, decoded_sequence
from ss_track.corpus.sources.terms import AMEND_COMMAND, changed_terms
from ss_track.corpus.sources.timestamps import TimestampQuality, assess_timestamps
from ss_track.corpus.storage.layout import MANIFEST_NAME, import_root, source_directory
from ss_track.corpus.storage.scratch import READ_ONLY_FILE_MODE, scratch_directory, shared_lock

IMPORTED = "imported"
UNCHANGED = "unchanged"
_SOURCE_STEM = "source"
_LOCK_NAME = ".import.lock"

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Outcome of an accepted import."""

    status: str
    source_sha256: str
    manifest_sha256: str
    manifest_path: Path
    timestamp_quality: str
    frame_count: int
    completeness_checks: list[str]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        record: dict[str, JsonValue] = asdict(self)
        record["manifest_path"] = str(self.manifest_path)
        return record


def import_source(declaration_path: Path, data_root: Path) -> ImportResult:
    """Import one recording, leaving a complete record or nothing."""
    declaration = load_recording_declaration(declaration_path)
    require_regular_file(declaration.source_path)
    if declaration.source_path.stat().st_size == 0:
        raise CorpusRefusal(RefusalCode.SOURCE_EMPTY, "source file has zero length")
    policy = current_decode_policy()
    imports = import_root(data_root)
    with shared_lock(imports, _LOCK_NAME, clear=(imports,)), scratch_directory(imports) as staged:
        return _import_into(declaration, policy, staged, data_root)


def _import_into(
    declaration: RecordingDeclaration, policy: DecodePolicy, staged: Path, data_root: Path
) -> ImportResult:
    stored = staged / f"{_SOURCE_STEM}{declaration.source_path.suffix.lower()}"
    sha256, size = copy_declared_source(declaration, stored)
    _read_if_present(data_root, sha256, declaration.video_stream_index)
    inspection = inspect_media(stored, policy, video_stream_index=declaration.video_stream_index)
    quality = assess_timestamps(inspection.pts, declaration.capture_clock_evidence)
    identity = source_identity(sha256, inspection.video_stream_index)
    if not inspection.completeness_checks:
        _LOG.warning("source %s has no container-level completeness evidence", identity)
    sealed = seal(_manifest_body(declaration, policy, inspection, quality, sha256, size, stored))
    write_sealed(staged / MANIFEST_NAME, sealed)
    stored.chmod(READ_ONLY_FILE_MODE)
    target = source_directory(data_root, identity)
    status = _commit(staged, target, sealed, declaration)
    return ImportResult(
        status=status,
        source_sha256=identity,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=target / MANIFEST_NAME,
        timestamp_quality=quality.value,
        frame_count=len(inspection.pts),
        completeness_checks=list(inspection.completeness_checks),
    )


def _origin(declaration: RecordingDeclaration) -> dict[str, JsonValue]:
    """Return upstream membership when the declaration records it, and nothing otherwise."""
    if not declaration.origin:
        return {}
    return {"origin": [item.to_record() for item in declaration.origin]}


def _manifest_body(
    declaration: RecordingDeclaration,
    policy: DecodePolicy,
    inspection: MediaInspection,
    quality: TimestampQuality,
    sha256: str,
    size: int,
    stored: Path,
) -> dict[str, JsonValue]:
    """Build the hashed record. It holds no clock time or path, so an import can be repeated."""
    evidence = declaration.capture_clock_evidence
    return {
        **SOURCE_MANIFEST.stamp(),
        "source": {
            "sha256": sha256,
            "sha256_declared": declaration.expected_sha256 is not None,
            "size_bytes": size,
            "stored_name": stored.name,
        },
        **declared_terms(declaration),
        **_origin(declaration),
        "capture": declaration.capture,
        "sequence": decoded_sequence(inspection, quality, evidence, declaration.color_matrix),
        **policy.record_fields(),
    }


def _read_if_present(data_root: Path, content_sha256: str, index: int | None) -> None:
    """Refuse a damaged record of this identity before spending a decode on it.

    Inspection still refuses a container that has more than one video stream and names none,
    before anything is published.
    """
    target = source_directory(data_root, addressed_identity(content_sha256, index))
    if target.exists():
        read_sealed(target / MANIFEST_NAME, SOURCE_MANIFEST)


def _commit(
    staged: Path, target: Path, sealed: dict[str, Any], declaration: RecordingDeclaration
) -> str:
    """Publish a finished directory in one rename, or confirm the one already there."""
    if not target.exists():
        staged.rename(target)
        return IMPORTED
    existing = read_sealed(target / MANIFEST_NAME, SOURCE_MANIFEST)
    if existing != sealed:
        raise _import_conflict(existing, sealed, declaration)
    require_stored_source(target, sealed, mismatch=RefusalCode.RECORD_TAMPERED)
    return UNCHANGED


def _import_conflict(
    existing: Mapping[str, Any], sealed: Mapping[str, Any], declaration: RecordingDeclaration
) -> CorpusRefusal:
    """Name the terms that differ, and the command only when it can record the change."""
    terms = changed_terms(existing, sealed)
    facts = changed_facts(existing, declaration)
    amendable = terms and not facts
    message = (
        f"this source was already imported under other terms; record them with {AMEND_COMMAND}"
        if amendable
        else "this source was already imported with a different declaration or decoder"
    )
    details: dict[str, JsonValue] = {
        "existing_manifest_sha256": existing[SEAL_FIELD],
        "new_manifest_sha256": sealed[SEAL_FIELD],
        "changed_terms": list(terms),
    }
    if facts:
        details["changed_facts"] = list(facts)
    return CorpusRefusal(RefusalCode.IMPORT_CONFLICT, message, details)
