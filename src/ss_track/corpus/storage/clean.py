"""`ss-track data clean`: remove registered kinds of reproducible artifact from one data root.

Each kind states what it removes, how the bytes are made again and which lock keeps a live command
away. Only named kinds and named targets are touched, nothing is removed until the operator applies
the plan, and no kind holds a sealed record, an imported source copy, a declaration or a review
decision. A task that adds a disposable artifact registers its kind in `clean_kinds.py`.
"""

import os
import shutil
import stat
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.storage.clean_kinds import KINDS, SCRATCH_KIND, CleanKind

PLANNED = "planned"
CLEANED = "cleaned"


@dataclass(frozen=True, slots=True)
class Entry:
    """One file or directory a kind would remove, with the bytes it holds."""

    path: Path
    size_bytes: int


@dataclass(frozen=True, slots=True)
class KindPlan:
    """What one kind removes for one target, and how to make it again."""

    kind: str
    target: str | None
    restore: str
    entries: tuple[Entry, ...]

    @property
    def size_bytes(self) -> int:
        return sum(entry.size_bytes for entry in self.entries)


class CleanResult:
    """The plan, and whether it was applied."""

    def __init__(self, applied: bool, plans: tuple[KindPlan, ...], data_root: Path) -> None:
        self.applied = applied
        self.plans = plans
        self.data_root = data_root

    def to_record(self) -> dict[str, object]:
        """Return the command result: every kind's entries, bytes and restore path."""
        return {
            "status": CLEANED if self.applied else PLANNED,
            "clean": {
                "applied": self.applied,
                "total_bytes": sum(plan.size_bytes for plan in self.plans),
                "kinds": [self._plan(plan) for plan in self.plans],
            },
        }

    def _plan(self, plan: KindPlan) -> dict[str, object]:
        return {
            "kind": plan.kind,
            "target": plan.target,
            "restore": plan.restore,
            "bytes": plan.size_bytes,
            "entries": [
                {
                    "path": entry.path.relative_to(self.data_root).as_posix(),
                    "bytes": entry.size_bytes,
                }
                for entry in plan.entries
            ],
        }


def clean_data_root(
    data_root: Path,
    kinds: list[str],
    *,
    corpora: list[str],
    runs: list[str],
    apply: bool,
) -> CleanResult:
    """Plan the named kinds over their targets, and remove the entries when `apply` is set."""
    root = data_root.resolve()
    requests = _requests(kinds, corpora, runs)
    with ExitStack() as locks:
        plans = []
        for kind, target in requests:
            kind.collect(root, target)  # refuse an unknown target before its lock creates folders
            locks.enter_context(kind.locked(root, target))
            entries = tuple(_entry(root, path) for path in kind.collect(root, target))
            plans.append(KindPlan(kind.name, target, kind.restore_for(target), entries))
        if apply:
            for plan in plans:
                for entry in plan.entries:
                    _remove(entry.path)
    return CleanResult(apply, tuple(plans), root)


def _requests(
    kinds: list[str], corpora: list[str], runs: list[str]
) -> list[tuple[CleanKind, str | None]]:
    _require_kinds(kinds)
    targets: dict[str | None, list[str | None]] = {
        "corpus": list(sorted(set(corpora))),
        "run": list(sorted(set(runs))),
        None: [None],
    }
    requests: list[tuple[CleanKind, str | None]] = []
    for name in sorted(set(kinds)):
        kind = KINDS[name]
        named = targets[kind.target]
        if kind.target is not None and not named:
            raise CorpusRefusal(
                RefusalCode.MANIFEST_INVALID,
                f"kind {name} needs at least one --{kind.target}",
                {"kind": name},
            )
        requests.extend((kind, target) for target in named)
    used = {kind.target for kind, _target in requests}
    for option, values in (("corpus", corpora), ("run", runs)):
        if values and option not in used:
            raise CorpusRefusal(
                RefusalCode.MANIFEST_INVALID,
                f"--{option} names a target no requested kind uses",
                {"option": option},
            )
    return requests


def _require_kinds(kinds: list[str]) -> None:
    unknown = sorted(set(kinds) - set(KINDS))
    if unknown or not kinds:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "name at least one known kind to clean",
            {"unknown": _json_list(unknown), "known": _json_list(sorted(KINDS))},
        )
    if SCRATCH_KIND in kinds and len(set(kinds)) > 1:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "clean scratch on its own: it holds every lock in the data root",
            {"kinds": _json_list(sorted(set(kinds)))},
        )


def _json_list(values: list[str]) -> JsonValue:
    return list[JsonValue](values)


def _entry(root: Path, path: Path) -> Entry:
    if path.is_symlink() or root not in path.parents:
        raise CorpusRefusal(
            RefusalCode.STORAGE_FAILED,
            "a clean entry is a link or lies outside the data root",
            {"path": str(path)},
        )
    return Entry(path, _size(path))


def _size(path: Path) -> int:
    if not path.is_dir():
        return path.lstat().st_size
    total = 0
    for folder, _directories, files in os.walk(path):
        total += sum((Path(folder) / name).lstat().st_size for name in files)
    return total


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        _writable(path)
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _writable(path: Path) -> None:
    """Let the owner unlink inside read-only bundle directories before they are removed."""
    for folder, _directories, _files in os.walk(path):
        mode = Path(folder).lstat().st_mode
        Path(folder).chmod(stat.S_IMODE(mode) | stat.S_IWUSR | stat.S_IXUSR)
