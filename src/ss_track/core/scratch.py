"""How a write reaches the data root: under a lock, through scratch, and by one rename.

A writer works in a name that starts with `SCRATCH_PREFIX` and publishes by rename, so a reader
never meets a partial file or directory. A run killed before its rename leaves that scratch behind.
The next run that holds the same lock removes it, because holding the lock proves that no live run
owns it. The kernel drops every lock here however the process ends.
"""

import fcntl
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from ss_track.core.refusal import CorpusRefusal, RefusalCode

SCRATCH_PREFIX = ".incoming-"
READ_ONLY_FILE_MODE = 0o444
READ_ONLY_DIRECTORY_MODE = 0o555
# Scratch holds this child, which is what moves: the emptied scratch is then removed on exit.
_STAGED = "staged"


@contextmanager
def exclusive_lock(
    folder: Path, name: str, *, clear: tuple[Path, ...] = (), busy: CorpusRefusal | None = None
) -> Iterator[None]:
    """Hold `folder/name` exclusively, then remove the scratch a killed run left in `clear`.

    Without `busy` this waits for the holder. With `busy`, a held lock raises that refusal.
    """
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if busy is not None else 0))
        except BlockingIOError as error:
            if busy is None:
                raise
            raise busy from error
        clear_scratch(*clear)
        yield


@contextmanager
def directory_lock(directory: Path) -> Iterator[None]:
    """Hold `directory` itself exclusively, so that no lock file is left inside it.

    A contract set and a data root are locked this way, because each holds only the files its
    contract names.
    """
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


@contextmanager
def shared_lock(folder: Path, name: str, *, clear: tuple[Path, ...] = ()) -> Iterator[None]:
    """Hold `folder/name` shared. A run that finds no other holder first clears `clear`.

    Every writer of those folders holds this lock while its scratch exists, so a run that can take
    it exclusively knows that no scratch there is live. Turning that lock into a shared one is not
    atomic, and nothing of this run exists during the gap.
    """
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            clear_scratch(*clear)
        fcntl.flock(handle, fcntl.LOCK_SH)
        yield


def clear_scratch(*folders: Path) -> None:
    """Remove every scratch file and directory a killed run left in `folders`.

    The caller holds the lock that every writer of those folders takes.
    """
    for folder in folders:
        for leftover in folder.glob(f"{SCRATCH_PREFIX}*"):
            if leftover.is_dir() and not leftover.is_symlink():
                shutil.rmtree(leftover)
            else:
                leftover.unlink()


@contextmanager
def scratch_directory(parent: Path) -> Iterator[Path]:
    """Yield an empty directory to fill and then rename into place inside `parent`.

    Whatever was not renamed away is removed on exit, including after an error or an interrupt.
    """
    with TemporaryDirectory(prefix=SCRATCH_PREFIX, dir=parent) as scratch:
        staged = Path(scratch) / _STAGED
        staged.mkdir()
        yield staged


def write_atomically(path: Path, payload: bytes, *, mode: int | None = None) -> None:
    """Replace one file with `payload`, so a crash cannot leave a partial file in its place.

    The bytes reach the disk before the rename. `mode`, when given, is set before the rename. A
    failure at any step removes the scratch file and raises.
    """
    with NamedTemporaryFile(dir=path.parent, prefix=SCRATCH_PREFIX, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if mode is not None:
            temporary.chmod(mode)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def holds_payload(path: Path, payload: bytes) -> bool:
    """Return whether `path` already holds exactly `payload`, refusing anything else there.

    A path that holds other bytes, or is not a file, is `CORPUS_CONFLICT`: a write-once output is
    never replaced, so the caller chooses another path.
    """
    if not path.exists():
        return False
    if path.is_file() and path.read_bytes() == payload:
        return True
    raise CorpusRefusal(
        RefusalCode.CORPUS_CONFLICT,
        "the output path already holds something else; choose another path",
        {"path": str(path)},
    )


def write_once(path: Path, payload: bytes, *, mode: int | None = None) -> bool:
    """Write a file once and return whether it was written.

    The same bytes again change nothing. Other bytes at that path are refused, not replaced.
    """
    if holds_payload(path, payload):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, payload, mode=mode)
    return True
