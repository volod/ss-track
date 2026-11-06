"""The one read path for a sealed record: its seal, then its kind, then the disposition of its major.

Three entries answer three questions, and no caller reads a sealed record any other way, as
`tests/corpus/records/test_sealed_reads.py` holds. `read_sealed` serves evidence, `read_stated`
serves an inspection or an amendment, and `read_comparable` serves a comparison rule through a
projection. Writing a record is `corpus.records.sealing`; the refusals these reads raise are
`corpus.records.read_refusals`.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.canonical import SEAL_FIELD, seal_of
from ss_track.core.refusal import JsonValue
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.projections import installed_projections
from ss_track.corpus.records.read_refusals import (
    incomplete_record,
    schema_refusal,
    shape_refusal,
    tampered,
)
from ss_track.corpus.records.read_window import (
    StatedShape,
    apply_views,
    installed_views,
    stated_shape,
)
from ss_track.schema.registry.contract import DISPOSITIONS, FACTS, KIND_FIELD, VERSION_FIELD, VIEW
from ss_track.schema.validation.enforce import older_disposition


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
        raise shape_refusal(path, record_format, found, _strictest(disposition, shape[0]), shape)
    if current:
        return record
    if disposition == VIEW and type(found) is int:
        return apply_views(record, installed_views(), found, record_format.major)
    raise schema_refusal(path, record_format, found, disposition)


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
        raise schema_refusal(path, record_format, found, disposition)
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
    with incomplete_record(path.name):
        projected = None if project is None else project(record)
    return Comparable(str(record[SEAL_FIELD]), found, projected)


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


def _read_intact(path: Path, record_format: RecordFormat) -> dict[str, JsonValue]:
    """Return an object whose seal matches and whose kind is this format's, interpreting nothing else.

    `ValueError` covers bad text, bad JSON, an over-long integer and a `NaN`, which `canonical_json`
    refuses because no record can hold one. Unmatched, those would end in a traceback.
    """
    try:
        loaded = json.loads(path.read_text(encoding="ascii"))
        if not isinstance(loaded, dict):
            raise tampered(path, "record is not a JSON object")
        seal_matches = loaded.get(SEAL_FIELD) == seal_of(loaded)
    except FileNotFoundError as error:
        raise tampered(path, "record is missing") from error
    except (ValueError, RecursionError) as error:
        raise tampered(path, f"record is not valid JSON: {error}") from error
    if not seal_matches:
        raise tampered(path, "record content does not match its seal")
    if loaded.get(KIND_FIELD) != record_format.kind:
        raise tampered(path, f"record kind is not {record_format.kind}")
    return loaded
