"""Opening a bundle from its sealed record refuses one of another schema, or one that changed."""

import json
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, open_frame_bundle
from tests._sealing import self_sealed
from tests.corpus.bundles._staged_frames import make_writable, stage_two_streams
from tests.corpus.conftest import WriteCorpus, WriteRecording, reseal


@pytest.fixture
def staged(
    imported: ImportResult,
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> Path:
    return stage_two_streams(imported, media, write_recording, write_corpus, data_root)


def test_a_bundle_from_another_schema_is_refused_by_name(staged: Path) -> None:
    reseal(staged / "manifest.json", schema_version=1)

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(staged)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_an_edited_record_is_refused(staged: Path) -> None:
    path = make_writable(staged / "manifest.json")
    path.write_text(path.read_text(encoding="ascii").replace('"rgb24"', '"bgr24"'), "ascii")

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(staged)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_a_record_whose_index_no_longer_matches_the_bundle_hash_is_refused(staged: Path) -> None:
    path = staged / "manifest.json"
    record = json.loads(path.read_text(encoding="ascii"))
    record["identity"]["frames"][0]["sha256"] = "0" * 64
    reseal(path, identity=record["identity"])

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(staged)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_an_incomplete_record_is_refused(staged: Path) -> None:
    path = staged / "manifest.json"
    record = json.loads(path.read_text(encoding="ascii"))
    del record["identity"], record["manifest_sha256"]
    make_writable(path).write_text(json.dumps(self_sealed(record)), encoding="ascii")

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(staged)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
