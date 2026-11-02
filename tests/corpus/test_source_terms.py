"""Source terms are explicit, time-dependent gates, never a mutation of evidence."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from ss_track.corpus import (
    CorpusRefusal,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.declaration import load_recording_declaration
from ss_track.corpus.terms import evaluation_date
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    recording_declaration,
    reseal,
    stream_of,
)

BEFORE = date(2030, 6, 14)
UNTIL = date(2030, 6, 15)
AFTER = date(2030, 6, 16)


def _rights(**changes: object) -> dict[str, object]:
    rights = recording_declaration()["rights"]
    assert isinstance(rights, dict)
    return rights | changes


@pytest.mark.parametrize("operation", ["build", "stage", "verify"])
@pytest.mark.parametrize("today", [BEFORE, UNTIL, AFTER])
def test_retention_boundary_at_every_entrypoint(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    operation: str,
    today: date,
) -> None:
    imported = import_source(
        write_recording(rights=_rights(retain_until=UNTIL.isoformat())), data_root
    )
    declaration = write_corpus([stream_of(imported)])
    built = build_corpus(declaration, data_root, today=BEFORE)
    stage_corpus(built.corpus_id, data_root, today=BEFORE)
    evidence = {path: path.read_bytes() for path in data_root.rglob("*") if path.is_file()}

    def run() -> None:
        if operation == "build":
            assert build_corpus(declaration, data_root, today=today).status == "unchanged"
        elif operation == "stage":
            assert stage_corpus(built.corpus_id, data_root, today=today).status == "unchanged"
        else:
            assert (
                verify_corpus_frames(built.corpus_id, data_root, today=today).status == "verified"
            )

    if today == AFTER:
        with pytest.raises(CorpusRefusal) as caught:
            run()
        assert caught.value.code is RefusalCode.RETENTION_EXPIRED
        assert caught.value.details == {
            "source_sha256": imported.source_sha256,
            "retain_until": UNTIL.isoformat(),
        }
    else:
        run()
    assert evidence == {path: path.read_bytes() for path in data_root.rglob("*") if path.is_file()}


def test_expired_source_never_publishes_a_corpus(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    source = import_source(write_recording(rights=_rights(retain_until=UNTIL)), data_root)
    with pytest.raises(CorpusRefusal, match="retention") as caught:
        build_corpus(write_corpus([stream_of(source)]), data_root, today=AFTER)
    assert caught.value.code is RefusalCode.RETENTION_EXPIRED
    assert not (data_root / "corpus").exists()
    assert source.manifest_path.exists()


@pytest.mark.parametrize("permitted", [False, True])
def test_derivation_permission_controls_generated_cases_only(
    clip: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    permitted: bool,
) -> None:
    imported = import_source(write_recording(rights=_rights(derived_frames=permitted)), data_root)
    # Ordinary decoding remains allowed even when generated cases are forbidden.
    ordinary = build_corpus(write_corpus([stream_of(imported)]), data_root, today=AFTER)
    stage_corpus(ordinary.corpus_id, data_root, today=AFTER)
    recipe = case_of("shake", "camera_shake", 1, {"amplitude": 2})
    declaration = write_corpus([stream_of(imported, generated_cases=[recipe])], corpus_id="derived")
    if permitted:
        build_corpus(declaration, data_root, today=AFTER)
        assert stage_corpus("derived", data_root, today=AFTER).status == "staged"
    else:
        with pytest.raises(CorpusRefusal) as caught:
            build_corpus(declaration, data_root, today=AFTER)
        assert caught.value.code is RefusalCode.RIGHTS_CONFLICT
        assert caught.value.details["conflicts"] == [
            {
                "stream_id": "one",
                "source_sha256": imported.source_sha256,
                "field": "derived_frames",
                "source_value": False,
                "scenario_value": True,
            }
        ]
        assert not (data_root / "corpus" / "derived").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("retain_until", "2030-02-30"),
        ("retain_until", "20300615"),
        ("retain_until", "2030-W24-6"),
        ("retain_until", "2030-06-15T00:00:00"),
        ("retain_until", True),
        ("retain_until", 20300615),
        ("derived_frames", "true"),
        ("derived_frames", 1),
        ("derived_frames", None),
    ],
)
def test_invalid_terms_are_refused(
    write_recording: WriteRecording, field: str, value: object
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        load_recording_declaration(write_recording(rights=_rights(**{field: value})))
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert field in caught.value.message


@pytest.mark.parametrize("field", ["retain_until", "derived_frames"])
def test_terms_have_no_defaults(write_recording: WriteRecording, field: str) -> None:
    rights = _rights()
    del rights[field]
    with pytest.raises(CorpusRefusal, match=field):
        load_recording_declaration(write_recording(rights=rights))


def test_quoted_and_yaml_dates_seal_identically(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    first = import_source(write_recording(rights=_rights(retain_until=UNTIL)), data_root)
    second = import_source(
        write_recording(rights=_rights(retain_until=UNTIL.isoformat())), data_root
    )
    assert first.manifest_sha256 == second.manifest_sha256
    assert second.status == "unchanged"


def test_old_source_records_require_explicit_migration(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    source = import_source(write_recording(), data_root)
    reseal(source.manifest_path, schema_version=1)
    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(source)]), data_root, today=BEFORE)
    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_legacy_corpus_without_terms_is_refused(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    source = import_source(write_recording(), data_root)
    built = build_corpus(write_corpus([stream_of(source)]), data_root, today=BEFORE)
    record = yaml.safe_load(built.manifest_path.read_text())
    del record["streams"][0]["rights"]["retain_until"]
    reseal(built.manifest_path, streams=record["streams"])
    for operation in (stage_corpus, verify_corpus_frames):
        with pytest.raises(CorpusRefusal) as caught:
            operation(built.corpus_id, data_root, today=BEFORE)
        assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_default_evaluation_day_is_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    class Clock:
        @staticmethod
        def now(tz: object) -> datetime:
            assert tz is UTC
            return datetime(2030, 6, 15, tzinfo=UTC)

    monkeypatch.setattr("ss_track.corpus.terms.datetime", Clock)
    assert evaluation_date(None) == UNTIL
    assert evaluation_date(BEFORE) == BEFORE
