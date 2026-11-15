"""Registry of removable, reproducible artifact kinds.

Each area registers the kinds it writes when it is imported. The developer tool caches belong to
no area, so they are registered here.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path

SCRATCH_KIND = "scratch"
TOOL_CACHES_KIND = "tool-caches"
CACHE_DIRECTORY = "cache"  # the Makefile's $(DATA_ROOT)/cache
TOOL_CACHES = ("complexipy", "mypy", "pytest", "ruff")

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


def _tool_caches(data_root: Path, _target: str | None) -> list[Path]:
    return [
        path
        for name in TOOL_CACHES
        if (path := data_root / CACHE_DIRECTORY / name).is_dir() and not path.is_symlink()
    ]


@contextmanager
def _unlocked(_data_root: Path, _target: str | None) -> Iterator[None]:
    yield


register_kinds(
    {
        TOOL_CACHES_KIND: CleanKind(
            TOOL_CACHES_KIND,
            None,
            "the next make target recreates the ruff, mypy, pytest and complexipy caches",
            _tool_caches,
            _unlocked,
        )
    }
)
