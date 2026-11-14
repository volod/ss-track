"""Registry of removable, reproducible artifact kinds."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

SCRATCH_KIND = "scratch"

Collect = Callable[[Path, str | None], list[Path]]
Locked = Callable[[Path, str | None], AbstractContextManager[None]]


@dataclass(frozen=True, slots=True)
class CleanKind:
    """One registered kind: what it removes, for which target, and how it is restored."""

    name: str
    target: str | None
    restore: str
    collect: Collect
    locked: Locked

    def restore_for(self, target: str | None) -> str:
        return self.restore.format(target=target)


KINDS: dict[str, CleanKind] = {}


def register_kinds(kinds: dict[str, CleanKind]) -> None:
    """Register an area's kinds, refusing conflicting registrations."""
    overlap = KINDS.keys() & kinds.keys()
    if overlap:
        raise ValueError(f"duplicate clean kinds: {sorted(overlap)}")
    KINDS.update(kinds)
