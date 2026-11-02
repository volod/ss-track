"""`ss-track import --amend-terms`: record new terms for an imported source, decoding nothing.

Only rights and sensitivity change. Every other section is carried from the existing record, so
restoring the old terms of a current record restores its seal. Stored bytes are not read: a
withdrawal must stay recordable after an operator has already removed them, and `corpus build`
hashes them again regardless. The installed decoder is not consulted either, because recording
narrower terms must not need a decode of the material they withdraw.
"""

import fcntl
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from ss_track.corpus.declaration import RecordingDeclaration, load_recording_declaration
from ss_track.corpus.decode import DecodePolicy, current_decode_policy
from ss_track.corpus.importer import (
    IMPORT_DIRECTORY,
    MANIFEST_NAME,
    SCHEMA_VERSION,
    SEQUENCE_KEYS,
    SOURCE_MANIFEST_KIND,
    changed_facts,
    declared_terms,
    decode_policy_sha256,
    require_regular_file,
    source_directory,
)
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import (
    SCRATCH_PREFIX,
    SEAL_FIELD,
    read_sealed,
    require_schema,
    seal,
    sha256_file,
    write_sealed,
)
from ss_track.corpus.terms import changed_terms

AMENDED = "amended"
UNCHANGED = "unchanged"
REPLACED_DIRECTORY = "replaced"
_LOCK_NAME = ".amendment.lock"
_REPLACED_SUFFIX = ".json"
_SCHEMA_WITHOUT_TERMS = 1  # lacks retain_until and derived_frames, which only an operator can state
_POLICY_KEYS = frozenset(item.name for item in fields(DecodePolicy))


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

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": self.status,
            "source_sha256": self.source_sha256,
            "manifest_sha256": self.manifest_sha256,
            "manifest_path": str(self.manifest_path),
            "replaced_manifest_sha256": self.replaced_manifest_sha256,
            "replaced_path": None if self.replaced_path is None else str(self.replaced_path),
            "changed_terms": list(self.changed_terms),
            "decode_policy_current": self.decode_policy_current,
        }


def replaced_record_path(directory: Path, manifest_sha256: str) -> Path:
    """Return where a replaced record is kept, under the seal that corpus versions pinned."""
    return directory / REPLACED_DIRECTORY / f"{manifest_sha256}{_REPLACED_SUFFIX}"


def amend_source_terms(declaration_path: Path, data_root: Path) -> AmendmentResult:
    """Replace one source record's terms in one atomic step, keeping the record it replaces."""
    declaration = load_recording_declaration(declaration_path)
    sha256 = _named_source(declaration)
    directory = source_directory(data_root, sha256)
    if not directory.is_dir():
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "no imported source has these bytes, and an amendment cannot import or change a file",
            {"source_sha256": sha256},
        )
    with _exclusive_amendment(data_root):
        return _amend(declaration, sha256, directory)


def _named_source(declaration: RecordingDeclaration) -> str:
    """Find the source by its bytes, or by its declared hash once the original has gone."""
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


@contextmanager
def _exclusive_amendment(data_root: Path) -> Iterator[None]:
    """Serialize amendments, so two at once cannot lose a record neither of them kept."""
    with (data_root / IMPORT_DIRECTORY / _LOCK_NAME).open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _amend(declaration: RecordingDeclaration, sha256: str, directory: Path) -> AmendmentResult:
    path = directory / MANIFEST_NAME
    existing = read_sealed(path, SOURCE_MANIFEST_KIND)
    _require_amendable(existing, declaration, sha256, path)
    body = {key: value for key, value in existing.items() if key != SEAL_FIELD}
    sealed = seal(body | {"schema_version": SCHEMA_VERSION} | declared_terms(declaration))
    current = _policy_is_installed(existing)
    if sealed == existing:
        seal_value = str(sealed[SEAL_FIELD])
        return AmendmentResult(UNCHANGED, sha256, seal_value, path, None, None, [], current)
    replaced = _keep_replaced(existing, directory)
    write_sealed(path, sealed)
    return AmendmentResult(
        status=AMENDED,
        source_sha256=sha256,
        manifest_sha256=str(sealed[SEAL_FIELD]),
        manifest_path=path,
        replaced_manifest_sha256=str(existing[SEAL_FIELD]),
        replaced_path=replaced,
        changed_terms=changed_terms(existing, sealed),
        decode_policy_current=current,
    )


def _require_amendable(
    record: Mapping[str, Any], declaration: RecordingDeclaration, sha256: str, path: Path
) -> None:
    if record.get("schema_version") == _SCHEMA_WITHOUT_TERMS:
        _require_current_facts(record, sha256)
    else:
        require_schema(record, SCHEMA_VERSION, path)
    facts = changed_facts(record, declaration)
    if facts:
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "an amendment changes only rights and sensitivity",
            {"source_sha256": sha256, "changed_facts": list(facts)},
        )


def _require_current_facts(record: Mapping[str, Any], sha256: str) -> None:
    """Refuse an older record that writing forward would leave short of the current major."""
    sequence = record.get("sequence", {}).keys()
    policy = record.get("decode_policy", {}).keys()
    missing = [f"sequence.{key}" for key in sorted(SEQUENCE_KEYS - sequence)]
    missing += [f"decode_policy.{key}" for key in sorted(_POLICY_KEYS - policy)]
    if missing:
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            "this record lacks decoded facts that an amendment cannot supply",
            {"source_sha256": sha256, "missing_facts": list(missing)},
        )


def _policy_is_installed(record: Mapping[str, Any]) -> bool:
    installed = decode_policy_sha256(current_decode_policy().as_record())
    return bool(record.get("decode_policy_sha256") == installed)


def _keep_replaced(record: Mapping[str, JsonValue], directory: Path) -> Path:
    """Keep the old record first, so a run killed at any point loses neither version.

    Holding the amendment lock proves that any scratch file here is a killed run's.
    """
    for folder in (directory, directory / REPLACED_DIRECTORY):
        for partial in folder.glob(f"{SCRATCH_PREFIX}*"):
            partial.unlink()
    path = replaced_record_path(directory, str(record[SEAL_FIELD]))
    write_sealed(path, record)
    return path
