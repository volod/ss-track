"""Small checks shared by packs, labels, seeds and masks."""

from collections.abc import Iterable

from ss_track.corpus.declarations.fields import invalid


def first_duplicate(values: Iterable[str]) -> str | None:
    """Return the first value that repeats, or ``None`` when every value is unique."""
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None


def require_unique(values: Iterable[str], noun: str) -> None:
    """Refuse the first repeated value, naming it."""
    found = first_duplicate(values)
    if found is not None:
        raise invalid(f"duplicate {noun} {found}")
