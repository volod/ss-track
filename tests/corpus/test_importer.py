import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode, import_source
from ss_track.corpus.decode import DecodePolicy
from ss_track.corpus.sealed import read_sealed, sha256_file
from tests.corpus._media import FRAME_COUNT, write_clip
from tests.corpus.conftest import WriteRecording


def test_import_writes_a_hashed_manifest_with_every_required_field(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    result = import_source(write_recording(), data_root)

    manifest = read_sealed(result.manifest_path, "ss-track.source-manifest")
    sequence = manifest["sequence"]
    assert isinstance(sequence, dict)
    assert result.status == "imported"
    assert manifest["source"] == {
        "sha256": sha256_file(clip),
        "sha256_declared": False,
        "size_bytes": clip.stat().st_size,
        "stored_name": "source.mkv",
    }
    assert manifest["rights"] == {
        "holder": "Project Contributors",
        "basis": "owned",
        "retention": "project duration",
        "retain_until": None,
        "derived_frames": True,
        "sharing": "restricted",
    }
    assert manifest["sensitivity"] == {"level": "low", "notes": None}
    assert sequence["timestamp_quality"] == "derived"
    assert sequence["frame_count"] == FRAME_COUNT
    assert sequence["pts"] == [index * 40 for index in range(FRAME_COUNT)]
    assert sequence["time_base"] == "1/1000"
    assert sequence["completeness_checks"] == ["matroska_segment_size"]
    assert manifest["decode_policy_sha256"]


def test_manifest_contains_no_path_or_clock_time(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    result = import_source(write_recording(), data_root)

    text = result.manifest_path.read_text(encoding="ascii")
    assert str(clip.parent) not in text
    assert clip.name not in text


def test_stored_evidence_is_read_only(imported, data_root: Path) -> None:  # type: ignore[no-untyped-def]
    directory = data_root / "import" / imported.source_sha256

    modes = {path.name: stat.S_IMODE(path.stat().st_mode) for path in directory.iterdir()}

    assert modes == {"manifest.json": 0o444, "source.mkv": 0o444}


def test_stored_copy_does_not_depend_on_the_original(
    clip: Path,
    imported,
    data_root: Path,  # type: ignore[no-untyped-def]
) -> None:
    source = data_root / "import" / imported.source_sha256 / "source.mkv"
    clip.unlink()

    assert sha256_file(source) == imported.source_sha256


def test_declared_hash_is_verified_and_recorded(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    result = import_source(write_recording(sha256=sha256_file(clip)), data_root)

    manifest = read_sealed(result.manifest_path, "ss-track.source-manifest")
    assert isinstance(manifest["source"], dict)
    assert manifest["source"]["sha256_declared"] is True


def test_missing_pts_imports_as_missing_with_no_invented_values(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_clip(media / "clip.mjpeg", container_format="mjpeg")

    result = import_source(write_recording("clip.mjpeg"), data_root)

    manifest = read_sealed(result.manifest_path, "ss-track.source-manifest")
    assert isinstance(manifest["sequence"], dict)
    assert result.timestamp_quality == "missing"
    assert manifest["sequence"]["pts"] == [None] * FRAME_COUNT


def test_capture_clock_evidence_grades_stored_pts_as_measured(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    declaration = write_recording(timestamps={"capture_clock_evidence": "hardware clock"})

    assert import_source(declaration, data_root).timestamp_quality == "measured"


def test_missing_completeness_evidence_warns_and_stays_visible(
    media: Path,
    write_recording: WriteRecording,
    data_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_clip(media / "clip.mjpeg", container_format="mjpeg")

    result = import_source(write_recording("clip.mjpeg"), data_root)

    assert result.completeness_checks == []
    assert "no container-level completeness evidence" in caplog.text


def test_repeating_an_import_changes_nothing(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    first = import_source(write_recording(), data_root)
    before = first.manifest_path.read_bytes()

    second = import_source(write_recording(), data_root)

    assert (first.status, second.status) == ("imported", "unchanged")
    assert second.manifest_sha256 == first.manifest_sha256
    assert first.manifest_path.read_bytes() == before
    assert [path.name for path in (data_root / "import").iterdir()] == [first.source_sha256]


def test_same_bytes_with_changed_rights_are_refused(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    first = import_source(write_recording(), data_root)
    changed = write_recording(sensitivity={"level": "high"})

    with pytest.raises(CorpusRefusal) as caught:
        import_source(changed, data_root)

    assert caught.value.code is RefusalCode.IMPORT_CONFLICT
    assert caught.value.details["existing_manifest_sha256"] == first.manifest_sha256


def test_changed_decoder_is_a_conflict_not_a_silent_rewrite(
    clip: Path,
    write_recording: WriteRecording,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import_source(write_recording(), data_root)
    upgraded = DecodePolicy(decoder="pyav", decoder_version="99", ffmpeg_version="99")
    monkeypatch.setattr("ss_track.corpus.importer.current_decode_policy", lambda: upgraded)

    with pytest.raises(CorpusRefusal) as caught:
        import_source(write_recording(), data_root)

    assert caught.value.code is RefusalCode.IMPORT_CONFLICT


def test_reimport_detects_a_changed_stored_source(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    result = import_source(write_recording(), data_root)
    stored = result.manifest_path.parent / "source.mkv"
    stored.chmod(0o644)
    stored.write_bytes(stored.read_bytes()[:-1] + b"\x00")

    with pytest.raises(CorpusRefusal) as caught:
        import_source(write_recording(), data_root)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_a_second_process_writes_identical_bytes(
    clip: Path, write_recording: WriteRecording, tmp_path: Path
) -> None:
    declaration = write_recording()
    manifests = []
    for name in ("first", "second"):
        root = tmp_path / name
        subprocess.run(
            [sys.executable, "-m", "ss_track.cli", "import", "--source", str(declaration)],
            check=True,
            capture_output=True,
            env={"DATA_DIR": str(root), "PATH": ""},
        )
        manifests.append(next(root.glob("import/*/manifest.json")).read_bytes())

    assert manifests[0] == manifests[1]
    assert json.loads(manifests[0])["kind"] == "ss-track.source-manifest"
