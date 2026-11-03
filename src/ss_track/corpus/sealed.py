"""Canonical hashing and self-verifying JSON records."""

import hashlib
import json
import os
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from ss_track.canonical import SEAL_FIELD, seal_of
from ss_track.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema.enforce import older_remedy, require_record

SCRATCH_PREFIX = ".incoming-"
READ_ONLY_FILE_MODE = 0o444
READ_ONLY_DIRECTORY_MODE = 0o555
OLDER = "older"
NEWER = "newer"
UNSTATED = "unstated"
_CHUNK_BYTES = 1024 * 1024
_UNSEALED = "0" * 64  # a well-formed stand-in, so validation needs no hash of an invalid body
_NEWER_REMEDY = "install the ss-track version that wrote this record"
_UNWRITTEN_REMEDY = "no ss-track version writes this; restore the record from a trusted copy"


@dataclass(frozen=True, slots=True)
class RecordFormat:
    """One kind of sealed record and the major this code reads and writes."""

    kind: str
    major: int


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 of a file's bytes."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def copy_with_sha256(source: Path, target: Path) -> tuple[str, int]:
    """Copy a file and hash the bytes actually copied, so one read serves both."""
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as reader, target.open("xb") as writer:
        while chunk := reader.read(_CHUNK_BYTES):
            digest.update(chunk)
            writer.write(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def seal(body: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the record with a hash that covers every other field, once its contract holds.

    This is the one validation a record gets: a writer defect is `RECORD_INVALID` with nothing
    sealed, and a read then trusts the seal instead of walking the fields again.
    """
    require_record(dict(body) | {SEAL_FIELD: _UNSEALED})  # before hashing, which a NaN would break
    sealed = dict(body)
    sealed[SEAL_FIELD] = seal_of(body)
    return sealed


def write_sealed(path: Path, sealed: Mapping[str, JsonValue]) -> None:
    """Write a read-only record so that a crash cannot leave a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(sealed, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
    with NamedTemporaryFile(
        "w", encoding="ascii", dir=path.parent, prefix=SCRATCH_PREFIX, delete=False
    ) as handle:
        handle.write(payload + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary = Path(handle.name)
    temporary.chmod(READ_ONLY_FILE_MODE)
    temporary.replace(path)


def read_sealed(
    path: Path, record_format: RecordFormat, *, older_majors: Collection[int] = ()
) -> dict[str, JsonValue]:
    """Read a record through its seal, then its kind, then its major: the only sealed read.

    Only a command that exists to replace an older record passes `older_majors`, and it then answers
    for what that major lacks.
    """
    record = _read_intact(path)
    if record.get("kind") != record_format.kind:
        raise _tampered(path, f"record kind is not {record_format.kind}")
    accepted = sorted({record_format.major, *older_majors})
    found = record.get("schema_version")
    if type(found) is not int or found not in accepted:  # True and 1.0 compare equal to 1
        age = _age(found, record_format.major)
        remedy = _remedy(age, record_format, found)
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            f"{path.name} ({record_format.kind}) has {age} schema {found}; "
            f"this version reads schema {record_format.major}: {remedy}",
            schema_details(path, record_format, found, accepted) | {"remedy": remedy},
        )
    return record


def schema_details(
    path: Path, record_format: RecordFormat, found: JsonValue, accepted: Collection[int]
) -> dict[str, JsonValue]:
    """State which record a schema refusal is about, and how its major relates to this code's."""
    majors: list[JsonValue] = [*sorted(accepted)]
    return {
        "record": path.name,
        "path": str(path),
        "kind": record_format.kind,
        "found_schema_version": found,
        "accepted_schema_versions": majors,
        "age": _age(found, record_format.major),
    }


def _age(found: JsonValue, major: int) -> str:
    if type(found) is not int:
        return UNSTATED
    return OLDER if found < major else NEWER


def _remedy(age: str, record_format: RecordFormat, found: JsonValue) -> str:
    """Name the change log's migration for an older major, which is its one statement."""
    if age == OLDER and type(found) is int:
        return older_remedy(record_format.kind, found) or _UNWRITTEN_REMEDY
    return _NEWER_REMEDY if age == NEWER else _UNWRITTEN_REMEDY


def _read_intact(path: Path) -> dict[str, JsonValue]:
    """Return an object whose seal matches, interpreting nothing else in it.

    `ValueError` covers bad text, bad JSON, an over-long integer and a `NaN`, which `canonical_json`
    refuses because no record can hold one. Unmatched, those would end in a traceback.
    """
    try:
        loaded = json.loads(path.read_text(encoding="ascii"))
        if not isinstance(loaded, dict):
            raise _tampered(path, "record is not a JSON object")
        seal_matches = loaded.get(SEAL_FIELD) == seal_of(loaded)
    except FileNotFoundError as error:
        raise _tampered(path, "record is missing") from error
    except (ValueError, RecursionError) as error:
        raise _tampered(path, f"record is not valid JSON: {error}") from error
    if not seal_matches:
        raise _tampered(path, "record content does not match its seal")
    return loaded


def _tampered(path: Path, message: str) -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.RECORD_TAMPERED, message, {"record": path.name})
