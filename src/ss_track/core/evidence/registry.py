"""Registrations for comparison projections."""

from collections.abc import Callable, Mapping
from typing import Any

from ss_track.core.refusal import JsonValue

type Projection = Callable[[Mapping[str, Any]], dict[str, JsonValue]]
PROJECTIONS: dict[tuple[str, int], Projection] = {}


def installed_projections() -> Mapping[tuple[str, int], Projection]:
    """Return the registered projections."""
    return PROJECTIONS


def register_projections(projections: Mapping[tuple[str, int], Projection]) -> None:
    """Install an area's projections without replacing another area's entries."""
    overlap = PROJECTIONS.keys() & projections.keys()
    if overlap:
        raise ValueError(f"duplicate projections: {sorted(overlap)}")
    PROJECTIONS.update(projections)
