"""A generated case hard-links frames it does not change, and verification still names damage."""

import errno
import shutil
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    open_frame_bundle,
)
from ss_track.corpus.bundles import frame_store
from ss_track.corpus.bundles.frame_store import require_space
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.cases import generated
from ss_track.corpus.cases.generated import write_case_bundle
from ss_track.corpus.versions.manifests import load_corpus_manifest
from tests.corpus._media import FRAME_COUNT, HEIGHT, WIDTH
from tests.corpus.bundles._staged_frames import flip_byte, frames_refusal
from tests.corpus.cases._staged_cases import stage_cases
from tests.corpus.conftest import WriteCorpus, case_of

_WINDOW = {"start_frame": 6, "end_frame": 16}
_CHANGED = range(6, 16)
_BLUR = {"max_radius": 2}


def _files(bundle: FrameBundle) -> list[Path]:
    return [bundle.directory / ref.frame_name for ref in bundle.frame_refs()]


def _allocated(path: Path) -> int:
    """Return the bytes this inode occupies. A hard link reports the full inode, once."""
    stat = path.stat()
    blocks = stat.st_blocks * 512
    return blocks if blocks else stat.st_size


def _unique_bytes(paths: list[Path]) -> int:
    seen: set[tuple[int, int]] = set()
    total = 0
    for path in paths:
        stat = path.stat()
        key = (stat.st_dev, stat.st_ino)
        if key in seen:
            continue
        seen.add(key)
        total += _allocated(path)
    return total


def _blur(case_id: str = "blurred") -> dict[str, object]:
    return case_of(case_id, "blur", 1, _BLUR, window=_WINDOW)


def test_a_short_window_shares_untouched_frames_and_matches_a_copy(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = stage_cases(imported, write_corpus, data_root, _blur())
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "blurred")
    _assert_window_links(parent, case)
    added, untouched = _disk_delta(parent, case)
    assert added == len(_CHANGED) * _allocated(_files(parent)[0])
    assert untouched == (FRAME_COUNT - len(_CHANGED)) * _allocated(_files(parent)[0])
    assert added + untouched == sum(_allocated(path) for path in _files(case))

    monkeypatch.setattr(frame_store.os, "link", _refuse_link)
    case_record = load_corpus_manifest("pilot-v1", data_root)["generated_cases"][0]
    assert isinstance(case_record, dict)
    other = tmp_path / "unlinked"
    other.mkdir()
    copied = write_case_bundle(case_record, parent, other)

    assert copied.bundle_sha256 == case.bundle_sha256
    assert [item.sha256 for item in copied.frame_refs()] == [
        item.sha256 for item in case.frame_refs()
    ]
    for ref in copied.frame_refs():
        assert copied.read_frame(ref.frame_index) == case.read_frame(ref.frame_index)
        parent_file = parent.directory / parent.frame_ref(ref.content_frame_index).frame_name
        assert (copied.directory / ref.frame_name).stat().st_ino != parent_file.stat().st_ino


def _assert_window_links(parent: FrameBundle, case: FrameBundle) -> None:
    for ref in case.frame_refs():
        case_file = case.directory / ref.frame_name
        parent_file = parent.directory / parent.frame_ref(ref.frame_index).frame_name
        assert (case_file.stat().st_ino == parent_file.stat().st_ino) is (
            ref.frame_index not in _CHANGED
        )


def _disk_delta(parent: FrameBundle, case: FrameBundle) -> tuple[int, int]:
    """Return bytes the case added, and bytes of its frames that share the parent's inodes."""
    parent_files = _files(parent)
    added = _unique_bytes(parent_files + _files(case)) - _unique_bytes(parent_files)
    untouched = sum(
        _allocated(case.directory / ref.frame_name)
        for ref in case.frame_refs()
        if ref.frame_index not in _CHANGED
    )
    return added, untouched


def _refuse_link(*_args: object, **_kwargs: object) -> None:
    raise OSError(errno.EXDEV, "Invalid cross-device link")


