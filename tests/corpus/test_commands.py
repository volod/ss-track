"""`ss-track import` and `ss-track corpus`: one JSON record per command, and a failing status."""

from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from tests.corpus.conftest import WriteCorpus, WriteRecording, last_record

_CORPUS = "pilot-v1"


def _import(write_recording: WriteRecording, caplog: pytest.LogCaptureFixture) -> str:
    assert main(["import", "--source", str(write_recording())]) == EXIT_OK
    return str(last_record(caplog)["source_sha256"])


def _build(manifest: Path) -> int:
    return main(["corpus", "build", "--manifest", str(manifest)])


def _built(
    write_recording: WriteRecording, write_corpus: WriteCorpus, caplog: pytest.LogCaptureFixture
) -> None:
    source_sha256 = _import(write_recording, caplog)
    assert _build(write_corpus([{"stream_id": "one", "source_sha256": source_sha256}])) == EXIT_OK


def test_import_then_build_report_json_results(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert main(["import", "--source", str(write_recording())]) == EXIT_OK
    imported = last_record(caplog)

    stream = {"stream_id": "one", "source_sha256": imported["source_sha256"]}
    assert _build(write_corpus([stream])) == EXIT_OK

    built = last_record(caplog)
    assert imported["status"] == "imported"
    assert built["status"] == "built"
    assert built["stream_count"] == 1
    assert built["generated_case_count"] == 0
    assert built["splits"] == {
        "development": {
            "group_count": 1,
            "encounter_count": 1,
            "stream_count": 1,
            "generated_case_count": 0,
        }
    }
    assert Path(str(built["manifest_path"])).is_file()


def test_a_rights_conflict_is_a_structured_refusal_with_a_failing_status(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stream = {"stream_id": "one", "source_sha256": _import(write_recording, caplog)}
    public = {"sharing": "public", "max_sensitivity": "high"}

    assert _build(write_corpus([stream], scenario_rights=public)) == EXIT_REFUSED

    refusal = last_record(caplog)
    assert refusal["code"] == "RIGHTS_CONFLICT"
    assert refusal["details"]["conflicts"][0]["stream_id"] == "one"  # type: ignore[index]
    assert not (cli_root / "corpus").exists()


def test_stage_then_verify_report_json_results(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _built(write_recording, write_corpus, caplog)

    assert main(["corpus", "stage", "--corpus", _CORPUS]) == EXIT_OK
    staged = last_record(caplog)
    assert main(["corpus", "verify", "--corpus", _CORPUS]) == EXIT_OK
    verified = last_record(caplog)

    bundles = staged["bundles"]
    assert isinstance(bundles, list)
    assert staged["status"] == "staged"
    assert bundles[0]["stream_id"] == "one"
    assert bundles[0]["transform"] == "identity"
    assert Path(bundles[0]["manifest_path"]).is_file()
    assert verified["status"] == "verified"
    assert verified["bundles"][0]["bundle_sha256"] == bundles[0]["bundle_sha256"]  # type: ignore[index]
    assert verified["frame_set_sha256"] == staged["frame_set_sha256"]


def test_a_corrupted_frame_is_named_with_a_failing_status(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _built(write_recording, write_corpus, caplog)
    assert main(["corpus", "stage", "--corpus", _CORPUS]) == EXIT_OK
    frame = cli_root / "corpus" / _CORPUS / "frames" / "one" / "00000002.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"corrupted")

    assert main(["corpus", "verify", "--corpus", _CORPUS]) == EXIT_REFUSED

    refusal = last_record(caplog)
    assert refusal["code"] == "FRAME_CORRUPTED"
    assert refusal["details"]["frames"] == [  # type: ignore[index]
        {"stream_id": "one", "frame": "00000002.rgb24", "reason": "hash_mismatch"}
    ]


def test_staging_an_unbuilt_corpus_is_a_structured_refusal(
    cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    assert main(["corpus", "stage", "--corpus", "absent"]) == EXIT_REFUSED

    assert last_record(caplog)["code"] == "CORPUS_NOT_BUILT"


def test_refusal_is_one_json_record_and_a_failing_status(
    media: Path, write_recording: WriteRecording, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (media / "clip.mkv").write_bytes(b"")

    assert main(["import", "--source", str(write_recording())]) == EXIT_REFUSED

    assert last_record(caplog) == {
        "status": "refused",
        "code": "SOURCE_EMPTY",
        "message": "source file has zero length",
        "details": {},
    }


def test_unwritable_data_root_is_a_structured_refusal(
    clip: Path,
    write_recording: WriteRecording,
    cli_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    (tmp_path / "occupied").touch()
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "occupied"))

    assert main(["import", "--source", str(write_recording())]) == EXIT_REFUSED

    assert last_record(caplog)["code"] == "STORAGE_FAILED"
