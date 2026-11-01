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
