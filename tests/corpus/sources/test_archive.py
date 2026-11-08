"""Network-free extraction safety and retry checks."""

import hashlib
import stat
import zipfile
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources.archive import extract_selected


def _zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def test_select_retry_conflict_and_budget(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    _zip(archive, {"videos/a.mp4": b"abc", "videos/b.mp4": b"other"})
    root = tmp_path / "output"
    expected = {"videos/a.mp4": hashlib.sha256(b"abc").hexdigest()}
    assert extract_selected(archive, root, {"videos/a.mp4"}, 3) == expected
    assert extract_selected(archive, root, {"videos/a.mp4"}, 3) == expected
    assert not (root / "videos/b.mp4").exists()
    with pytest.raises(CorpusRefusal, match="budget"):
        extract_selected(archive, root, {"videos/a.mp4"}, 2)
    (root / "videos/a.mp4").write_bytes(b"conflict")
    with pytest.raises(CorpusRefusal) as refusal:
        extract_selected(archive, root, {"videos/a.mp4"}, 3)
    assert refusal.value.code == RefusalCode.IMPORT_CONFLICT
    assert (root / "videos/a.mp4").read_bytes() == b"conflict"
    assert not list(root.rglob(".extract-*"))


@pytest.mark.parametrize(
    "name", ["../escape", "/absolute", "a/../escape", "a\\escape", "C:/escape"]
)
def test_refuses_unsafe_unselected_entry(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "source.zip"
    _zip(archive, {"safe.mp4": b"safe", name: b"bad"})
    with pytest.raises(CorpusRefusal, match="unsafe"):
        extract_selected(archive, tmp_path / "out", {"safe.mp4"}, 4)
    assert not (tmp_path / "out").exists()


def test_refuses_symlink_and_missing_selection(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(info, "elsewhere")
    with pytest.raises(CorpusRefusal, match="non-regular"):
        extract_selected(archive, tmp_path / "out", {"link"}, 100)
    _zip(archive, {"a.mp4": b"abc"})
    with pytest.raises(CorpusRefusal, match="missing"):
        extract_selected(archive, tmp_path / "out", {"b.mp4"}, 100)


def test_refuses_destination_symlink(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    _zip(archive, {"videos/a.mp4": b"abc"})
    root = tmp_path / "out"
    root.mkdir()
    (root / "videos").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(CorpusRefusal, match=r"escapes|symbolic link"):
        extract_selected(archive, root, {"videos/a.mp4"}, 3)
    assert not (tmp_path / "a.mp4").exists()
