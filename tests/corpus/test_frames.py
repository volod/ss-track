import json
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    open_frame_bundle,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.frames import FrameDamage, frame_name, frames_corrupted
from ss_track.corpus.sealed import seal, sha256_bytes, sha256_file
from tests.corpus._media import FRAME_COUNT, HEIGHT, WIDTH, write_clip
from tests.corpus.conftest import WriteCorpus, WriteRecording, reseal, stream_of

_CORPUS = "pilot-v1"
_NAMED_FRAME_LIMIT = 32


@pytest.fixture
def staged(
    imported: ImportResult,
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> Path:
    """Return the directory of one staged bundle, writable so a test can damage it."""
    write_clip(media / "other.mkv", width=WIDTH + 2)
    other = import_source(write_recording("other.mkv"), data_root)
    streams = [stream_of(imported), stream_of(other, stream_id="two")]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus(_CORPUS, data_root)
    directory = data_root / "corpus" / _CORPUS / "frames" / "one"
    directory.chmod(0o755)
    return directory


def _writable(path: Path) -> Path:
    path.chmod(0o644)
    return path


def _flip_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    _writable(path).write_bytes(data)


def _truncate(path: Path) -> None:
    _writable(path).write_bytes(path.read_bytes()[:-1])


def _append(path: Path) -> None:
    _writable(path).write_bytes(path.read_bytes() + b"\x00")


def _delete(path: Path) -> None:
    path.unlink()


def _refusal_of(data_root: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(_CORPUS, data_root)
    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    return caught.value


def test_a_bundle_from_another_schema_is_refused_by_name(staged: Path) -> None:
    reseal(staged / "manifest.json", schema_version=1)

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(staged)

    assert caught.value.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_a_clean_bundle_verifies(staged: Path, data_root: Path) -> None:
    result = verify_corpus_frames(_CORPUS, data_root)

    assert result.status == "verified"
    assert [bundle.stream_id for bundle in result.bundles] == ["one", "two"]
    assert {bundle.frame_count for bundle in result.bundles} == {FRAME_COUNT}


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        pytest.param(_flip_byte, "hash_mismatch", id="one-byte-flipped"),
        pytest.param(_truncate, "hash_mismatch", id="truncated"),
        pytest.param(_append, "hash_mismatch", id="extended"),
        pytest.param(_delete, "missing", id="deleted"),
    ],
)
def test_a_corrupted_frame_fails_verification_by_name(
    staged: Path, data_root: Path, damage, reason: str
) -> None:  # type: ignore[no-untyped-def]
    damage(staged / "00000003.rgb24")

    refusal = _refusal_of(data_root)

    assert refusal.details == {
        "damaged_count": 1,
        "frames": [{"stream_id": "one", "frame": "00000003.rgb24", "reason": reason}],
    }
    assert "00000003.rgb24" in refusal.message


def test_verification_names_every_damaged_frame_across_streams(
    staged: Path, data_root: Path
) -> None:
    _flip_byte(staged / "00000001.rgb24")
    _delete(staged / "00000002.rgb24")
    other = staged.parent / "two"
    other.chmod(0o755)
    _flip_byte(other / "00000005.rgb24")

    frames = _refusal_of(data_root).details["frames"]

    assert isinstance(frames, list)
    assert [(item["stream_id"], item["frame"]) for item in frames] == [  # type: ignore[index,call-overload]
        ("one", "00000001.rgb24"),
        ("one", "00000002.rgb24"),
        ("two", "00000005.rgb24"),
    ]


def test_a_file_the_index_does_not_list_fails_verification(staged: Path, data_root: Path) -> None:
    (staged / "extra.rgb24").write_bytes(b"not a frame")

    frames = _refusal_of(data_root).details["frames"]

    assert frames == [{"stream_id": "one", "frame": "extra.rgb24", "reason": "unexpected_file"}]


def test_a_large_damage_report_stays_bounded_and_keeps_the_count() -> None:
    damage = [FrameDamage("one", frame_name(i, "rgb24"), "missing") for i in range(1000)]

    refusal = frames_corrupted(damage)

    frames = refusal.details["frames"]
    assert isinstance(frames, list)
    assert refusal.details["damaged_count"] == 1000
    assert len(frames) == _NAMED_FRAME_LIMIT


