"""The registered kinds of reproducible artifact `ss-track data clean` may remove.

A kind names the bytes it removes, the target an operator names (a corpus version, a run, or none),
how the bytes are made again, and the lock its writer holds, so a live command is never cleaned
under. Register a new kind here, with a test of its plan, removal and restore, in the change that
first writes such an artifact.
"""

import fcntl
import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from ss_track.core.clean_kinds import SCRATCH_KIND, CleanKind
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.core.scratch import SCRATCH_PREFIX, exclusive_lock
from ss_track.corpus.storage.layout import (
    DISCOVERY_DIRECTORY,
    corpus_manifest_path,
    discovery_run_directory,
    frame_set_path,
    frames_root,
)

ACQUISITION_RECORD = "acquisition.json"
ACQUISITION_LOCK = ".acquisition.lock"
ACQUISITION_CACHE = "cache"
ACQUISITION_SCRATCH = "scratch"
STAGING_LOCK = ".staging.lock"
LOCK_SUFFIX = ".lock"
TOOL_CACHES = ("complexipy", "mypy", "pytest", "ruff")
CACHE_DIRECTORY = "cache"


def _staged_frames(data_root: Path, corpus_id: str | None) -> list[Path]:
    assert corpus_id is not None
    if not corpus_manifest_path(data_root, corpus_id).is_file():
        raise CorpusRefusal(
            RefusalCode.CORPUS_NOT_BUILT, "no built corpus version", {"corpus_id": corpus_id}
        )
    if not frame_set_path(data_root, corpus_id).is_file():
        raise CorpusRefusal(
            RefusalCode.FRAME_SET_NOT_STAGED,
            "the corpus version has no sealed frame set to stage again",
            {"corpus_id": corpus_id},
        )
    root = frames_root(data_root, corpus_id)
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if not path.name.startswith("."))


@contextmanager
def _staging_locked(data_root: Path, corpus_id: str | None) -> Iterator[None]:
    assert corpus_id is not None
    busy = CorpusRefusal(
        RefusalCode.STAGING_IN_PROGRESS,
        "another run is staging this corpus version",
        {"corpus_id": corpus_id},
    )
    with exclusive_lock(frames_root(data_root, corpus_id), STAGING_LOCK, busy=busy):
        yield


def _acquisition_cache(data_root: Path, run_id: str | None) -> list[Path]:
    assert run_id is not None
    root = discovery_run_directory(data_root, run_id)
    if not (root / ACQUISITION_RECORD).is_file():
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "the run holds no sealed acquisition",
            {"run_id": run_id},
        )
    cache = root / ACQUISITION_CACHE
    return sorted(cache.iterdir()) if cache.is_dir() else []


@contextmanager
def _acquisition_locked(data_root: Path, run_id: str | None) -> Iterator[None]:
    assert run_id is not None
    busy = CorpusRefusal(
        RefusalCode.DATA_ROOT_BUSY, "an acquisition of this run is active", {"run_id": run_id}
    )
    with exclusive_lock(discovery_run_directory(data_root, run_id), ACQUISITION_LOCK, busy=busy):
        yield


def _scratch(data_root: Path, _target: str | None) -> list[Path]:
    found: list[Path] = []
    for folder, directories, files in _walk(data_root):
        for name in (*directories, *files):
            if name.startswith(SCRATCH_PREFIX):
                found.append(folder / name)
        directories[:] = [name for name in directories if not name.startswith(SCRATCH_PREFIX)]
    for acquisition in sorted((data_root / DISCOVERY_DIRECTORY).glob(f"*/{ACQUISITION_SCRATCH}")):
        if (acquisition.parent / ACQUISITION_RECORD).is_file() and acquisition.is_dir():
            found.extend(sorted(acquisition.iterdir()))
    return sorted(set(found))


@contextmanager
def _every_lock_free(data_root: Path, _target: str | None) -> Iterator[None]:
    """Hold every lock file in the data root, so no writer owns the scratch being removed."""
    with ExitStack() as held:
        for path in sorted(_lock_files(data_root)):
            handle = held.enter_context(path.open("a"))
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise CorpusRefusal(
                    RefusalCode.DATA_ROOT_BUSY,
                    "a command holds a lock in this data root",
                    {"lock": path.relative_to(data_root).as_posix()},
                ) from error
        yield


def _lock_files(data_root: Path) -> list[Path]:
    return [
        folder / name
        for folder, _directories, files in _walk(data_root)
        for name in files
        if name.startswith(".") and name.endswith(LOCK_SUFFIX)
    ]


def _walk(data_root: Path) -> Iterator[tuple[Path, list[str], list[str]]]:
    for folder, directories, files in os.walk(data_root):
        yield Path(folder), directories, files


def _tool_caches(data_root: Path, _target: str | None) -> list[Path]:
    return [
        path
        for name in TOOL_CACHES
        if (path := data_root / CACHE_DIRECTORY / name).is_dir() and not path.is_symlink()
    ]


@contextmanager
def _unlocked(_data_root: Path, _target: str | None) -> Iterator[None]:
    yield


KINDS: dict[str, CleanKind] = {
    kind.name: kind
    for kind in (
        CleanKind(
            "staged-frames",
            "corpus",
            "ss-track corpus stage --corpus {target} stages the same frame set again",
            _staged_frames,
            _staging_locked,
        ),
        CleanKind(
            "acquisition-cache",
            "run",
            "repeat the run's ss-track discover acquire command; it transfers the archive again",
            _acquisition_cache,
            _acquisition_locked,
        ),
        CleanKind(
            SCRATCH_KIND,
            None,
            "nothing: scratch is what a killed command left behind",
            _scratch,
            _every_lock_free,
        ),
        CleanKind(
            "tool-caches",
            None,
            "the next make target recreates the ruff, mypy, pytest and complexipy caches",
            _tool_caches,
            _unlocked,
        ),
    )
}
