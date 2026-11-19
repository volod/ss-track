"""Explicit capture judgments are amended alone and never inferred."""

from pathlib import Path

import pytest

from ss_track.corpus import RefusalCode, amend_source
from ss_track.corpus.declarations.declaration import load_recording_declaration
from tests.corpus._amending import refused
from tests.corpus.conftest import WriteRecording


@pytest.mark.parametrize("field", ["camera_control_mode", "observer_platform"])
def test_invalid_judgment_names_field(write_recording: WriteRecording, field: str) -> None:
    declared = write_recording(capture={field: "invented"})
    refusal = refused(lambda: load_recording_declaration(declared), RefusalCode.MANIFEST_INVALID)
    assert field in str(refusal)


def test_command_amends_capture_only(
    imported: object,
    write_recording: WriteRecording,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from ss_track.cli import main
    from ss_track.commands.report import EXIT_OK
    from tests.corpus.conftest import last_record

    declaration = write_recording(capture={"observer_platform": "airborne"})
    assert main(["import", "--source", str(declaration), "--amend-capture"]) == EXIT_OK
    assert last_record(caplog)["status"] == "amended"
    assert main(["import", "--source", str(declaration), "--amend-capture"]) == EXIT_OK
    assert last_record(caplog)["status"] == "unchanged"


def test_capture_change_lists_pinned_version_and_allows_successor(
    imported: object,
    write_recording: WriteRecording,
    write_corpus: object,
    data_root: Path,
) -> None:
    from ss_track.corpus import build_corpus, verify_corpus_frames
    from ss_track.corpus.sources.importer import ImportResult
    from tests.corpus._amending import staged
    from tests.corpus.conftest import WriteCorpus, stream_of

    assert isinstance(imported, ImportResult)
    assert callable(write_corpus)
    corpus_writer: WriteCorpus = write_corpus
    staged(imported, corpus_writer, data_root)
    declaration = write_recording(capture={"observer_platform": "airborne"})
    result = amend_source(declaration, data_root, amend_capture=True, amend_terms=False)
    assert result.impact is not None
    assert "pilot-v1" in str(result.impact.to_record())
    refused(lambda: verify_corpus_frames("pilot-v1", data_root), RefusalCode.SOURCE_RECORD_CHANGED)
    successor = corpus_writer([stream_of(imported)], corpus_id="pilot-v2", supersedes="pilot-v1")
    assert build_corpus(successor, data_root).status == "built"


def test_capture_amendment_refuses_other_capture_changes(
    imported: object, write_recording: WriteRecording, data_root: Path
) -> None:
    from ss_track.corpus.sources.importer import ImportResult

    assert isinstance(imported, ImportResult)
    before = imported.manifest_path.read_bytes()
    declaration = write_recording(
        capture={"camera": "a different camera", "observer_platform": "airborne"}
    )
    refusal = refused(
        lambda: amend_source(declaration, data_root, amend_capture=True, amend_terms=False),
        RefusalCode.IMPORT_CONFLICT,
    )
    assert refusal.details["changed_facts"] == ["capture"]
    assert imported.manifest_path.read_bytes() == before
