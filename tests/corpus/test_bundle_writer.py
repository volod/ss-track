import json
import logging
import shutil
import stat
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    open_frame_bundle,
    stage_corpus,
)
from ss_track.corpus.frames import FRAME_BUNDLE_KIND
from ss_track.corpus.sealed import read_sealed, sha256_bytes
from tests.corpus._media import FRAME_COUNT, HEIGHT, WIDTH, expected_rgb, write_clip
from tests.corpus.conftest import WriteCorpus, WriteRecording, reseal, stream_of

_CORPUS = "pilot-v1"
_ODD_WIDTH = 65
_ODD_HEIGHT = 49
_WRITER_MODULE = "ss_track.corpus.bundle_writer"


def _bundle_path(data_root: Path, sequence: str = "one", corpus: str = _CORPUS) -> Path:
    return data_root / "corpus" / corpus / "frames" / sequence


def _manifest(data_root: Path) -> dict[str, object]:
    return read_sealed(_bundle_path(data_root) / "manifest.json", FRAME_BUNDLE_KIND)


def _identity(data_root: Path) -> dict[str, object]:
    identity = _manifest(data_root)["identity"]
    assert isinstance(identity, dict)
    return identity


def _refused(data_root: Path, code: RefusalCode, corpus: str = _CORPUS) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(corpus, data_root)
    assert caught.value.code is code
    return caught.value


def _scratch(data_root: Path) -> list[Path]:
    return list(_bundle_path(data_root).parent.glob(".incoming-*"))


