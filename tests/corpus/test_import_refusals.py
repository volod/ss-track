from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode, import_source
from ss_track.corpus.sealed import sha256_file
from tests.corpus._media import write_clip, write_clip_with_pts
from tests.corpus.conftest import WriteRecording


def _assert_refused_leaving_nothing(
    declaration: Path, data_root: Path, code: RefusalCode
) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        import_source(declaration, data_root)
    assert caught.value.code is code
    imports = data_root / "import"
    assert not imports.exists() or list(imports.iterdir()) == []
    return caught.value


def test_wrong_hash_is_refused_with_both_values(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    declaration = write_recording(sha256="0" * 64)

    refusal = _assert_refused_leaving_nothing(
        declaration, data_root, RefusalCode.SOURCE_HASH_MISMATCH
    )

    assert refusal.details == {"expected_sha256": "0" * 64, "actual_sha256": sha256_file(clip)}


def test_zero_length_source_is_refused(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    (media / "clip.mkv").touch()

    _assert_refused_leaving_nothing(write_recording(), data_root, RefusalCode.SOURCE_EMPTY)


def test_absent_source_is_refused(write_recording: WriteRecording, data_root: Path) -> None:
    _assert_refused_leaving_nothing(write_recording(), data_root, RefusalCode.SOURCE_NOT_FOUND)


def test_directory_source_is_refused(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    (media / "clip.mkv").mkdir()

    _assert_refused_leaving_nothing(write_recording(), data_root, RefusalCode.SOURCE_UNREADABLE)


def test_unreadable_source_is_refused(
    clip: Path, write_recording: WriteRecording, data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny(*_: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("ss_track.corpus.importer.copy_with_sha256", deny)

    _assert_refused_leaving_nothing(write_recording(), data_root, RefusalCode.SOURCE_UNREADABLE)


@pytest.mark.parametrize("keep", [0.3, 0.6, 0.9])
def test_truncated_source_is_refused(
    clip: Path, write_recording: WriteRecording, data_root: Path, keep: float
) -> None:
    data = clip.read_bytes()
    clip.write_bytes(data[: int(len(data) * keep)])

    _assert_refused_leaving_nothing(write_recording(), data_root, RefusalCode.SOURCE_DAMAGED)


@pytest.mark.parametrize(
    ("position", "pts"),
    [pytest.param(3, 80, id="duplicate"), pytest.param(3, 70, id="backward")],
)
def test_non_increasing_pts_is_refused(
    media: Path, write_recording: WriteRecording, data_root: Path, position: int, pts: int
) -> None:
    times = [index * 40 for index in range(8)]
    times[position] = pts
    write_clip_with_pts(media / "clip.mkv", times)

    refusal = _assert_refused_leaving_nothing(
        write_recording(), data_root, RefusalCode.PTS_NON_INCREASING
    )

    assert refusal.details == {"frame_index": 3, "previous_pts": 80, "pts": pts}


def test_capture_clock_evidence_cannot_upgrade_missing_timestamps(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_clip(media / "clip.mjpeg", container_format="mjpeg")
    declaration = write_recording(
        "clip.mjpeg", timestamps={"capture_clock_evidence": "hardware clock"}
    )

    _assert_refused_leaving_nothing(declaration, data_root, RefusalCode.TIMESTAMP_CLAIM_UNSUPPORTED)
