"""Descriptor publication swaps one complete generation and recovers a killed swap."""

import errno
import logging
import os
import shutil
from pathlib import Path

import pytest

from ss_track.corpus.descriptors.descriptor_publish import publish_descriptor


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_identical_bytes_are_left_in_place(tmp_path: Path) -> None:
    output = {"croissant.json": b"v1\n", "nested/card.md": b"# v1\n"}
    first = publish_descriptor(tmp_path, "pilot-v1", "restricted", output)
    inode = first.stat().st_ino
    assert publish_descriptor(tmp_path, "pilot-v1", "restricted", output) == first
    assert first.stat().st_ino == inode
    assert _files(first.parent) == output
    assert not (first.parent / ".describe.lock").exists()
    assert (first.parent.parent / ".describe.lock").is_file()


def test_one_visibility_does_not_change_the_other(tmp_path: Path) -> None:
    restricted = {"croissant.json": b"restricted\n", "note.txt": b"secret-note\n"}
    publish_descriptor(tmp_path, "pilot-v1", "restricted", restricted)
    publish_descriptor(tmp_path, "pilot-v1", "public", {"croissant.json": b"public\n"})
    parent = tmp_path / "corpus" / "pilot-v1" / "descriptions"
    before = _files(parent / "restricted")
    publish_descriptor(tmp_path, "pilot-v1", "public", {"croissant.json": b"public-v2\n"})
    assert _files(parent / "restricted") == before
    assert _files(parent / "public") == {"croissant.json": b"public-v2\n"}
    assert not (parent / ".replaced-public").exists()
    assert not (parent / ".replaced-restricted").exists()


def test_failed_swap_restores_the_previous_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = {"croissant.json": b"v1\n", "old.txt": b"old\n"}
    new = {"croissant.json": b"v2\n", "new.txt": b"new\n"}
    manifest = publish_descriptor(tmp_path, "pilot-v1", "restricted", old)
    original = os.rename

    def rename(src: object, dst: object, *args: object, **kwargs: object) -> None:
        source = Path(os.fspath(src))  # type: ignore[arg-type]
        destination = Path(os.fspath(dst))  # type: ignore[arg-type]
        if source.name == "staged" and destination.name == "restricted":
            raise OSError(errno.EIO, "interrupted")
        original(src, dst, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "rename", rename)
    with pytest.raises(OSError, match="interrupted"):
        publish_descriptor(tmp_path, "pilot-v1", "restricted", new)
    parent = manifest.parent.parent
    assert _files(manifest.parent) == old
    assert not (parent / ".replaced-restricted").exists()
    assert list(parent.glob(".incoming-*")) == []


def test_a_killed_swap_does_not_publish_a_partial_tree(tmp_path: Path) -> None:
    old = {"croissant.json": b"v1\n", "old.txt": b"old\n"}
    new = {"croissant.json": b"v2\n", "new.txt": b"new\n"}
    manifest = publish_descriptor(tmp_path, "pilot-v1", "restricted", old)
    parent = manifest.parent.parent
    manifest.parent.rename(parent / ".replaced-restricted")
    scratch = parent / ".incoming-killed"
    scratch.mkdir()
    (scratch / "partial.txt").write_bytes(b"MIXED")
    publish_descriptor(tmp_path, "pilot-v1", "restricted", new)
    published = _files(parent / "restricted")
    assert published == new
    assert b"MIXED" not in b"".join(published.values())
    assert b"old\n" not in b"".join(published.values())
    assert not (parent / ".replaced-restricted").exists()
    assert list(parent.glob(".incoming-*")) == []


def test_a_published_tree_is_kept_when_recovery_remains(tmp_path: Path) -> None:
    manifest = publish_descriptor(tmp_path, "pilot-v1", "restricted", {"croissant.json": b"old\n"})
    parent = manifest.parent.parent
    recovery = parent / ".replaced-restricted"
    shutil.copytree(manifest.parent, recovery)
    manifest.write_bytes(b"new\n")
    (manifest.parent / "fresh.txt").write_bytes(b"fresh\n")
    output = {"croissant.json": b"new\n", "fresh.txt": b"fresh\n"}
    publish_descriptor(tmp_path, "pilot-v1", "restricted", output)
    assert _files(manifest.parent) == output
    assert not recovery.exists()
    inode = manifest.stat().st_ino
    assert publish_descriptor(tmp_path, "pilot-v1", "restricted", output) == manifest
    assert manifest.stat().st_ino == inode


def test_recovery_cleanup_failure_keeps_the_new_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    publish_descriptor(tmp_path, "pilot-v1", "restricted", {"croissant.json": b"old\n"})
    real = shutil.rmtree

    def rmtree(path: object, *args: object, **kwargs: object) -> None:
        if Path(os.fspath(path)).name.startswith(".replaced-"):  # type: ignore[arg-type]
            raise OSError(errno.EBUSY, "busy")
        real(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(shutil, "rmtree", rmtree)
    new = {"croissant.json": b"new\n"}
    with caplog.at_level(logging.WARNING):
        manifest = publish_descriptor(tmp_path, "pilot-v1", "restricted", new)
    parent = manifest.parent.parent
    assert _files(manifest.parent) == new
    assert (parent / ".replaced-restricted").is_dir()
    assert "could not remove descriptor recovery" in caplog.text
    monkeypatch.undo()
    inode = manifest.stat().st_ino
    publish_descriptor(tmp_path, "pilot-v1", "restricted", new)
    assert not (parent / ".replaced-restricted").exists()
    assert manifest.stat().st_ino == inode
    assert _files(manifest.parent) == new
