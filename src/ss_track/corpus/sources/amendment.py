"""`ss-track import --amend-terms`: record new terms for an imported source, decoding nothing.

Only rights and sensitivity change. Every other section is carried from the existing record, so
restoring the old terms of a current record restores its seal. Stored bytes are not read: a
withdrawal must stay recordable after an operator has already removed them, and `corpus build`
hashes them again regardless. The installed decoder is not consulted either, because recording
narrower terms must not need a decode of the material they withdraw.

The lock, the replaced-record keep and the current-major gate are shared with `--redecode`
(`corpus.sources.redecode`), which writes a successor the same way but from a fresh decode. After
the replacement is recorded, both commands list the corpus versions on this data root that pin the
replaced record. The listing refuses nothing and removes nothing.
"""

import fcntl
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.declaration import (
    RecordingDeclaration,
    load_recording_declaration,
)
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.records.read_refusals import schema_details
from ss_track.corpus.records.sealed import read_sealed, read_stated
from ss_track.corpus.records.sealing import (
    SCRATCH_PREFIX,
    seal,
    seal_violations,
    sha256_file,
    write_sealed,
)
from ss_track.corpus.sources.identity import source_identity
from ss_track.corpus.sources.importer import (
    IMPORT_DIRECTORY,
    MANIFEST_NAME,
    SOURCE_MANIFEST,
    changed_facts,
    declared_terms,
    decode_policy_sha256,
    require_regular_file,
    source_directory,
)
from ss_track.corpus.sources.terms import changed_terms
from ss_track.corpus.versions.impact import AmendmentImpact, report_amendment_impact
from ss_track.schema.registry.contract import FACTS, VERSION_FIELD, VIEW

AMENDED = "amended"
UNCHANGED = "unchanged"
REPLACED_DIRECTORY = "replaced"
_LOCK_NAME = ".amendment.lock"
_REPLACED_SUFFIX = ".json"
REDECODE_REMEDY = "supply them together with ss-track import --redecode --amend-terms"


@dataclass(frozen=True, slots=True)
class AmendmentResult:
    """Outcome of an accepted amendment."""

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


def replaced_record_path(directory: Path, manifest_sha256: str) -> Path:
    """Return where a replaced record is kept, under the seal that corpus versions pinned."""
    return directory / REPLACED_DIRECTORY / f"{manifest_sha256}{_REPLACED_SUFFIX}"


def amend_source_terms(declaration_path: Path, data_root: Path) -> AmendmentResult:
    """Replace one source record's terms in one atomic step, keeping the record it replaces."""
    declaration = load_recording_declaration(declaration_path)
    sha256 = named_source(declaration)
    directory = source_directory(data_root, sha256)
    if not directory.is_dir():
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "no imported source has these bytes, and an amendment cannot import or change a file",
            {"source_sha256": sha256},
        )
    with exclusive_source_lock(data_root):
        return _amend(declaration, sha256, directory, data_root)


def content_hash(declaration: RecordingDeclaration) -> str:
    """Return the file hash, or the declared hash once the original file has gone."""
    declared = declaration.expected_sha256
    path = declaration.source_path
    if declared is not None and not path.exists():
        return declared
    require_regular_file(path)
    try:
        found = sha256_file(path)
    except PermissionError as error:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, str(error.strerror)) from error
    if declared is not None and declared != found:
        raise CorpusRefusal(
            RefusalCode.SOURCE_HASH_MISMATCH,
            "source bytes do not match the declared hash",
            {"expected_sha256": declared, "actual_sha256": found},
        )
    return found


def named_source(declaration: RecordingDeclaration) -> str:
    """Return the source identity this declaration names.

    An omitted index addresses the first video stream. A later stream keeps its index, including
    after the file is gone, when the declared hash and that index together name it. An amendment
    does not open the container, so it cannot tell a missing index from the first stream.
    """
    index = declaration.video_stream_index
    return source_identity(content_hash(declaration), 0 if index is None else index)


@contextmanager
def exclusive_source_lock(data_root: Path) -> Iterator[None]:
    """Serialize amendments and redecodes, so two at once cannot lose a record neither kept."""
    with (data_root / IMPORT_DIRECTORY / _LOCK_NAME).open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _amend(
    declaration: RecordingDeclaration, sha256: str, directory: Path, data_root: Path
) -> AmendmentResult:
    path = directory / MANIFEST_NAME
    stated = read_stated(path, SOURCE_MANIFEST)
    # A view major reads as the current one; a `facts` major is what an amendment exists to replace.
    existing = read_sealed(path, SOURCE_MANIFEST) if stated.disposition == VIEW else stated.record
    carried = {key: value for key, value in existing.items() if key != SEAL_FIELD}
    successor = carried | {VERSION_FIELD: SOURCE_MANIFEST.major} | declared_terms(declaration)
    if stated.disposition == FACTS:
        require_current_facts(successor, existing, sha256, path)
    require_unchanged_facts(existing, declaration, sha256)
    sealed = seal(successor)
    current = _policy_is_installed(existing)
    if sealed == existing:
        seal_value = str(sealed[SEAL_FIELD])
        return AmendmentResult(UNCHANGED, sha256, seal_value, path, None, None, [], current)
    replaced_sha = str(existing[SEAL_FIELD])
    replaced = keep_replaced(existing, directory)
    write_sealed(path, sealed)
    return AmendmentResult(
        status=AMENDED,
        source_sha256=sha256,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=path,
        replaced_manifest_sha256=replaced_sha,
        replaced_path=replaced,
        changed_terms=changed_terms(existing, sealed),
        decode_policy_current=current,
        impact=report_amendment_impact(data_root, replaced_sha),
    )


def require_unchanged_facts(
    record: Mapping[str, Any], declaration: RecordingDeclaration, sha256: str
) -> None:
    """Refuse a declaration that disagrees with the carried capture facts, inventing nothing."""
    facts = changed_facts(record, declaration)
    if facts:
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "an amendment or a redecode changes no capture fact",
            {"source_sha256": sha256, "changed_facts": list(facts)},
        )


def require_current_facts(
    successor: Mapping[str, JsonValue], record: Mapping[str, Any], sha256: str, path: Path
) -> None:
    """Refuse a successor that still falls short of the current major, by name.

    The current contract states every fact a record of this major holds. An amendment alone adds
    only terms, and the earliest source records of major 1 also lack four decoded facts that only a
    decode gives; a plain `--redecode` alone carries the existing terms forward unchanged, so a
    record that predates required terms is short the same way. Only `--redecode --amend-terms`
    together supply both at once.
    """
    found = seal_violations(successor)
    if found:
        listed: list[JsonValue] = [item.to_record() for item in found]
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            "this record lacks facts of the current major that this command cannot supply alone",
            schema_details(path, SOURCE_MANIFEST, record[VERSION_FIELD])
            | {"source_sha256": sha256, "violations": listed, "remedy": REDECODE_REMEDY},
        )


def _policy_is_installed(record: Mapping[str, Any]) -> bool:
    installed = decode_policy_sha256(current_decode_policy().as_record())
    return bool(record.get("decode_policy_sha256") == installed)


def keep_replaced(record: Mapping[str, JsonValue], directory: Path) -> Path:
    """Keep the old record first, so a run killed at any point loses neither version.

    Holding the source lock proves that any scratch file here is a killed run's.
    """
    for folder in (directory, directory / REPLACED_DIRECTORY):
        for partial in folder.glob(f"{SCRATCH_PREFIX}*"):
            partial.unlink()
    path = replaced_record_path(directory, str(record[SEAL_FIELD]))
    write_sealed(path, record)
    return path
