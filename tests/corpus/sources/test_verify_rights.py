"""`corpus verify` proves the recorded rights still hold, not only that frames are intact.

Terms change through the real amendment. A record that changes in anything else has no command, so
those fixtures remove the source's directory and import it again, through the real importer.
"""

import shutil
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    amend_source_terms,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus._amending import rights_with
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    last_record,
    stream_of,
)
from tests.corpus.sources._verify_rights import CORPUS, UNTIL, refused_verify, stage_before

_PUBLIC_SCENARIO = {"sharing": "public", "max_sensitivity": "high"}


def _reimport(source: ImportResult, declaration: Path, data_root: Path) -> ImportResult:
    shutil.rmtree(source.manifest_path.parent)
    return import_source(declaration, data_root)


def test_a_source_amended_to_restricted_refuses_and_exits_one(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    shared = import_source(write_recording(rights=rights_with(sharing="public")), cli_root)
    declared = write_corpus([stream_of(shared)], scenario_rights=_PUBLIC_SCENARIO)
    build_corpus(declared, cli_root)
    stage_corpus(CORPUS, cli_root)
    assert main(["corpus", "verify", "--corpus", CORPUS]) == EXIT_OK

    closed = amend_source_terms(write_recording(rights=rights_with(sharing="restricted")), cli_root)

    assert main(["corpus", "verify", "--corpus", CORPUS]) == EXIT_REFUSED
    refusal = last_record(caplog)
    assert refusal["status"] == "refused"
    assert refusal["code"] == "SOURCE_RECORD_CHANGED"
    assert refusal["details"] == {
        "stream_id": "one",
        "source_sha256": shared.source_sha256,
        "corpus_source_manifest_sha256": shared.manifest_sha256,
        "source_manifest_sha256": closed.manifest_sha256,
        "changed_terms": ["rights.sharing"],
    }


def test_an_expired_source_refuses_and_exits_one(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = import_source(write_recording(rights=rights_with(retain_until=UNTIL)), cli_root)
    stage_before(source, write_corpus, cli_root)

    assert main(["corpus", "verify", "--corpus", CORPUS]) == EXIT_REFUSED

    refusal = last_record(caplog)
    assert refusal["code"] == "RETENTION_EXPIRED"
    assert refusal["details"] == {
        "source_sha256": source.source_sha256,
        "retain_until": UNTIL.isoformat(),
    }


def test_an_unchanged_corpus_verifies_and_writes_nothing(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stage_before(imported, write_corpus, cli_root)
    evidence = {path: path.read_bytes() for path in cli_root.rglob("*") if path.is_file()}

    assert main(["corpus", "verify", "--corpus", CORPUS]) == EXIT_OK

    assert last_record(caplog)["status"] == "verified"
    assert evidence == {path: path.read_bytes() for path in cli_root.rglob("*") if path.is_file()}


@pytest.mark.parametrize(
    ("declared", "changed"),
    [
        ({"rights": rights_with(sharing="public")}, ["rights.sharing"]),
        ({"rights": rights_with(retain_until=UNTIL)}, ["rights.retain_until"]),
        ({"rights": rights_with(derived_frames=False)}, ["rights.derived_frames"]),
        ({"rights": rights_with(basis="licensed")}, ["rights.basis"]),
        ({"sensitivity": {"level": "high"}}, ["sensitivity.level"]),
        (
            {"rights": rights_with(sharing="public", holder="Someone Else")},
            ["rights.holder", "rights.sharing"],
        ),
    ],
)
def test_the_refusal_names_every_term_that_changed(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    declared: dict[str, object],
    changed: list[str],
) -> None:
    stage_before(imported, write_corpus, data_root)

    amend_source_terms(write_recording(**declared), data_root)

    refusal = refused_verify(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["changed_terms"] == changed


def test_a_record_that_changed_outside_its_terms_still_refuses_and_names_none(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    stage_before(imported, write_corpus, data_root)

    _reimport(imported, write_recording(capture={"camera": "bench camera"}), data_root)

    refusal = refused_verify(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["changed_terms"] == []


def test_withdrawing_derivation_refuses_the_cases_of_a_staged_corpus(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    recipe = case_of("shake", "camera_shake", 1, {"amplitude": 2})
    build_corpus(write_corpus([stream_of(imported, generated_cases=[recipe])]), data_root)
    stage_corpus(CORPUS, data_root)
    assert verify_corpus_frames(CORPUS, data_root).status == "verified"

    amend_source_terms(write_recording(rights=rights_with(derived_frames=False)), data_root)

    refusal = refused_verify(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["changed_terms"] == ["rights.derived_frames"]


def test_reimporting_the_same_declaration_restores_the_pinned_record(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    stage_before(imported, write_corpus, data_root)

    again = _reimport(imported, write_recording(), data_root)

    assert again.manifest_sha256 == imported.manifest_sha256
    assert verify_corpus_frames(CORPUS, data_root).status == "verified"


def test_a_new_corpus_version_carries_the_withdrawn_rights_and_the_old_one_stays_refused(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    shared = import_source(write_recording(rights=rights_with(sharing="public")), data_root)
    public = write_corpus([stream_of(shared)], scenario_rights=_PUBLIC_SCENARIO)
    build_corpus(public, data_root)
    stage_corpus(CORPUS, data_root)

    amend_source_terms(write_recording(rights=rights_with(sharing="restricted")), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(public, data_root)
    assert caught.value.code is RefusalCode.RIGHTS_CONFLICT
    build_corpus(write_corpus([stream_of(shared)], corpus_id="pilot-v2"), data_root)
    stage_corpus("pilot-v2", data_root)
    assert verify_corpus_frames("pilot-v2", data_root).status == "verified"
    refused_verify(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