@pytest.fixture
def built(imported: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> ImportResult:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    return imported


def test_stage_writes_every_frame_with_an_index_and_per_frame_hashes(
    built: ImportResult, data_root: Path
) -> None:
    result = stage_corpus(_CORPUS, data_root)

    bundle = result.bundles[0]
    directory = _bundle_path(data_root)
    identity = _identity(data_root)
    frames = identity["frames"]
    assert isinstance(frames, list)
    assert result.status == "staged"
    assert (bundle.status, bundle.frame_count) == ("staged", FRAME_COUNT)
    assert (bundle.pixel_format, bundle.width, bundle.height) == ("rgb24", WIDTH, HEIGHT)
    assert identity["source_sha256"] == built.source_sha256
    assert identity["bytes_per_frame"] == WIDTH * HEIGHT * 3
    assert [frame["frame_index"] for frame in frames] == list(range(FRAME_COUNT))
    assert [frame["pts"] for frame in frames] == [index * 40 for index in range(FRAME_COUNT)]
    for frame in frames:
        pixels = (directory / f"{frame['frame_index']:08d}.rgb24").read_bytes()
        assert sha256_bytes(pixels) == frame["sha256"]
        assert len(pixels) == WIDTH * HEIGHT * 3


def test_a_clean_decode_reproduces_the_original_pixels_exactly(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    write_clip(media / "clip.mkv", "ffv1", "bgr0")
    imported = import_source(write_recording(), data_root)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    stage_corpus(_CORPUS, data_root)

    bundle = open_frame_bundle(_bundle_path(data_root))
    assert all(bundle.read_frame(i) == expected_rgb(i) for i in range(FRAME_COUNT))


@pytest.mark.parametrize(
    ("name", "codec", "pixel_format"),
    [
        pytest.param("clip.mov", "qtrle", "rgb24", id="native-rgb24"),
        pytest.param("clip.mkv", "ffv1", "bgr0", id="converted-rgb"),
    ],
)
def test_an_odd_width_stages_with_no_row_padding(
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    name: str,
    codec: str,
    pixel_format: str,
) -> None:
    size = {"width": _ODD_WIDTH, "height": _ODD_HEIGHT}
    write_clip(media / name, codec, pixel_format, frames=3, **size)
    imported = import_source(write_recording(name), data_root)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    stage_corpus(_CORPUS, data_root)

    bundle = open_frame_bundle(_bundle_path(data_root))
    assert bundle.read_frame(2) == expected_rgb(2, _ODD_WIDTH, _ODD_HEIGHT)


def test_a_selection_stages_only_its_window_under_source_frame_indices(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    window = {"start_frame": 5, "end_frame": 9}
    build_corpus(write_corpus([stream_of(imported, selection=window)]), data_root)
    build_corpus(write_corpus([stream_of(imported)], corpus_id="whole"), data_root)

    stage_corpus(_CORPUS, data_root)
    stage_corpus("whole", data_root)

    partial = open_frame_bundle(_bundle_path(data_root))
    whole = open_frame_bundle(data_root / "corpus" / "whole" / "frames" / "one")
    assert sorted(path.name for path in partial.directory.glob("*.rgb24")) == [
        f"0000000{index}.rgb24" for index in range(5, 9)
    ]
    assert [ref.frame_index for ref in partial.frame_refs()] == [5, 6, 7, 8]
    assert all(partial.read_frame(i) == whole.read_frame(i) for i in range(5, 9))
    assert partial.bundle_sha256 != whole.bundle_sha256


def test_a_bundle_is_read_only(built: ImportResult, data_root: Path) -> None:
    stage_corpus(_CORPUS, data_root)

    directory = _bundle_path(data_root)
    assert stat.S_IMODE(directory.stat().st_mode) == 0o555
    assert {stat.S_IMODE(path.stat().st_mode) for path in directory.iterdir()} == {0o444}


def test_a_bundle_records_how_its_pixels_were_made(built: ImportResult, data_root: Path) -> None:
    stage_corpus(_CORPUS, data_root)

    manifest = _manifest(data_root)
    assert manifest["source_pixel_format"] == "yuvj420p"
    assert manifest["source_bits_per_component"] == 8
    assert manifest["precision_reduced"] is False
    assert manifest["display_rotation_degrees"] == 0
    assert manifest["interlaced_frames"] == 0
    assert manifest["timestamp_quality"] == "derived"
    assert manifest["color"] == {
        "matrix": 5,
        "range": 2,
        "primaries": 2,
        "transfer": 2,
        "chroma_location": 2,
    }


def test_a_deep_source_is_staged_and_flagged_as_reduced(
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_clip(media / "clip.mkv", "ffv1", "yuv420p10le", frames=3)
    imported = import_source(write_recording(), data_root)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    with caplog.at_level(logging.WARNING, _WRITER_MODULE):
        stage_corpus(_CORPUS, data_root)

    manifest = _manifest(data_root)
    assert manifest["source_bits_per_component"] == 10
    assert manifest["precision_reduced"] is True
    assert "10-bit source staged at 8 bits" in caplog.text


@pytest.mark.parametrize(
    ("codec", "pixel_format", "warned"),
    [
        pytest.param("ffv1", "yuv444p", True, id="yuv-needs-a-matrix"),
        pytest.param("ffv1", "gray", False, id="gray-has-no-matrix"),
        pytest.param("ffv1", "bgr0", False, id="rgb-has-no-matrix"),
    ],
)
def test_an_untagged_matrix_is_reported_only_when_conversion_used_one(
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    caplog: pytest.LogCaptureFixture,
    codec: str,
    pixel_format: str,
    warned: bool,
) -> None:
    write_clip(media / "clip.mkv", codec, pixel_format, frames=3)
    imported = import_source(write_recording(), data_root)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    with caplog.at_level(logging.WARNING, _WRITER_MODULE):
        stage_corpus(_CORPUS, data_root)

    assert ("no color matrix tag" in caplog.text) is warned


def test_a_missing_pts_stays_absent_in_the_frame_index(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    write_clip(media / "clip.mjpeg", container_format="mjpeg")
    imported = import_source(write_recording("clip.mjpeg"), data_root)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    stage_corpus(_CORPUS, data_root)

    bundle = open_frame_bundle(_bundle_path(data_root))
    assert imported.timestamp_quality == "missing"
    assert {ref.pts for ref in bundle.frame_refs()} == {None}
    assert bundle.frame_ref(0).timestamp_quality == "missing"


def test_changed_stored_source_is_refused(built: ImportResult, data_root: Path) -> None:
    stored = built.manifest_path.parent / "source.mkv"
    stored.chmod(0o644)
    stored.write_bytes(stored.read_bytes() + b"\x00")

    _refused(data_root, RefusalCode.SOURCE_HASH_MISMATCH)

    assert not _bundle_path(data_root).exists()


def test_a_source_redecoded_after_the_build_is_refused(
    built: ImportResult, data_root: Path
) -> None:
    reseal(built.manifest_path, decode_policy_sha256="d" * 64)

    _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)

    assert not _bundle_path(data_root).exists()


def test_a_decode_that_disagrees_with_the_import_record_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    record = json.loads(imported.manifest_path.read_text(encoding="ascii"))
    sequence = record["sequence"] | {"pts": [pts + 1 for pts in record["sequence"]["pts"]]}
    reseal(imported.manifest_path, sequence=sequence)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    refusal = _refused(data_root, RefusalCode.DECODE_DRIFT)

    assert refusal.details["fields"] == ["pts"]
    assert not _bundle_path(data_root).exists()
    assert not _scratch(data_root)


def test_a_failed_write_leaves_no_bundle_and_no_scratch(
    built: ImportResult, data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written = []
    write_bytes = Path.write_bytes

    def fail_on_third(path: Path, data: bytes) -> int:
        written.append(path)
        if len(written) == 3:
            raise OSError(28, "No space left on device")
        return write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_on_third)

    with pytest.raises(OSError, match="No space left"):
        stage_corpus(_CORPUS, data_root)

    assert not _bundle_path(data_root).exists()
    assert not _scratch(data_root)


def test_too_little_free_space_is_refused_before_decoding(
    built: ImportResult, data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = shutil.disk_usage(data_root)
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: usage._replace(free=WIDTH * HEIGHT * 3 * FRAME_COUNT - 1)
    )

    refusal = _refused(data_root, RefusalCode.STORAGE_FAILED)

    assert refusal.details["required_bytes"] == WIDTH * HEIGHT * 3 * FRAME_COUNT
    assert not _scratch(data_root)
