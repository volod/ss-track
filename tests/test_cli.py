import json
import logging
from pathlib import Path

import pytest
import yaml

from ss_track.cli import EXIT_OK, EXIT_REFUSED, build_parser, main
from tests.corpus._media import write_clip
from tests.corpus.conftest import recording_declaration


def test_parser_selects_the_info_command() -> None:
    assert build_parser().parse_args(["info"]).command == "info"


def test_info_command_logs_the_project_identity(caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO)

    assert main(["info"]) == 0
    assert "ss-track" in caplog.text
    assert "ss_track" in caplog.text


def _record(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    return json.loads(caplog.records[-1].getMessage())


@pytest.fixture
def recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> Path:
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    write_clip(tmp_path / "clip.mkv")
    declaration = tmp_path / "recording.yaml"
    declaration.write_text(yaml.safe_dump(recording_declaration()), encoding="utf-8")
    return declaration


def test_parser_selects_the_corpus_commands() -> None:
    assert build_parser().parse_args(["import", "--source", "a.yaml"]).command == "import"
    parsed = build_parser().parse_args(["corpus", "build", "--manifest", "b.yaml"])
    assert (parsed.command, parsed.corpus_command) == ("corpus", "build")
    for action in ("stage", "verify"):
        parsed = build_parser().parse_args(["corpus", action, "--corpus", "c1"])
        assert (parsed.corpus_command, parsed.corpus) == (action, "c1")


def test_import_then_build_report_json_results(
    recording: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    assert main(["import", "--source", str(recording)]) == EXIT_OK
    imported = _record(caplog)
    corpus = tmp_path / "corpus.yaml"
    sequence = {"sequence_id": "one", "source_sha256": imported["source_sha256"]}
    corpus.write_text(
        yaml.safe_dump({"schema_version": 1, "corpus_id": "c1", "sequences": [sequence]}),
        encoding="utf-8",
    )

    assert main(["corpus", "build", "--manifest", str(corpus)]) == EXIT_OK

    built = _record(caplog)
    assert imported["status"] == "imported"
    assert built["status"] == "built"
    assert Path(str(built["manifest_path"])).is_file()


def _built_corpus(recording: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    assert main(["import", "--source", str(recording)]) == EXIT_OK
    sequence = {"sequence_id": "one", "source_sha256": _record(caplog)["source_sha256"]}
    corpus = tmp_path / "corpus.yaml"
    corpus.write_text(
        yaml.safe_dump({"schema_version": 1, "corpus_id": "c1", "sequences": [sequence]}),
        encoding="utf-8",
    )
    assert main(["corpus", "build", "--manifest", str(corpus)]) == EXIT_OK


def test_stage_then_verify_report_json_results(
    recording: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _built_corpus(recording, tmp_path, caplog)

    assert main(["corpus", "stage", "--corpus", "c1"]) == EXIT_OK
    staged = _record(caplog)
    assert main(["corpus", "verify", "--corpus", "c1"]) == EXIT_OK
    verified = _record(caplog)

    bundles = staged["bundles"]
    assert isinstance(bundles, list)
    assert staged["status"] == "staged"
    assert bundles[0]["sequence_id"] == "one"
    assert Path(bundles[0]["manifest_path"]).is_file()
    assert verified["status"] == "verified"
    assert verified["bundles"][0]["bundle_sha256"] == bundles[0]["bundle_sha256"]  # type: ignore[index]


def test_a_corrupted_frame_is_named_with_a_failing_status(
    recording: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _built_corpus(recording, tmp_path, caplog)
    assert main(["corpus", "stage", "--corpus", "c1"]) == EXIT_OK
    frame = tmp_path / "data" / "corpus" / "c1" / "frames" / "one" / "00000002.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"corrupted")

    assert main(["corpus", "verify", "--corpus", "c1"]) == EXIT_REFUSED

    refusal = _record(caplog)
    assert refusal["code"] == "FRAME_CORRUPTED"
    assert refusal["details"]["frames"] == [  # type: ignore[index]
        {"sequence_id": "one", "frame": "00000002.rgb24", "reason": "hash_mismatch"}
    ]


def test_staging_an_unbuilt_corpus_is_a_structured_refusal(
    recording: Path, caplog: pytest.LogCaptureFixture
) -> None:
    assert main(["corpus", "stage", "--corpus", "absent"]) == EXIT_REFUSED

    assert _record(caplog)["code"] == "CORPUS_NOT_BUILT"


def test_refusal_is_one_json_record_and_a_failing_status(
    recording: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "clip.mkv").write_bytes(b"")

    assert main(["import", "--source", str(recording)]) == EXIT_REFUSED

    assert _record(caplog) == {
        "status": "refused",
        "code": "SOURCE_EMPTY",
        "message": "source file has zero length",
        "details": {},
    }


def test_unwritable_data_root_is_a_structured_refusal(
    recording: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    (tmp_path / "occupied").touch()
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "occupied"))

    assert main(["import", "--source", str(recording)]) == EXIT_REFUSED

    assert _record(caplog)["code"] == "STORAGE_FAILED"