def test_staging_again_over_a_damaged_bundle_is_refused(staged: Path, data_root: Path) -> None:
    _flip_byte(staged / "00000003.rgb24")

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED


def test_verifying_an_unstaged_sequence_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.BUNDLE_NOT_STAGED
    assert caught.value.details == {"stream_id": "one"}


def test_verifying_an_unbuilt_corpus_is_refused(data_root: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames("never-built", data_root)

    assert caught.value.code is RefusalCode.CORPUS_NOT_BUILT


def test_reading_a_frame_returns_exactly_the_indexed_bytes(staged: Path) -> None:
    bundle = open_frame_bundle(staged)

    pixels = bundle.read_frame(7)

    assert len(pixels) == WIDTH * HEIGHT * 3
    assert sha256_bytes(pixels) == bundle.frame_ref(7).sha256
    assert pixels != bundle.read_frame(8)


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        pytest.param(_flip_byte, "hash_mismatch", id="changed"),
        pytest.param(_delete, "missing", id="deleted"),
    ],
)
def test_a_damaged_frame_cannot_be_read(staged: Path, damage, reason: str) -> None:  # type: ignore[no-untyped-def]
    bundle = open_frame_bundle(staged)
    damage(staged / "00000004.rgb24")

    with pytest.raises(CorpusRefusal) as caught:
        bundle.read_frame(4)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert caught.value.details["frames"] == [
        {"stream_id": "one", "frame": "00000004.rgb24", "reason": reason}
    ]
    assert bundle.read_frame(5)


@pytest.mark.parametrize("frame_index", [-1, FRAME_COUNT, FRAME_COUNT + 100])
def test_a_frame_outside_the_bundle_is_refused(staged: Path, frame_index: int) -> None:
    bundle = open_frame_bundle(staged)

    for action in (bundle.read_frame, bundle.frame_ref):
        with pytest.raises(CorpusRefusal) as caught:
            action(frame_index)
        assert caught.value.code is RefusalCode.FRAME_NOT_IN_BUNDLE
        assert caught.value.details["frame_index"] == frame_index


def test_a_frame_ref_identifies_the_frame_and_how_to_reach_it(
    staged: Path, imported: ImportResult
) -> None:
    bundle = open_frame_bundle(staged)

    ref = bundle.frame_ref(3)

    assert ref.to_record() == {
        "stream_id": "one",
        "source_sha256": imported.source_sha256,
        "frame_index": 3,
        "pts": 120,
        "time_base": "1/1000",
        "timestamp_quality": "derived",
        "capture_clock_evidence": None,
        "width": WIDTH,
        "height": HEIGHT,
        "pixel_format": "rgb24",
        "transform": "identity",
        "bundle_sha256": bundle.bundle_sha256,
        "frame_name": "00000003.rgb24",
        "sha256": sha256_file(staged / "00000003.rgb24"),
    }
    assert json.dumps(ref.to_record())


def test_frame_refs_list_every_frame_in_presentation_order(staged: Path) -> None:
    bundle = open_frame_bundle(staged)

    assert len(bundle) == FRAME_COUNT
    assert [ref.frame_index for ref in bundle.frame_refs()] == list(range(FRAME_COUNT))


def test_an_edited_record_is_refused(staged: Path) -> None:
    path = _writable(staged / "manifest.json")
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
    _writable(path).write_text(json.dumps(seal(record)), encoding="ascii")

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(staged)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED


def test_a_removed_bundle_can_be_staged_again_to_the_same_hash(
    staged: Path, data_root: Path
) -> None:
    before = open_frame_bundle(staged).bundle_sha256
    for path in staged.iterdir():
        path.unlink()
    staged.rmdir()

    result = stage_corpus(_CORPUS, data_root)

    assert result.status == "staged"
    assert result.bundles[0].status == "staged"
    assert result.bundles[1].status == "unchanged"
    assert open_frame_bundle(staged).bundle_sha256 == before