def test_a_repeated_frame_links_to_the_frame_it_shows(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("repeated", "duplicated_frames", 1, {"count": 3}, window=_WINDOW),
    )
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "repeated")

    for ref in case.frame_refs():
        shown = parent.directory / parent.frame_ref(ref.content_frame_index).frame_name
        assert (case.directory / ref.frame_name).stat().st_ino == shown.stat().st_ino
    assert _unique_bytes(_files(parent) + _files(case)) == _unique_bytes(_files(parent))


def test_verify_names_a_damaged_frame_the_case_copied(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(imported, write_corpus, data_root, _blur())
    flip_byte(root / "blurred" / "00000006.rgb24")

    assert frames_refusal(data_root).details["frames"] == [
        {"stream_id": "blurred", "frame": "00000006.rgb24", "reason": "hash_mismatch"}
    ]


def test_verify_names_every_bundle_that_shares_a_damaged_frame(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(imported, write_corpus, data_root, _blur())
    flip_byte(root / "blurred" / "00000000.rgb24")

    assert frames_refusal(data_root).details["frames"] == [
        {"stream_id": "one", "frame": "00000000.rgb24", "reason": "hash_mismatch"},
        {"stream_id": "blurred", "frame": "00000000.rgb24", "reason": "hash_mismatch"},
    ]


def test_removing_a_shared_name_leaves_the_parent_frame(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(imported, write_corpus, data_root, _blur())
    case = root / "blurred"
    case.chmod(0o755)
    (case / "00000000.rgb24").unlink()

    assert frames_refusal(data_root).details["frames"] == [
        {"stream_id": "blurred", "frame": "00000000.rgb24", "reason": "missing"}
    ]
    assert open_frame_bundle(root / "one").read_frame(0)


def test_a_short_window_fits_in_the_space_its_changed_frames_need(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_bytes = WIDTH * HEIGHT * 3
    _limit_case_space(monkeypatch, len(_CHANGED) * frame_bytes)

    root = stage_cases(imported, write_corpus, data_root, _blur())

    assert (root / "blurred").is_dir()


def test_a_short_window_is_refused_when_one_changed_frame_does_not_fit(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_bytes = WIDTH * HEIGHT * 3
    _limit_case_space(monkeypatch, len(_CHANGED) * frame_bytes - 1)

    with pytest.raises(CorpusRefusal) as caught:
        stage_cases(imported, write_corpus, data_root, _blur())

    assert caught.value.code is RefusalCode.STORAGE_FAILED
    assert not (data_root / "corpus" / "pilot-v1" / "frames" / "blurred").exists()
    assert (data_root / "corpus" / "pilot-v1" / "frames" / "one").is_dir()


def test_a_case_that_only_repeats_frames_needs_no_extra_frame_space(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[int] = []

    def limited(root: Path, frames: int, width: int, height: int) -> None:
        seen.append(frames)
        usage = shutil.disk_usage(root)._replace(free=0)
        monkeypatch.setattr(shutil, "disk_usage", lambda _path: usage)
        require_space(root, frames, width, height)

    monkeypatch.setattr(generated, "require_space", limited)
    stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("repeated", "duplicated_frames", 1, {"count": 2}),
    )

    assert seen == [0]


def test_a_parent_on_another_device_reserves_every_frame(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[int] = []
    monkeypatch.setattr(generated, "_same_device", lambda _parent, _root: False)

    def spy(root: Path, frames: int, width: int, height: int) -> None:
        seen.append(frames)
        require_space(root, frames, width, height)

    monkeypatch.setattr(generated, "require_space", spy)
    stage_cases(imported, write_corpus, data_root, _blur())

    assert seen == [FRAME_COUNT]


def _limit_case_space(monkeypatch: pytest.MonkeyPatch, free_bytes: int) -> None:
    def limited(root: Path, frames: int, width: int, height: int) -> None:
        usage = shutil.disk_usage(root)._replace(free=free_bytes)
        monkeypatch.setattr(shutil, "disk_usage", lambda _path: usage)
        require_space(root, frames, width, height)

    monkeypatch.setattr(generated, "require_space", limited)
