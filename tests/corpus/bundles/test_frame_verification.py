"""`corpus verify` names every damaged, missing or unlisted frame, and staging will not cover it."""

from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    open_frame_bundle,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.bundles.frames import FrameDamage, frame_name, frames_corrupted
from tests.corpus._media import FRAME_COUNT
from tests.corpus.bundles._staged_frames import (
    CORPUS,
    delete_frame,
    flip_byte,
    frames_refusal,
    make_writable,
    stage_two_streams,
)
from tests.corpus.conftest import WriteCorpus, WriteRecording, stream_of

_NAMED_FRAME_LIMIT = 32


@pytest.fixture
def staged(
    imported: ImportResult,
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> Path:
    return stage_two_streams(imported, media, write_recording, write_corpus, data_root)


def _truncate(path: Path) -> None:
    make_writable(path).write_bytes(path.read_bytes()[:-1])


def _append(path: Path) -> None:
    make_writable(path).write_bytes(path.read_bytes() + b"\x00")


def test_a_clean_bundle_verifies(staged: Path, data_root: Path) -> None:
    result = verify_corpus_frames(CORPUS, data_root)

    assert result.status == "verified"
    assert [bundle.stream_id for bundle in result.bundles] == ["one", "two"]
    assert {bundle.frame_count for bundle in result.bundles} == {FRAME_COUNT}


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        pytest.param(flip_byte, "hash_mismatch", id="one-byte-flipped"),
        pytest.param(_truncate, "hash_mismatch", id="truncated"),
        pytest.param(_append, "hash_mismatch", id="extended"),
        pytest.param(delete_frame, "missing", id="deleted"),
    ],
)
def test_a_corrupted_frame_fails_verification_by_name(
    staged: Path, data_root: Path, damage, reason: str
) -> None:  # type: ignore[no-untyped-def]
    damage(staged / "00000003.rgb24")

    refusal = frames_refusal(data_root)

    assert refusal.details == {
        "damaged_count": 1,
        "frames": [{"stream_id": "one", "frame": "00000003.rgb24", "reason": reason}],
    }
    assert "00000003.rgb24" in refusal.message


def test_verification_names_every_damaged_frame_across_streams(
    staged: Path, data_root: Path
) -> None:
    flip_byte(staged / "00000001.rgb24")
    delete_frame(staged / "00000002.rgb24")
    other = staged.parent / "two"
    other.chmod(0o755)
    flip_byte(other / "00000005.rgb24")

    frames = frames_refusal(data_root).details["frames"]

    assert isinstance(frames, list)
    assert [(item["stream_id"], item["frame"]) for item in frames] == [  # type: ignore[index,call-overload]
        ("one", "00000001.rgb24"),
        ("one", "00000002.rgb24"),
        ("two", "00000005.rgb24"),
    ]


def test_a_file_the_index_does_not_list_fails_verification(staged: Path, data_root: Path) -> None:
    (staged / "extra.rgb24").write_bytes(b"not a frame")

    frames = frames_refusal(data_root).details["frames"]

    assert frames == [{"stream_id": "one", "frame": "extra.rgb24", "reason": "unexpected_file"}]


def test_a_large_damage_report_stays_bounded_and_keeps_the_count() -> None:
    damage = [FrameDamage("one", frame_name(i, "rgb24"), "missing") for i in range(1000)]

    refusal = frames_corrupted(damage)

    frames = refusal.details["frames"]
    assert isinstance(frames, list)
    assert refusal.details["damaged_count"] == 1000
    assert len(frames) == _NAMED_FRAME_LIMIT


def test_staging_again_over_a_damaged_bundle_is_refused(staged: Path, data_root: Path) -> None:
    flip_byte(staged / "00000003.rgb24")

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED


def test_verifying_an_unstaged_sequence_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(CORPUS, data_root)

    assert caught.value.code is RefusalCode.BUNDLE_NOT_STAGED
    assert caught.value.details == {"stream_id": "one"}


def test_verifying_an_unbuilt_corpus_is_refused(data_root: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames("never-built", data_root)

    assert caught.value.code is RefusalCode.CORPUS_NOT_BUILT


def test_a_removed_bundle_can_be_staged_again_to_the_same_hash(
    staged: Path, data_root: Path
) -> None:
    before = open_frame_bundle(staged).bundle_sha256
    for path in staged.iterdir():
        path.unlink()
    staged.rmdir()

    result = stage_corpus(CORPUS, data_root)

    assert result.status == "staged"
    assert result.bundles[0].status == "staged"
    assert result.bundles[1].status == "unchanged"
    assert open_frame_bundle(staged).bundle_sha256 == before
