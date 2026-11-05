"""A frame that matches its parent is a hard link, including across the scratch rename."""

import errno
from pathlib import Path

import pytest

from ss_track.core.canonical import sha256_bytes
from ss_track.corpus.bundles import frame_store
from ss_track.corpus.bundles.frame_store import store_frame
from ss_track.corpus.bundles.frames import frame_name
from ss_track.corpus.bundles.publish import publish_bundle
from ss_track.corpus.decoding.pixels import OUTPUT_PIXEL_FORMAT


def _parent(tmp_path: Path, pixels: bytes) -> Path:
    directory = tmp_path / "parent"
    directory.mkdir()
    source = directory / frame_name(3, OUTPUT_PIXEL_FORMAT)
    source.write_bytes(pixels)
    return source


def test_a_shared_frame_keeps_its_inode_when_scratch_is_published(tmp_path: Path) -> None:
    pixels = b"\x01\x02\x03" * 20
    source = _parent(tmp_path, pixels)
    digest = sha256_bytes(pixels)
    root = tmp_path / "frames"
    root.mkdir()

    with publish_bundle(root, root / "case") as staged:
        entry = store_frame(staged, 3, 40, pixels, link_from=source, link_sha256=digest)

    published = root / "case" / frame_name(3, OUTPUT_PIXEL_FORMAT)
    assert entry == {"frame_index": 3, "pts": 40, "sha256": digest}
    assert published.stat().st_ino == source.stat().st_ino
    assert published.stat().st_nlink == 2
    assert published.read_bytes() == pixels
    assert published.stat().st_mode & 0o777 == 0o444
    assert (root / "case").stat().st_mode & 0o777 == 0o555
    assert list(root.glob(".incoming-*")) == []


def test_a_different_hash_is_a_new_file(tmp_path: Path) -> None:
    source = _parent(tmp_path, b"\x01" * 12)
    pixels = b"\x02" * 12
    directory = tmp_path / "case"
    directory.mkdir()

    entry = store_frame(
        directory, 1, None, pixels, link_from=source, link_sha256=sha256_bytes(source.read_bytes())
    )

    stored = directory / frame_name(1, OUTPUT_PIXEL_FORMAT)
    assert stored.stat().st_ino != source.stat().st_ino
    assert stored.read_bytes() == pixels
    assert entry["sha256"] == sha256_bytes(pixels)
    assert source.stat().st_nlink == 1


def test_a_parent_whose_size_changed_is_copied(tmp_path: Path) -> None:
    source = _parent(tmp_path, b"short")
    pixels = b"abcdefghij"
    directory = tmp_path / "case"
    directory.mkdir()

    store_frame(directory, 1, 0, pixels, link_from=source, link_sha256=sha256_bytes(pixels))

    stored = directory / frame_name(1, OUTPUT_PIXEL_FORMAT)
    assert stored.stat().st_ino != source.stat().st_ino
    assert stored.read_bytes() == pixels


@pytest.mark.parametrize(
    "code",
    [errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP, errno.EMLINK],
)
def test_a_filesystem_that_refuses_links_stores_a_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    pixels = b"\x04" * 16
    source = _parent(tmp_path, pixels)
    directory = tmp_path / "case"
    directory.mkdir()

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(code, "link refused")

    monkeypatch.setattr(frame_store.os, "link", refuse)
    entry = store_frame(directory, 3, 8, pixels, link_from=source, link_sha256=sha256_bytes(pixels))

    stored = directory / frame_name(3, OUTPUT_PIXEL_FORMAT)
    assert stored.stat().st_ino != source.stat().st_ino
    assert stored.read_bytes() == pixels
    assert entry["sha256"] == sha256_bytes(pixels)
    assert source.stat().st_nlink == 1


def test_a_link_error_other_than_a_filesystem_refusal_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pixels = b"\x05" * 8
    source = _parent(tmp_path, pixels)
    directory = tmp_path / "case"
    directory.mkdir()

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(frame_store.os, "link", refuse)

    with pytest.raises(OSError) as caught:
        store_frame(directory, 3, 8, pixels, link_from=source, link_sha256=sha256_bytes(pixels))

    assert caught.value.errno == errno.EIO
    assert not (directory / frame_name(3, OUTPUT_PIXEL_FORMAT)).exists()
