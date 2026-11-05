"""Publish finished bundle directories by rename, or leave nothing behind."""

import shutil
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from ss_track.corpus.records.sealing import READ_ONLY_DIRECTORY_MODE, SCRATCH_PREFIX


@contextmanager
def publish_bundle(root: Path, target: Path) -> Iterator[Path]:
    """Yield a scratch directory and publish it complete by one rename, or leave nothing."""
    with publish_bundles(root, (target,)) as (staged,):
        yield staged


@contextmanager
def publish_bundles(root: Path, targets: Sequence[Path]) -> Iterator[tuple[Path, ...]]:
    """Yield one scratch directory per target and publish all of them, or leave none.

    Renames run only after the caller has finished writing. A rename that fails, or an
    interruption while the directories are moving, removes every target this attempt already
    published. Scratch that never moved is removed with its temporary directory.
    """
    with ExitStack() as stack:
        staged_dirs = tuple(_scratch_dir(stack, root) for _target in targets)
        yield staged_dirs
        _rename_all(staged_dirs, targets)
    for target in targets:
        target.chmod(READ_ONLY_DIRECTORY_MODE)


def _scratch_dir(stack: ExitStack, root: Path) -> Path:
    scratch = stack.enter_context(TemporaryDirectory(prefix=SCRATCH_PREFIX, dir=root))
    staged = Path(scratch) / "staged"
    staged.mkdir()
    return staged


def _rename_all(staged_dirs: Sequence[Path], targets: Sequence[Path]) -> None:
    """Move every staged directory into place, rolling back a pass that stops halfway."""
    published: list[Path] = []
    try:
        for staged, target in zip(staged_dirs, targets, strict=True):
            staged.rename(target)
            published.append(target)
    except BaseException:
        for path in published:
            shutil.rmtree(path)
        raise
