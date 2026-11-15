"""Small checks shared by labels, seeds and masks."""

from ss_track.corpus.declarations.fields import invalid


def require_unique(values: list[str], noun: str) -> None:
    """Refuse the first repeated value, naming it."""
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise invalid(f"duplicate {noun} {value}")
        seen.add(value)
