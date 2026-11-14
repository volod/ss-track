"""Explicit capture judgments preserve old evidence and never infer historical values."""

import json
from pathlib import Path

import pytest

from ss_track.corpus import RefusalCode, amend_source_terms
from ss_track.corpus.declarations.declaration import load_recording_declaration
from ss_track.corpus.sources.inspection import inspect_source
from tests.corpus._amending import read_source, refused
from tests.corpus._historic import kept_record
from tests.corpus.conftest import WriteRecording


@pytest.mark.parametrize("field", ["camera_control_mode", "observer_platform"])
def test_invalid_judgment_names_field(write_recording: WriteRecording, field: str) -> None:
    declared = write_recording(capture={field: "invented"})
    refusal = refused(lambda: load_recording_declaration(declared), RefusalCode.MANIFEST_INVALID)
    assert field in str(refusal)


def test_old_source_migrates_without_media_and_retains_bytes(
    write_recording: WriteRecording, data_root: Path
) -> None:
    original = kept_record("source-schema-2-129a350.json")
    old = json.loads(original)
    sha256 = old["source"]["sha256"]
    path = data_root / "import" / sha256 / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(original)
    declaration = write_recording(
        source="missing.mkv",
        sha256=sha256,
        capture={"camera_control_mode": "fixed_camera", "observer_platform": "ground_fixed"},
    )
    inspected = inspect_source(sha256, None, data_root)
    assert inspected.to_record()["source_inspection"]["disposition"] == "facts"
    refusal = refused(
        lambda: amend_source_terms(declaration, data_root), RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    )
    assert "--amend-capture" in refusal.details["missing_operations"]
    assert path.read_bytes() == original

    result = amend_source_terms(declaration, data_root, amend_capture=True, amend_terms=False)
    current = read_source(path)
    assert current["capture"]["camera_control_mode"] == "fixed_camera"
    assert current["capture"]["observer_platform"] == "ground_fixed"
    assert result.replaced_path is not None
    assert result.replaced_path.read_bytes() == original
    for key in (
        "source",
        "sequence",
        "rights",
        "sensitivity",
        "decode_policy",
        "decode_policy_sha256",
    ):
        assert current[key] == old[key]
    assert (
        amend_source_terms(declaration, data_root, amend_capture=True, amend_terms=False).status
        == "unchanged"
    )


def test_incomplete_historical_migration_names_every_missing_operation(
    write_recording: WriteRecording, data_root: Path
) -> None:
    original = kept_record("source-schema-1-0238d55.json")
    old = json.loads(original)
    sha256 = old["source"]["sha256"]
    path = data_root / "import" / sha256 / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(original)
    declaration = write_recording(source="missing.mkv", sha256=sha256)

    refusal = refused(
        lambda: amend_source_terms(declaration, data_root, amend_terms=False),
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
    )
    assert set(refusal.details["missing_operations"]) == {
        "--amend-capture",
        "--amend-terms",
        "--redecode",
    }
    assert path.read_bytes() == original
    assert not (path.parent / "replaced").exists()


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
    result = amend_source_terms(declaration, data_root, amend_capture=True, amend_terms=False)
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
        lambda: amend_source_terms(declaration, data_root, amend_capture=True, amend_terms=False),
        RefusalCode.IMPORT_CONFLICT,
    )
    assert refusal.details["changed_facts"] == ["capture"]
    assert imported.manifest_path.read_bytes() == before
