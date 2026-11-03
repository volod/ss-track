"""Canonical hashing and self-verifying JSON records."""

import hashlib
import json
import os
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from ss_track.canonical import SEAL_FIELD, seal_of
from ss_track.corpus.projections import installed_projections
from ss_track.corpus.read_window import StatedShape, apply_views, installed_views, stated_shape
from ss_track.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema.enforce import (
    older_disposition,
    older_remedy,
    readable_majors,
    require_record,
)
from ss_track.schema.store import DISPOSITIONS, FACTS, VERSION_FIELD, VIEW

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


def read_sealed(path: Path, record_format: RecordFormat) -> dict[str, JsonValue]:
    """Read a record as evidence: its seal, then its kind, then the disposition of its major.

    This is the only sealed read that hands a record onward as evidence. A record of the current
    major is returned as written; one of a `view` major is returned as the current major, in memory;
    anything else is refused with the change log's remedy.
    """
    record = _read_intact(path, record_format)
    found = record.get(VERSION_FIELD)
    current = _is_major(found, record_format.major)
    disposition = None if current else _disposition(record_format, found)
    shape = stated_shape(record_format.kind, found, record) if type(found) is int else None
    if shape is not None:
        raise _shape_refusal(path, record_format, found, _strictest(disposition, shape[0]), shape)
    if current:
        return record
    if disposition == VIEW and type(found) is int:
        return apply_views(record, installed_views(), found, record_format.major)
    raise _schema_refusal(path, record_format, found, disposition)


@dataclass(frozen=True, slots=True)
class StatedRecord:
    """A record as written, for inspection and for an amendment that writes its successor."""

    record: dict[str, JsonValue]
    disposition: str | None  # None for the current shape


def read_stated(path: Path, record_format: RecordFormat) -> StatedRecord:
    """Read a record whose stated facts stay readable, as written, without serving it as evidence.

    A `facts` or `view` major qualifies, and so does a stated shape of the current major. A retired,
    newer or unstated major is refused exactly as by `read_sealed`.
    """
    record = _read_intact(path, record_format)
    found = record.get(VERSION_FIELD)
    current = _is_major(found, record_format.major)
    disposition = None if current else _disposition(record_format, found)
    if not current and disposition not in (VIEW, FACTS):
        raise _schema_refusal(path, record_format, found, disposition)
    shape = stated_shape(record_format.kind, found, record) if type(found) is int else None
    return StatedRecord(record, disposition if shape is None else _strictest(disposition, shape[0]))


@dataclass(frozen=True, slots=True)
class Comparable:
    """What a comparison rule may read from a record of any major: its seal and its projection."""

    seal: str
    major: JsonValue
    projected: dict[str, JsonValue] | None  # None when that major keeps no projection


def read_comparable(path: Path, record_format: RecordFormat) -> Comparable:
    """Read a record for a comparison rule, whatever its disposition, through its major's projection.

    A record that fails its seal or names another kind still refuses: that says something about the
    evidence. A major with no projection says only something about the format.
    """
    record = _read_intact(path, record_format)
    found = record.get(VERSION_FIELD)
    project = (
        installed_projections().get((record_format.kind, found)) if type(found) is int else None
    )
    try:
        projected = None if project is None else project(record)
    except (KeyError, TypeError) as error:
        raise _tampered(path, f"record lacks a fact its major holds: {error}") from error
    return Comparable(str(record[SEAL_FIELD]), found, projected)


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


def _is_major(found: JsonValue, major: int) -> bool:
    return type(found) is int and found == major  # True and 1.0 compare equal to 1


def _strictest(disposition: str | None, shape: StatedShape) -> str:
    """A stated shape lacks facts its major's other records hold, so it is read no more freely."""
    found = [item for item in (disposition, shape.disposition) if item is not None]
    return max(found, key=DISPOSITIONS.index)


def _disposition(record_format: RecordFormat, found: JsonValue) -> str | None:
    if type(found) is not int:
        return None
    return older_disposition(record_format.kind, found, record_format.major)


def _schema_refusal(
    path: Path, record_format: RecordFormat, found: JsonValue, disposition: str | None
) -> CorpusRefusal:
    age = _age(found, record_format.major)
    remedy = _remedy(age, record_format, found)
    accepted = readable_majors(record_format.kind, record_format.major)
    stated = f" ({disposition})" if age == OLDER and disposition else ""
    return CorpusRefusal(
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
        f"{path.name} ({record_format.kind}) has {age} schema {found}{stated}; "
        f"this version reads schema {_listed(accepted)}: {remedy}",
        schema_details(path, record_format, found, accepted)
        | ({"disposition": disposition} if age == OLDER else {})
        | {"remedy": remedy},
    )


def _shape_refusal(
    path: Path,
    record_format: RecordFormat,
    found: JsonValue,
    disposition: str,
    shape: tuple[StatedShape, list[str]],
) -> CorpusRefusal:
    stated, lacking = shape
    return CorpusRefusal(
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
        f"{path.name} ({record_format.kind}) is {stated.name}, an older shape of schema {found} "
        f"({disposition}): {stated.remedy}",
        schema_details(
            path, record_format, found, readable_majors(record_format.kind, record_format.major)
        )
        | {
            "age": OLDER,
            "shape": stated.name,
            "disposition": disposition,
            "lacking": [*lacking],
            "remedy": stated.remedy,
        },
    )


def _listed(majors: Collection[int]) -> str:
    return ", ".join(str(major) for major in majors)


def _age(found: JsonValue, major: int) -> str:
    if type(found) is not int:
        return UNSTATED
    return OLDER if found < major else NEWER


def _remedy(age: str, record_format: RecordFormat, found: JsonValue) -> str:
    """Name the change log's migration for an older major, which is its one statement."""
    if age == OLDER and type(found) is int:
        return older_remedy(record_format.kind, found) or _UNWRITTEN_REMEDY
    return _NEWER_REMEDY if age == NEWER else _UNWRITTEN_REMEDY


def _read_intact(path: Path, record_format: RecordFormat) -> dict[str, JsonValue]:
    """Return an object whose seal matches and whose kind is this format's, interpreting nothing else.

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
    if loaded.get("kind") != record_format.kind:
        raise _tampered(path, f"record kind is not {record_format.kind}")
    return loaded


def _tampered(path: Path, message: str) -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.RECORD_TAMPERED, message, {"record": path.name})
