"""Reading a staged bundle: exactly the indexed bytes, and a reference to each frame."""

import json
import os
from pathlib import Path

import pytest

from ss_track.core.canonical import sha256_bytes
from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, open_frame_bundle
from ss_track.corpus.bundles import frames
from ss_track.corpus.bundles.frames import FileDigests
from ss_track.corpus.records.sealing import sha256_file
from tests.corpus._media import FRAME_COUNT, HEIGHT, WIDTH
from tests.corpus.bundles._staged_frames import delete_frame, flip_byte, stage_two_streams
from tests.corpus.conftest import WriteCorpus, WriteRecording


@pytest.fixture
def staged(
    imported: ImportResult,
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> Path:
    return stage_two_streams(imported, media, write_recording, write_corpus, data_root)


def test_reading_a_frame_returns_exactly_the_indexed_bytes(staged: Path) -> None:
    bundle = open_frame_bundle(staged)

    pixels = bundle.read_frame(7)

    assert len(pixels) == WIDTH * HEIGHT * 3
    assert sha256_bytes(pixels) == bundle.frame_ref(7).sha256
    assert pixels != bundle.read_frame(8)


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        pytest.param(flip_byte, "hash_mismatch", id="changed"),
        pytest.param(delete_frame, "missing", id="deleted"),
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
        "content_frame_index": 3,
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


def test_a_file_with_two_names_is_hashed_once_per_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = tmp_path / "parent"
    shared.write_bytes(b"frame")
    os.link(shared, tmp_path / "case")
    single = tmp_path / "single"
    single.write_bytes(b"other")
    hashed: list[str] = []

    def counted(path: Path) -> str:
        hashed.append(path.name)
        return sha256_file(path)

    monkeypatch.setattr(frames, "sha256_file", counted)
    digests = FileDigests()

    found = {digests.sha256(tmp_path / name) for name in ("parent", "case")}
    digests.sha256(single)
    digests.sha256(single)

    assert found == {sha256_bytes(b"frame")}
    assert hashed == ["parent", "single", "single"]
