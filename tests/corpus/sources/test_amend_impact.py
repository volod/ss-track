"""An amendment lists every corpus version that pins the record it replaced."""

import json
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK
from ss_track.corpus import (
    ImportResult,
    amend_source_terms,
    build_corpus,
    redecode_source,
    stage_corpus,
)
from ss_track.corpus.bundles.frames import frames_root
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from ss_track.corpus.records.projections import OTHER_SCHEMA
from ss_track.corpus.versions.builder import BuildResult
from ss_track.corpus.versions.unlinked import UNREADABLE
from tests.corpus._amending import evidence
from tests.corpus.conftest import WriteCorpus, WriteRecording, last_record, reseal, stream_of
from tests.corpus.versions._unlinked import plant

_UPGRADED = DecodePolicy(decoder="pyav", decoder_version="99", ffmpeg_version="99")


def _build(
    write_corpus: WriteCorpus, data_root: Path, corpus_id: str, source: ImportResult
) -> BuildResult:
    return build_corpus(write_corpus([stream_of(source)], corpus_id=corpus_id), data_root)


def _version(data_root: Path, corpus_id: str) -> dict[str, str]:
    return {"corpus_id": corpus_id, "frames_directory": str(frames_root(data_root, corpus_id))}


def _narrow(write_recording: WriteRecording, source: ImportResult) -> Path:
    """Declare the source by its hash, so the amendment does not depend on the clip's file name."""
    return write_recording(
        "missing.mkv", sha256=source.source_sha256, sensitivity={"level": "high"}
    )


def test_an_amendment_no_version_pins_omits_the_listing(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    result = amend_source_terms(_narrow(write_recording, imported), data_root)

    assert result.status == "amended"
    assert "impact" not in result.to_record()


def test_one_state_lists_pinning_versions_and_names_what_it_cannot_read(
    first: ImportResult,
    second: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _build(write_corpus, cli_root, "zeta", first)
    _build(write_corpus, cli_root, "other", second)
    reseal(_build(write_corpus, cli_root, "beta", first).manifest_path, schema_version=2)
    reseal(_build(write_corpus, cli_root, "z-old", first).manifest_path, schema_version=1)
    _build(write_corpus, cli_root, "alpha", first)
    plant(cli_root, "m-broken", "{")
    gap = plant(cli_root, "a-gap", "{}").parent
    (cli_root / "corpus" / "notes").mkdir()
    hidden = cli_root / "corpus" / ".hidden"
    hidden.mkdir()
    (hidden / "manifest.json").write_text("{", encoding="ascii")
    stage_corpus("alpha", cli_root)
    frames = evidence(frames_root(cli_root, "alpha"))
    assert not frames_root(cli_root, "zeta").exists()
    narrowed = _narrow(write_recording, first)
    gap.chmod(0)
    try:
        assert main(["import", "--source", str(narrowed), "--amend-terms"]) == EXIT_OK
        record = last_record(caplog)
        assert record["status"] == "amended"
        assert record["replaced_manifest_sha256"] == first.manifest_sha256
        assert record["impact"] == {
            "versions": [
                _version(cli_root, "alpha"),
                _version(cli_root, "beta"),
                _version(cli_root, "zeta"),
            ],
            "not_compared": [
                {"corpus_id": "a-gap", "reason": UNREADABLE},
                {"corpus_id": "m-broken", "reason": UNREADABLE},
                {"corpus_id": "z-old", "reason": OTHER_SCHEMA},
            ],
        }
        assert main(["import", "--source", str(narrowed), "--amend-terms"]) == EXIT_OK
        again = last_record(caplog)
        assert again["status"] == "unchanged"
        assert "impact" not in again
        assert evidence(frames_root(cli_root, "alpha")) == frames
    finally:
        gap.chmod(0o755)


def test_a_version_is_listed_once_however_many_streams_pin_the_record(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    built = _build(write_corpus, data_root, "pilot-v1", imported)
    record = json.loads(built.manifest_path.read_text(encoding="ascii"))
    streams = record["streams"]
    assert isinstance(streams, list)
    copy = dict(streams[0])
    copy["stream_id"] = "two"
    reseal(built.manifest_path, streams=[streams[0], copy])

    result = amend_source_terms(_narrow(write_recording, imported), data_root)

    assert result.to_record()["impact"] == {"versions": [_version(data_root, "pilot-v1")]}


def test_an_unreadable_corpus_directory_does_not_fail_the_amendment(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _build(write_corpus, data_root, "pilot-v1", imported)
    corpus = data_root / "corpus"
    corpus.chmod(0)
    try:
        result = amend_source_terms(_narrow(write_recording, imported), data_root)
    finally:
        corpus.chmod(0o755)

    assert result.status == "amended"
    assert result.replaced_manifest_sha256 == imported.manifest_sha256
    assert result.manifest_path.is_file()
    assert result.to_record()["impact"] == {"scan": UNREADABLE}


def test_a_redecode_lists_versions_that_pin_the_replaced_record(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declaration = write_recording()
    _build(write_corpus, cli_root, "pilot-v1", imported)
    unchanged = redecode_source(declaration, cli_root)
    assert unchanged.status == "unchanged"
    assert "impact" not in unchanged.to_record()
    monkeypatch.setattr("ss_track.corpus.sources.redecode.current_decode_policy", lambda: _UPGRADED)

    assert main(["import", "--source", str(declaration), "--redecode"]) == EXIT_OK

    record = last_record(caplog)
    assert record["status"] == "redecoded"
    assert record["impact"] == {"versions": [_version(cli_root, "pilot-v1")]}
