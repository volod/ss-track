"""How the read path refuses a sealed record, so each refusal says what an operator must act on.

`corpus.records.sealed` decides; this states the decision. A schema refusal names the contract, the found
and accepted majors, whether the record is older, newer or unstated, its disposition and the change
log's remedy. A tampered or incomplete record names the file and what failed.
"""

from collections.abc import Collection, Iterator
from contextlib import contextmanager
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.read_window import StatedShape
from ss_track.schema.validation.enforce import older_remedy, readable_majors

OLDER = "older"
NEWER = "newer"
UNSTATED = "unstated"
_NEWER_REMEDY = "install the ss-track version that wrote this record"
_UNWRITTEN_REMEDY = "no ss-track version writes this; restore the record from a trusted copy"


def schema_details(
    path: Path, record_format: RecordFormat, found: JsonValue
) -> dict[str, JsonValue]:
    """State which record a schema refusal is about, and how its major relates to this code's."""
    majors: list[JsonValue] = [*readable_majors(record_format.kind, record_format.major)]
    return {
        "record": path.name,
        "path": str(path),
        "kind": record_format.kind,
        "found_schema_version": found,
        "accepted_schema_versions": majors,
        "age": _age(found, record_format.major),
    }


def schema_refusal(
    path: Path, record_format: RecordFormat, found: JsonValue, disposition: str | None
) -> CorpusRefusal:
    """Refuse a record of a major this code does not read, with the change log's remedy."""
    age = _age(found, record_format.major)
    remedy = _remedy(age, record_format, found)
    accepted = readable_majors(record_format.kind, record_format.major)
    stated = f" ({disposition})" if age == OLDER and disposition else ""
    return CorpusRefusal(
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
        f"{path.name} ({record_format.kind}) has {age} schema {found}{stated}; "
        f"this version reads schema {_listed(accepted)}: {remedy}",
        schema_details(path, record_format, found)
        | ({"disposition": disposition} if age == OLDER else {})
        | {"remedy": remedy},
    )


def shape_refusal(
    path: Path,
    record_format: RecordFormat,
    found: JsonValue,
    disposition: str,
    shape: tuple[StatedShape, list[str]],
) -> CorpusRefusal:
    """Refuse a stated shape, naming what it lacks and the remedy its shape states."""
    stated, lacking = shape
    return CorpusRefusal(
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
        f"{path.name} ({record_format.kind}) is {stated.name}, an older shape of schema {found} "
        f"({disposition}): {stated.remedy}",
        schema_details(path, record_format, found)
        | {
            "age": OLDER,
            "shape": stated.name,
            "disposition": disposition,
            "lacking": [*lacking],
            "remedy": stated.remedy,
        },
    )


def tampered(path: Path, message: str) -> CorpusRefusal:
    """Refuse a record whose bytes cannot be believed: unreadable, unsealed or of another kind."""
    return CorpusRefusal(RefusalCode.RECORD_TAMPERED, message, {"record": path.name})


@contextmanager
def incomplete_record(name: str) -> Iterator[None]:
    """Refuse a record that lacks a fact its reader takes, which only a reseal by hand can make.

    A seal proves that a record matches itself, not its contract, so a reader that walks a record
    does it inside this, and a missing fact is a refusal instead of a traceback.
    """
    try:
        yield
    except (KeyError, TypeError) as error:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "record is incomplete",
            {"record": name, "field": str(error)},
        ) from error


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
