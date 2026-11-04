"""Strict JSON decoder hooks shared by documents and contract files; no file-reading entrypoint."""

import math


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Refuse duplicate keys instead of silently taking the last value."""
    document = dict(pairs)
    if len(document) != len(pairs):
        raise ValueError("a key is repeated")
    return document


def reject_constant(name: str) -> None:
    """Refuse Python's non-JSON NaN and infinity literals."""
    raise ValueError(f"{name} is not JSON")


def finite_float(text: str) -> float:
    """Refuse exponent overflow as well as literal infinity."""
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite numbers are not JSON")
    return value
