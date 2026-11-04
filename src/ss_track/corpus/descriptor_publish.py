"""Publish one complete descriptor generation, and recover an unfinished swap.

A reader of the published directory sees one generation, or no directory during the swap that
replaces it. The previous generation sits beside that directory until the new one is in place.
A scratch tree is never published: a killed write can be partial.
"""

import fcntl
import logging
import os
import shutil
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from ss_track.corpus.builder import CORPUS_DIRECTORY
from ss_track.corpus.sealed import SCRATCH_PREFIX

_LOG = logging.getLogger(__name__)
_DESCRIPTIONS = "descriptions"
_LOCK_NAME = ".describe.lock"
_RECOVERY_PREFIX = ".replaced-"
_STAGED = "staged"
_CROISSANT = "croissant.json"


def publish_descriptor(
    data_root: Path, corpus_id: str, visibility: str, output: Mapping[str, bytes]
) -> Path:
    """Publish one visibility and return the path of its Croissant document.

    The same bytes leave the published directory untouched. Different bytes are written aside
    and then swapped into place. An unfinished swap is put back before that.
    """
    parent = data_root / CORPUS_DIRECTORY / corpus_id / _DESCRIPTIONS
    target = parent / visibility
    recovery = parent / f"{_RECOVERY_PREFIX}{visibility}"
    with _exclusive(parent):
        _recover(target, recovery)
        _clear_scratch(parent)
        if _same(target, output):
            return target / _CROISSANT
        _install(parent, target, recovery, output)
    return target / _CROISSANT


@contextmanager
def _exclusive(parent: Path) -> Iterator[None]:
    """Serialize publication. The kernel drops this lock when the process ends."""
    parent.mkdir(parents=True, exist_ok=True)
    with (parent / _LOCK_NAME).open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _recover(target: Path, recovery: Path) -> None:
    """Put an unfinished swap back to one complete generation.

    Between the two renames the published name is absent and the previous tree is the recovery
    directory. After both renames the published tree is the new one and recovery is the previous
    generation, waiting to be removed.
    """
    if not recovery.exists():
        return
    if target.exists():
        _remove(recovery, required=True)
        return
    _rename(recovery, target)


def _clear_scratch(parent: Path) -> None:
    """Remove a killed run's scratch. The lock proves no other publication owns it."""
    for leftover in parent.glob(f"{SCRATCH_PREFIX}*"):
        shutil.rmtree(leftover)


def _same(target: Path, output: Mapping[str, bytes]) -> bool:
    if not target.is_dir():
        return False
    found = {
        path.relative_to(target).as_posix(): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
    }
    return found == dict(output)


def _install(parent: Path, target: Path, recovery: Path, output: Mapping[str, bytes]) -> None:
    with tempfile.TemporaryDirectory(prefix=SCRATCH_PREFIX, dir=parent) as temporary:
        staged = Path(temporary) / _STAGED
        staged.mkdir()
        _write_tree(staged, output)
        _fsync_directories(staged)
        _replace(staged, target, recovery)


def _replace(staged: Path, target: Path, recovery: Path) -> None:
    """Move the previous tree aside, then publish the staged tree by rename."""
    if not target.exists():
        _rename(staged, target)
        return
    _rename(target, recovery)
    try:
        _rename(staged, target)
    except BaseException:
        _restore(target, recovery)
        raise
    _remove(recovery, required=False)


def _restore(target: Path, recovery: Path) -> None:
    if not target.exists() and recovery.exists():
        _rename(recovery, target)


def _remove(path: Path, *, required: bool) -> None:
    """Drop a recovery tree. After a finished swap, failure leaves it for the next run."""
    try:
        shutil.rmtree(path)
    except OSError as error:
        if required:
            raise
        _LOG.warning(
            "could not remove descriptor recovery at %s: %s", path, error.strerror or "unknown"
        )
        return
    _fsync_dir(path.parent)


def _rename(source: Path, destination: Path) -> None:
    source.rename(destination)
    _fsync_dir(destination.parent)


def _write_tree(root: Path, output: Mapping[str, bytes]) -> None:
    for name, payload in output.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())


def _fsync_directories(root: Path) -> None:
    directories = [root, *(path for path in root.rglob("*") if path.is_dir())]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        _fsync_dir(directory)


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
