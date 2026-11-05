"""`corpus verify` checks every source record before any frame: unreadable, changed or expired."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

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
    reseal,
    stream_of,
)
from tests.corpus.sources._verify_rights import AFTER, CORPUS, UNTIL, refused_verify, stage_before


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
    stage_before(imported, write_corpus, data_root)

    damage(imported)

    refused_verify(data_root, code)


def test_every_source_of_a_corpus_is_checked(
    first: ImportResult,
    second: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    streams = [stream_of(first, stream_id="a"), stream_of(second, stream_id="b")]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus(CORPUS, data_root)
    sharing = rights_with(sharing="public")

    amend_source_terms(write_recording("clip-4.mkv", rights=sharing), data_root)

    refusal = refused_verify(data_root, RefusalCode.SOURCE_RECORD_CHANGED)
    assert refusal.details["stream_id"] == "b"


def test_verify_never_reads_stored_source_bytes(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    stage_before(imported, write_corpus, data_root)

    next(imported.manifest_path.parent.glob("source.*")).unlink()

    assert verify_corpus_frames(CORPUS, data_root).status == "verified"


def test_a_changed_record_refuses_before_any_frame_is_hashed(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    stage_before(imported, write_corpus, data_root)
    frame = data_root / "corpus" / CORPUS / "frames" / "one" / "00000002.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"corrupted")

    amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    refused_verify(data_root, RefusalCode.SOURCE_RECORD_CHANGED)


def test_expiry_stays_the_reason_after_an_operator_removes_expired_material(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    source = import_source(write_recording(rights=rights_with(retain_until=UNTIL)), data_root)
    stage_before(source, write_corpus, data_root)

    shutil.rmtree(source.manifest_path.parent)

    refused_verify(data_root, RefusalCode.RETENTION_EXPIRED, today=AFTER)
    refused_verify(data_root, RefusalCode.SOURCE_NOT_IMPORTED, today=UNTIL)


def test_stage_and_verify_refuse_a_changed_record_the_same_way(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    stage_before(imported, write_corpus, data_root)
    amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    for action in (stage_corpus, verify_corpus_frames):
        with pytest.raises(CorpusRefusal) as caught:
            action(CORPUS, data_root)
        assert caught.value.code is RefusalCode.SOURCE_RECORD_CHANGED
        assert caught.value.details["changed_terms"] == ["sensitivity.level"]
