"""What the read path does with a record that is not in the current shape: views and stated shapes.

A view reads a record of one major as the next, in memory. It leaves the file, its seal and every
pin as they are, and it names each value it derives, none of which may be an operator judgment or
an algorithm revision. Views compose one major at a time. The installed contracts declare which
majors are views, and this module holds the function for each, so a declared view with no function
is a damaged installation and not an older record.

A stated shape is a format that entered a major without a version of its own. No stamp tells it
apart, so one test of the record does, here on the read path and nowhere else.
"""

import copy
import logging
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.schema.compatibility.dispositions import PROTECTED_PROPERTIES
from ss_track.schema.compatibility.evolution import pointer_parts
from ss_track.schema.registry.contract import VERSION_FIELD
from ss_track.schema.registry.store import damaged

ANY_POSITION = "*"
_FIXED = frozenset({SEAL_FIELD, "kind", VERSION_FIELD})
_LOG = logging.getLogger(__name__)

type Record = Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class View:
    """Read a record of `major` as `major + 1`, deriving only the values `derived` names.

    `derived` holds JSON pointers, with `*` for any list position. The read path stamps the new
    major itself, so `upcast` must leave `schema_version`, `kind` and the seal alone.
    """

    kind: str
    major: int
    derived: tuple[str, ...]
    upcast: Callable[[Record], dict[str, JsonValue]]


@dataclass(frozen=True, slots=True)
class StatedShape:
    """A format sharing a major with another, told apart by one test of the record."""

    kind: str
    major: int
    name: str
    disposition: str
    remedy: str
    lacking: Callable[[Record], list[str]]  # what the record lacks, empty when it is not this shape


def view_findings(view: View) -> list[str]:
    """Name each value a view declares that no view may derive."""
    findings = []
    for derived in view.derived:
        parts = pointer_parts(derived)
        if not parts or parts[0] in _FIXED:
            findings.append(f"{derived}: the read path alone stamps the major and keeps the seal")
        protected = sorted(set(parts) & PROTECTED_PROPERTIES)
        if protected:
            findings.append(f"{derived}: a view never derives {', '.join(protected)}")
    return findings


def check_view(view: View, record: Record) -> list[str]:
    """Apply a view to one real record and name everything it did that it did not declare.

    This walks every value, so tests run it on kept records and the read path does not.
    """
    before = copy.deepcopy(dict(record))
    after = view.upcast(record)
    findings = view_findings(view)
    if dict(record) != before:
        findings.append("the view changed the record it read")
    for location, value in _leaves(after):
        if _value_at(before, location) != value and not _declared(location, view.derived):
            findings.append(f"/{'/'.join(location)}: derived without being named")
    return findings


def apply_views(
    record: Record, views: Mapping[tuple[str, int], View], found: int, current: int
) -> dict[str, JsonValue]:
    """Read a record of `found` as `current`, one major at a time."""
    kind = str(record["kind"])
    viewed = dict(record)
    for major in range(found, current):
        view = views.get((kind, major))
        if view is None:
            raise damaged(f"the contracts declare a view of {kind} {major} this tool lacks")
        findings = view_findings(view)
        if findings:
            raise damaged(f"the view of {kind} {major} is refused: " + "; ".join(findings))
        viewed = view.upcast(viewed) | {VERSION_FIELD: major + 1, SEAL_FIELD: record[SEAL_FIELD]}
        _LOG.info("read %s major %d as %d, deriving %s", kind, major, major + 1, view.derived)
    return viewed


def installed_views() -> Mapping[tuple[str, int], View]:
    """Return every view this tool holds. No installed contract declares one yet."""
    return INSTALLED_VIEWS


def stated_shape(kind: str, major: int, record: Record) -> tuple[StatedShape, list[str]] | None:
    """Return the stated shape a record of the current major has, with what it lacks, if any."""
    for shape in STATED_SHAPES:
        if shape.kind == kind and shape.major == major and (lacking := shape.lacking(record)):
            return shape, lacking
    return None


def _leaves(value: Any, location: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from _leaves(child, (*location, str(key)))
    elif isinstance(value, list) and value:
        for index, child in enumerate(value):
            yield from _leaves(child, (*location, str(index)))
    else:
        yield location, value


def _value_at(value: Any, location: tuple[str, ...]) -> Any:
    for part in location:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return _MISSING
    return value


def _declared(location: tuple[str, ...], derived: tuple[str, ...]) -> bool:
    """Say whether a derived pointer covers a value, at it or above it."""
    for pattern in derived:
        parts = pointer_parts(pattern)
        if len(parts) <= len(location) and all(
            part in (ANY_POSITION, actual) for part, actual in zip(parts, location, strict=False)
        ):
            return True
    return False


_MISSING = object()
INSTALLED_VIEWS: dict[tuple[str, int], View] = {}

STATED_SHAPES: list[StatedShape] = []
