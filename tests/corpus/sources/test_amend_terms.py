"""`import --amend-terms` records new terms for an imported source and changes nothing else."""

import stat
from pathlib import Path

import pytest

from ss_track.cli import build_parser, main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    amend_source_terms,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.records.sealed import read_sealed
from tests.corpus._amending import (
    CORPUS,
    evidence,
    read_source,
    refused,
    rights_with,
    staged,
    stored_source,
)
from tests.corpus.conftest import WriteCorpus, WriteRecording, last_record, stream_of

_PUBLIC_SCENARIO = {"sharing": "public", "max_sensitivity": "high"}


def test_an_amendment_to_restricted_refuses_the_pinning_corpus_and_keeps_the_bytes(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared = import_source(write_recording(rights=rights_with(sharing="public")), data_root)
    declared = write_corpus([stream_of(shared)], scenario_rights=_PUBLIC_SCENARIO)
    build_corpus(declared, data_root)
    stage_corpus(CORPUS, data_root)
    stored = stored_source(shared)
    before = stored.read_bytes()
    frames = evidence(data_root / "corpus" / CORPUS / "frames")

    def no_decode(*_: object) -> None:
        raise AssertionError("an amendment decodes nothing")

    monkeypatch.setattr("ss_track.corpus.sources.importer.inspect_media", no_decode)
    result = amend_source_terms(
        write_recording(rights=rights_with(sharing="restricted")), data_root
    )
    monkeypatch.undo()

    assert (result.status, result.changed_terms) == ("amended", ["rights.sharing"])
    assert result.replaced_manifest_sha256 == shared.manifest_sha256
    assert result.manifest_sha256 != shared.manifest_sha256
    refusal = refused(
        lambda: verify_corpus_frames(CORPUS, data_root), RefusalCode.SOURCE_RECORD_CHANGED
    )
    assert refusal.details["changed_terms"] == ["rights.sharing"]
    assert refusal.details["source_manifest_sha256"] == result.manifest_sha256
    assert stored.read_bytes() == before
    assert stat.S_IMODE(stored.stat().st_mode) == 0o444
    assert stat.S_IMODE(result.manifest_path.stat().st_mode) == 0o444
    assert evidence(data_root / "corpus" / CORPUS / "frames") == frames


def test_an_amended_record_is_the_one_a_fresh_import_would_write(
    clip: Path, write_recording: WriteRecording, tmp_path: Path
) -> None:
    import_source(write_recording(), tmp_path / "old")
    changed = write_recording(sensitivity={"level": "high", "notes": "faces"})

    amended = amend_source_terms(changed, tmp_path / "old")
    fresh = import_source(changed, tmp_path / "fresh")

    assert amended.manifest_path.read_bytes() == fresh.manifest_path.read_bytes()


def test_a_new_corpus_version_builds_on_the_amended_record(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    staged(imported, write_corpus, data_root)

    amended = amend_source_terms(write_recording(sensitivity={"level": "moderate"}), data_root)

    declared = write_corpus([stream_of(imported)], corpus_id="pilot-v2")
    assert build_corpus(declared, data_root).status == "built"
    assert stage_corpus("pilot-v2", data_root).status == "staged"
    assert verify_corpus_frames("pilot-v2", data_root).status == "verified"
    corpus = read_sealed(data_root / "corpus" / "pilot-v2" / "manifest.json", CORPUS_MANIFEST)
    assert isinstance(corpus["streams"], list)
    assert corpus["streams"][0]["source_manifest_sha256"] == amended.manifest_sha256


def test_a_linked_successor_replaces_a_version_the_amendment_refuses(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    staged(imported, write_corpus, data_root)
    amend_source_terms(write_recording(sensitivity={"level": "moderate"}), data_root)

    declared = write_corpus([stream_of(imported)], corpus_id="pilot-v2", supersedes=CORPUS)

    assert build_corpus(declared, data_root).status == "built"
    assert stage_corpus("pilot-v2", data_root).status == "staged"
    assert verify_corpus_frames("pilot-v2", data_root).status == "verified"
    refused(lambda: verify_corpus_frames(CORPUS, data_root), RefusalCode.SOURCE_RECORD_CHANGED)


def test_a_plain_import_of_changed_terms_names_them_and_the_command(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    changed = write_recording(
        rights=rights_with(sharing="public", derived_frames=False), sensitivity={"level": "high"}
    )

    refusal = refused(lambda: import_source(changed, data_root), RefusalCode.IMPORT_CONFLICT)

    assert refusal.details["changed_terms"] == [
        "rights.derived_frames",
        "rights.sharing",
        "sensitivity.level",
    ]
    assert "ss-track import --amend-terms" in refusal.message


@pytest.mark.parametrize(
    "declared",
    [
        {"capture": {"camera": "bench camera"}},
        {"timestamps": {"capture_clock_evidence": "hardware clock"}},
    ],
)
def test_a_plain_import_never_offers_the_command_for_a_change_it_cannot_record(
    imported: ImportResult,
    write_recording: WriteRecording,
    data_root: Path,
    declared: dict[str, object],
) -> None:
    changed = write_recording(sensitivity={"level": "high"}, **declared)

    refusal = refused(lambda: import_source(changed, data_root), RefusalCode.IMPORT_CONFLICT)

    assert refusal.details["changed_terms"] == ["sensitivity.level"]
    assert "--amend-terms" not in refusal.message


def test_after_an_amendment_only_the_new_declaration_imports_as_unchanged(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    narrowed = write_recording(sensitivity={"level": "high"})
    amended = amend_source_terms(narrowed, data_root)

    repeat = import_source(narrowed, data_root)

    assert (repeat.status, repeat.manifest_sha256) == ("unchanged", amended.manifest_sha256)
    old = write_recording()
    refused(lambda: import_source(old, data_root), RefusalCode.IMPORT_CONFLICT)


def test_a_withdrawal_stays_recordable_after_the_stored_bytes_are_removed(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    staged(imported, write_corpus, data_root)
    stored_source(imported).unlink()

    amend_source_terms(write_recording(rights=rights_with(derived_frames=False)), data_root)

    refusal = refused(
        lambda: verify_corpus_frames(CORPUS, data_root), RefusalCode.SOURCE_RECORD_CHANGED
    )
    assert refusal.details["changed_terms"] == ["rights.derived_frames"]


def test_an_installed_decoder_change_neither_blocks_nor_enters_an_amendment(
    imported: ImportResult,
    write_recording: WriteRecording,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = read_source(imported.manifest_path)
    upgraded = DecodePolicy(decoder="pyav", decoder_version="99", ffmpeg_version="99")
    monkeypatch.setattr("ss_track.corpus.sources.amendment.current_decode_policy", lambda: upgraded)

    result = amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    new = read_source(result.manifest_path)
    assert result.decode_policy_current is False
    assert new["decode_policy"] == old["decode_policy"]
    assert new["decode_policy_sha256"] == old["decode_policy_sha256"]
    assert new["sequence"] == old["sequence"]


def test_the_result_says_when_the_record_is_under_the_installed_decoder(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    amended = amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    assert amended.decode_policy_current is True


def test_the_command_reports_one_record_and_its_refusal_exits_one(
    imported: ImportResult,
    write_recording: WriteRecording,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    narrowed = write_recording(sensitivity={"level": "high"})

    assert main(["import", "--source", str(narrowed), "--amend-terms"]) == EXIT_OK
    record = last_record(caplog)
    assert record["status"] == "amended"
    assert record["changed_terms"] == ["sensitivity.level"]
    assert record["replaced_manifest_sha256"] == imported.manifest_sha256

    assert main(["import", "--source", str(narrowed), "--amend-terms"]) == EXIT_OK
    assert last_record(caplog)["status"] == "unchanged"

    changed = write_recording(capture={"camera": "bench camera"})
    assert main(["import", "--source", str(changed), "--amend-terms"]) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "IMPORT_CONFLICT"


def test_the_flag_is_off_unless_given() -> None:
    plain = build_parser().parse_args(["import", "--source", "a.yaml"])
    amending = build_parser().parse_args(["import", "--source", "a.yaml", "--amend-terms"])

    assert (plain.amend_terms, amending.amend_terms) == (False, True)
