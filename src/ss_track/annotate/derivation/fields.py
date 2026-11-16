"""Typed reads of a generated case and its stored label transform.

A corpus manifest's contract already accepted these values. A wrong type here is a record that
was resealed by hand, and it is refused rather than guessed.
"""

from collections.abc import Mapping

from ss_track.annotate.derivation.geom import Rect
from ss_track.corpus.declarations.fields import invalid


def integer(value: object, where: str) -> int:
    """Return an integer. A boolean is not one."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid(f"{where} is not an integer")
    return value


def text(holder: Mapping[str, object], name: str) -> str:
    """Return one non-empty string field."""
    found = holder.get(name)
    if not isinstance(found, str) or not found:
        raise invalid(f"{name} is not text")
    return found


def mapping(value: object, where: str) -> Mapping[str, object]:
    """Return one object."""
    if not isinstance(value, Mapping):
        raise invalid(f"{where} is not an object")
    return value


def rows(holder: Mapping[str, object], name: str) -> list[Mapping[str, object]]:
    """Return one list of objects."""
    raw = holder.get(name)
    if not isinstance(raw, list):
        raise invalid(f"{name} is not a list")
    return [mapping(item, f"{name} entry") for item in raw]


def integers(holder: Mapping[str, object], name: str) -> list[int]:
    """Return one list of integers."""
    raw = holder.get(name)
    if not isinstance(raw, list):
        raise invalid(f"{name} is not a list")
    return [integer(item, name) for item in raw]


def rect(value: object, where: str = "region") -> Rect:
    """Return one stored rectangle."""
    found = mapping(value, where)
    return Rect(
        integer(found.get("x"), "x"),
        integer(found.get("y"), "y"),
        integer(found.get("width"), "width"),
        integer(found.get("height"), "height"),
    )


def window(holder: Mapping[str, object], name: str) -> range:
    """Return the half-open frame window one field states."""
    found = mapping(holder.get(name), name)
    return range(
        integer(found.get("start_frame"), "start_frame"),
        integer(found.get("end_frame"), "end_frame"),
    )
