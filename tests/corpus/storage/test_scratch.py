"""One way to write on the data root: a lock, scratch a killed run left removed, one rename."""

import fcntl
import os
import stat
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.storage.scratch import (
    READ_ONLY_FILE_MODE,
    SCRATCH_PREFIX,
    clear_scratch,
    exclusive_lock,
    scratch_directory,
    shared_lock,
    write_atomically,
)

_LOCK = ".test.lock"


def _leftovers(folder: Path) -> tuple[Path, Path]:
    """Leave a killed run's scratch file and scratch directory, each holding read-only bytes."""
    folder.mkdir(parents=True, exist_ok=True)
    partial = folder / f"{SCRATCH_PREFIX}partial"
    partial.write_bytes(b"half")
    directory = folder / f"{SCRATCH_PREFIX}killed" / "staged"
    directory.mkdir(parents=True)
    (directory / "frame").write_bytes(b"raw")
    (directory / "frame").chmod(READ_ONLY_FILE_MODE)
    return partial, directory.parent


def test_clearing_removes_scratch_files_and_directories_and_nothing_else(tmp_path: Path) -> None:
    partial, directory = _leftovers(tmp_path)
    kept = tmp_path / "kept"
    kept.write_bytes(b"kept")

    clear_scratch(tmp_path, tmp_path / "absent")

    assert not partial.exists()
    assert not directory.exists()
    assert kept.read_bytes() == b"kept"


def test_an_exclusive_lock_clears_scratch_and_a_held_one_refuses(tmp_path: Path) -> None:
    folder = tmp_path / "made" / "here"
    busy = CorpusRefusal(RefusalCode.STAGING_IN_PROGRESS, "busy")
    with exclusive_lock(folder, _LOCK):
        partial, directory = _leftovers(folder)
        with pytest.raises(CorpusRefusal) as caught, exclusive_lock(folder, _LOCK, busy=busy):
            pass
        assert caught.value is busy
        assert partial.exists()

    with exclusive_lock(folder, _LOCK, clear=(folder,), busy=busy):
        assert not partial.exists()
        assert not directory.exists()


def test_a_shared_lock_clears_scratch_only_when_no_other_run_holds_it(tmp_path: Path) -> None:
    partial, directory = _leftovers(tmp_path)
    with (tmp_path / _LOCK).open("w") as other:
        fcntl.flock(other, fcntl.LOCK_SH)
        with shared_lock(tmp_path, _LOCK, clear=(tmp_path,)):
            assert partial.exists()
            assert directory.exists()

    with shared_lock(tmp_path, _LOCK, clear=(tmp_path,)):
        assert not partial.exists()
        assert not directory.exists()


def test_a_scratch_directory_leaves_nothing_once_its_child_has_moved(tmp_path: Path) -> None:
    with scratch_directory(tmp_path) as staged:
        assert staged.name == "staged"
        assert staged.parent.name.startswith(SCRATCH_PREFIX)
        (staged / "file").write_bytes(b"done")
        staged.rename(tmp_path / "published")

    assert [path.name for path in tmp_path.iterdir()] == ["published"]


def test_an_atomic_write_replaces_the_file_with_the_mode_it_names(tmp_path: Path) -> None:
    target = tmp_path / "record.json"
    target.write_bytes(b"old")

    write_atomically(target, b"new", mode=READ_ONLY_FILE_MODE)

    assert target.read_bytes() == b"new"
    assert stat.S_IMODE(target.stat().st_mode) == READ_ONLY_FILE_MODE
    assert [path.name for path in tmp_path.iterdir()] == ["record.json"]


@pytest.mark.parametrize("where", ["fsync", "replace"])
@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_a_failed_or_interrupted_write_leaves_the_old_file_and_no_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str, failure: type[BaseException]
) -> None:
    target = tmp_path / "sheet.png"
    target.write_bytes(b"old")

    def stop(*_args: object, **_kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(os, where, stop)

    with pytest.raises(failure):
        write_atomically(target, b"new")

    assert target.read_bytes() == b"old"
    assert list(tmp_path.glob(f"{SCRATCH_PREFIX}*")) == []
