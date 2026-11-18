"""The data roots one command has checked, and when a walk of an unstamped root may be reused.

Each check of a root without `contract-set.json` walks the whole root for sealed-looking files
(`core.evidence.unstamped`). Inside one command, entered with `one_command`, a later check of the
same root reuses a clean walk when no sealed read or write of a path under that root came between
them. A read or a write is where another writer's record would matter, so either ends the reuse for
every checked root that holds its path. Outside a command, every check walks.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CheckedRoot:
    """One root this command checked, as resolved, and whether it had no stamp when checked."""

    root: Path
    unstamped: bool
    walked_in: object | None = None  # the command whose clean walk a later check may reuse


# A check of one root never drops another, so a nested check cannot stop the outer root's stamping.
_CHECKED: ContextVar[tuple[CheckedRoot, ...]] = ContextVar("checked_data_roots", default=())
_COMMAND: ContextVar[object | None] = ContextVar("checking_command", default=None)


@contextmanager
def one_command() -> Iterator[None]:
    """Let checks of an unstamped root inside this block reuse a clean walk."""
    token = _COMMAND.set(object())
    try:
        yield
    finally:
        _COMMAND.reset(token)


def remember(root: Path, unstamped: bool | None, *, walked: bool = False) -> None:
    """Record resolved `root` as checked, or forget it when `unstamped` is None.

    `walked` says a clean walk found no record just now, so this command may reuse it.
    """
    kept = tuple(item for item in _CHECKED.get() if item.root != root)
    if unstamped is None:
        _CHECKED.set(kept)
        return
    walked_in = _COMMAND.get() if walked else None
    _CHECKED.set((*kept, CheckedRoot(root, unstamped, walked_in)))


def reusable_walk(root: Path) -> bool:
    """Say whether resolved `root` had a clean walk in this command with no read or write since."""
    command = _COMMAND.get()
    return command is not None and any(
        item.root == root and item.unstamped and item.walked_in is command
        for item in _CHECKED.get()
    )


def end_reuse(path: Path) -> None:
    """Open a read or write window at `path`: the next check of a root holding it walks again."""
    _CHECKED.set(
        tuple(
            replace(item, walked_in=None) if holds_path(item.root, path) else item
            for item in _CHECKED.get()
        )
    )


def holding(path: Path) -> CheckedRoot | None:
    """Return the most specific checked root that holds `path`, directly or through a link."""
    found = [item for item in _CHECKED.get() if holds_path(item.root, path)]
    return max(found, key=lambda item: len(item.root.parts), default=None)


def holds_path(root: Path, path: Path) -> bool:
    """Return whether `path` lies under `root`, as spelled or through a link on either side."""
    spellings = (path.absolute(), path.resolve())
    return any(
        spelling.is_relative_to(base)
        for base in {root.absolute(), root.resolve()}
        for spelling in spellings
    )
