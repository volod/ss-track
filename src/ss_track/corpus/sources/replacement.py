"""Writing a successor source record, which `--amend-terms`, `--amend-capture` and `--redecode` do.

Each runs under one lock on the data root's imports, so two at once cannot lose a record neither
kept. Each carries every section of the existing record it does not replace, keeps the replaced
record under its seal before writing, so a run killed at any point loses neither version, and then
lists the corpus versions on this data root that pin the replaced record. The listing refuses
nothing and removes nothing.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.sealed import read_sealed, read_stated
from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import READ_ONLY_FILE_MODE, exclusive_lock, write_atomically
from ss_track.corpus.declarations.declaration import RecordingDeclaration
from ss_track.corpus.records.kinds import SOURCE_MANIFEST
from ss_track.corpus.sources.source_record import changed_facts
from ss_track.corpus.sources.terms import changed_terms
from ss_track.corpus.storage.layout import (
    MANIFEST_NAME,
    REPLACED_DIRECTORY,
    import_root,
    replaced_record_path,
    source_directory,
)
from ss_track.corpus.versions.impact import AmendmentImpact, report_amendment_impact
from ss_track.schema.registry.contract import VERSION_FIELD

UNCHANGED = "unchanged"
_LOCK_NAME = ".amendment.lock"


@dataclass(frozen=True, slots=True)
class ReplacementResult:
    """Outcome of an accepted amendment or redecode."""

    status: str
    source_sha256: str
    manifest_sha256: str
    manifest_path: Path
    replaced_manifest_sha256: str | None
    replaced_path: Path | None
    changed_terms: list[str]
    decode_policy_current: bool
    impact: AmendmentImpact | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        record: dict[str, JsonValue] = {
            "status": self.status,
            "source_sha256": self.source_sha256,
            "manifest_sha256": self.manifest_sha256,
            "manifest_path": str(self.manifest_path),
            "replaced_manifest_sha256": self.replaced_manifest_sha256,
            "replaced_path": None if self.replaced_path is None else str(self.replaced_path),
            "changed_terms": list(self.changed_terms),
            "decode_policy_current": self.decode_policy_current,
        }
        if self.impact is not None:
            listed = self.impact.to_record()
            if listed:
                record["impact"] = listed
        return record


@dataclass(frozen=True, slots=True)
class ExistingRecord:
    """The record a successor replaces: as written, and as the read path serves it.

    A `view` major is read as the current one, in memory, and a successor carries that reading. The
    record kept under its seal is the one written, because only those bytes match that seal.
    """

    path: Path
    written: Mapping[str, Any]
    record: Mapping[str, Any]


@contextmanager
def replacing_source(data_root: Path, source_sha256: str, refusal: str) -> Iterator[ExistingRecord]:
    """Hold the source lock and yield the imported record that a successor will replace.

    `refusal` says why bytes with no import cannot be replaced. Holding the lock proves that any
    scratch beside this record, or among the kept ones, is a killed run's, so it is removed first.
    """
    directory = source_directory(data_root, source_sha256)
    if not directory.is_dir():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, refusal, {"source_sha256": source_sha256})
    clear = (directory, directory / REPLACED_DIRECTORY)
    with exclusive_lock(import_root(data_root), _LOCK_NAME, clear=clear):
        path = directory / MANIFEST_NAME
        written = read_stated(path, SOURCE_MANIFEST).record
        yield ExistingRecord(path, written, read_sealed(path, SOURCE_MANIFEST))


def successor_of(
    existing: ExistingRecord, changes: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    """Return the existing record with `changes`, at the current major.

    `seal` validates it in full, so a successor the current contract refuses writes nothing.
    """
    carried = {key: value for key, value in existing.record.items() if key != SEAL_FIELD}
    return carried | {VERSION_FIELD: SOURCE_MANIFEST.major} | dict(changes)


def require_unchanged_facts(
    record: Mapping[str, Any],
    declaration: RecordingDeclaration,
    source_sha256: str,
    *,
    amend_capture: bool = False,
) -> None:
    """Refuse a declaration that disagrees with the carried capture facts, inventing nothing."""
    facts = changed_facts(record, declaration, amend_capture=amend_capture)
    if facts:
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "the declaration changes capture facts not covered by the requested operations",
            {"source_sha256": source_sha256, "changed_facts": list(facts)},
        )


def replace_record(
    status: str,
    existing: ExistingRecord,
    successor: Mapping[str, JsonValue],
    source_sha256: str,
    data_root: Path,
    *,
    policy_current: bool,
) -> ReplacementResult:
    """Seal the successor and write it in place, keeping the record it replaces first.

    A successor equal to the existing record writes nothing and reports `unchanged`.
    """
    path = existing.path
    sealed = seal(successor)
    if sealed == existing.record:
        seal_value = str(sealed[SEAL_FIELD])
        return ReplacementResult(
            UNCHANGED, source_sha256, seal_value, path, None, None, [], policy_current
        )
    replaced_sha256 = str(existing.written[SEAL_FIELD])
    replaced = replaced_record_path(path.parent, replaced_sha256)
    replaced.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(replaced, path.read_bytes(), mode=READ_ONLY_FILE_MODE)
    write_sealed(path, sealed)
    return ReplacementResult(
        status=status,
        source_sha256=source_sha256,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=path,
        replaced_manifest_sha256=replaced_sha256,
        replaced_path=replaced,
        changed_terms=changed_terms(existing.record, sealed),
        decode_policy_current=policy_current,
        impact=report_amendment_impact(data_root, replaced_sha256),
    )
