"""`corpus verify` proves the recorded rights still hold, not only that frames are intact.

Import refuses to change an imported source, so these fixtures replace a record the way an operator
must: remove the source's directory and import it again, through the real importer.
"""

import json
import logging
import shutil
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from ss_track.cli import EXIT_OK, EXIT_REFUSED, main
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    recording_declaration,
    reseal,
    stream_of,
)

_CORPUS = "pilot-v1"
_BEFORE = date(1999, 12, 31)
_UNTIL = date(2000, 1, 1)
_AFTER = date(2000, 1, 2)
_PUBLIC_SCENARIO = {"sharing": "public", "max_sensitivity": "high"}


def _rights(**changes: object) -> dict[str, object]:
    rights = recording_declaration()["rights"]
    assert isinstance(rights, dict)
    return rights | changes


def _reimport(source: ImportResult, declaration: Path, data_root: Path) -> ImportResult:
    shutil.rmtree(source.manifest_path.parent)
    return import_source(declaration, data_root)


def _refused(data_root: Path, code: RefusalCode, today: date | None = None) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(_CORPUS, data_root, today=today)
    assert caught.value.code is code
    return caught.value


def _staged(source: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> None:
    build_corpus(write_corpus([stream_of(source)]), data_root, today=_BEFORE)
    stage_corpus(_CORPUS, data_root, today=_BEFORE)


def _last_record(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    record: dict[str, object] = json.loads(caplog.records[-1].getMessage())
    return record


@pytest.fixture
def cli_root(
    data_root: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> Path:
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("DATA_DIR", str(data_root))
    return data_root


def test_a_source_reimported_as_restricted_refuses_and_exits_one(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    shared = import_source(write_recording(rights=_rights(sharing="public")), cli_root)
    declared = write_corpus([stream_of(shared)], scenario_rights=_PUBLIC_SCENARIO)
    build_corpus(declared, cli_root)
    stage_corpus(_CORPUS, cli_root)
    assert main(["corpus", "verify", "--corpus", _CORPUS]) == EXIT_OK

    closed = _reimport(shared, write_recording(rights=_rights(sharing="restricted")), cli_root)

    assert main(["corpus", "verify", "--corpus", _CORPUS]) == EXIT_REFUSED
    refusal = _last_record(caplog)
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
    source = import_source(write_recording(rights=_rights(retain_until=_UNTIL)), cli_root)
    _staged(source, write_corpus, cli_root)

    assert main(["corpus", "verify", "--corpus", _CORPUS]) == EXIT_REFUSED

    refusal = _last_record(caplog)
    assert refusal["code"] == "RETENTION_EXPIRED"
    assert refusal["details"] == {
        "source_sha256": source.source_sha256,
        "retain_until": _UNTIL.isoformat(),
    }


def test_an_unchanged_corpus_verifies_and_writes_nothing(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _staged(imported, write_corpus, cli_root)
    evidence = {path: path.read_bytes() for path in cli_root.rglob("*") if path.is_file()}

    assert main(["corpus", "verify", "--corpus", _CORPUS]) == EXIT_OK

    assert _last_record(caplog)["status"] == "verified"
    assert evidence == {path: path.read_bytes() for path in cli_root.rglob("*") if path.is_file()}


@pytest.mark.parametrize(
    ("declared", "changed"),
    [
        ({"rights": _rights(sharing="public")}, ["rights.sharing"]),
        ({"rights": _rights(retain_until=_UNTIL)}, ["rights.retain_until"]),
        ({"rights": _rights(derived_frames=False)}, ["rights.derived_frames"]),
        ({"rights": _rights(basis="licensed")}, ["rights.basis"]),
        ({"sensitivity": {"level": "high"}}, ["sensitivity.level"]),
        (
            {"rights": _rights(sharing="public", holder="Someone Else")},
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
    _staged(imported, write_corpus, data_root)

    _reimport(imported, write_recording(**declared), data_root)

    refusal = _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["changed_terms"] == changed


def test_a_record_that_changed_outside_its_terms_still_refuses_and_names_none(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _staged(imported, write_corpus, data_root)

    _reimport(imported, write_recording(capture={"camera": "bench camera"}), data_root)

    refusal = _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["changed_terms"] == []


def test_withdrawing_derivation_refuses_the_cases_of_a_staged_corpus(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    recipe = case_of("shake", "camera_shake", 1, {"amplitude": 2})
    build_corpus(write_corpus([stream_of(imported, generated_cases=[recipe])]), data_root)
    stage_corpus(_CORPUS, data_root)
    assert verify_corpus_frames(_CORPUS, data_root).status == "verified"

    _reimport(imported, write_recording(rights=_rights(derived_frames=False)), data_root)

    refusal = _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["changed_terms"] == ["rights.derived_frames"]


def test_reimporting_the_same_declaration_restores_the_pinned_record(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _staged(imported, write_corpus, data_root)

    again = _reimport(imported, write_recording(), data_root)

    assert again.manifest_sha256 == imported.manifest_sha256
    assert verify_corpus_frames(_CORPUS, data_root).status == "verified"


def test_a_new_corpus_version_carries_the_withdrawn_rights_and_the_old_one_stays_refused(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    shared = import_source(write_recording(rights=_rights(sharing="public")), data_root)
    public = write_corpus([stream_of(shared)], scenario_rights=_PUBLIC_SCENARIO)
    build_corpus(public, data_root)
    stage_corpus(_CORPUS, data_root)

    closed = _reimport(shared, write_recording(rights=_rights(sharing="restricted")), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(public, data_root)
    assert caught.value.code is RefusalCode.RIGHTS_CONFLICT
    build_corpus(write_corpus([stream_of(closed)], corpus_id="pilot-v2"), data_root)
    stage_corpus("pilot-v2", data_root)
    assert verify_corpus_frames("pilot-v2", data_root).status == "verified"
    _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)


def _remove_directory(source: ImportResult) -> None:
    shutil.rmtree(source.manifest_path.parent)


def _overwrite_record(source: ImportResult) -> None:
    source.manifest_path.chmod(0o644)
    source.manifest_path.write_text("{}", encoding="ascii")


def _reseal_old_schema(source: ImportResult) -> None:
    reseal(source.manifest_path, schema_version=1)


@pytest.mark.parametrize(
    ("damage", "code"),
    [
        (_remove_directory, RefusalCode.SOURCE_NOT_IMPORTED),
        (_overwrite_record, RefusalCode.RECORD_TAMPERED),
        (_reseal_old_schema, RefusalCode.RECORD_SCHEMA_UNSUPPORTED),
    ],
)
def test_a_source_record_that_cannot_be_read_refuses(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    damage: Callable[[ImportResult], None],
    code: RefusalCode,
) -> None:
    _staged(imported, write_corpus, data_root)

    damage(imported)

    _refused(data_root, code)


def test_every_source_of_a_corpus_is_checked(
    first: ImportResult,
    second: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    streams = [stream_of(first, stream_id="a"), stream_of(second, stream_id="b")]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus(_CORPUS, data_root)
    sharing = _rights(sharing="public")

    _reimport(second, write_recording("clip-4.mkv", rights=sharing), data_root)

    refusal = _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["stream_id"] == "b"


def test_verify_never_reads_stored_source_bytes(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    _staged(imported, write_corpus, data_root)

    next(imported.manifest_path.parent.glob("source.*")).unlink()

    assert verify_corpus_frames(_CORPUS, data_root).status == "verified"


def test_a_changed_record_refuses_before_any_frame_is_hashed(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _staged(imported, write_corpus, data_root)
    frame = data_root / "corpus" / _CORPUS / "frames" / "one" / "00000002.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"corrupted")

    _reimport(imported, write_recording(sensitivity={"level": "high"}), data_root)

    _refused(data_root, RefusalCode.SOURCE_RECORD_CHANGED)


def test_expiry_stays_the_reason_after_an_operator_removes_expired_material(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    source = import_source(write_recording(rights=_rights(retain_until=_UNTIL)), data_root)
    _staged(source, write_corpus, data_root)

    shutil.rmtree(source.manifest_path.parent)

    _refused(data_root, RefusalCode.RETENTION_EXPIRED, today=_AFTER)
    _refused(data_root, RefusalCode.SOURCE_NOT_IMPORTED, today=_UNTIL)


def test_stage_and_verify_refuse_a_changed_record_the_same_way(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _staged(imported, write_corpus, data_root)
    _reimport(imported, write_recording(sensitivity={"level": "high"}), data_root)

    for action in (stage_corpus, verify_corpus_frames):
        with pytest.raises(CorpusRefusal) as caught:
            action(_CORPUS, data_root)
        assert caught.value.code is RefusalCode.SOURCE_RECORD_CHANGED
        assert caught.value.details["changed_terms"] == ["sensitivity.level"]
