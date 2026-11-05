"""Frames one corpus version may share: one group, adjacent windows, plain frames and a parent."""

from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus._media import (
    FRAME_COUNT,
    HEIGHT,
    MP4_OPTIONS,
    WIDTH,
    X264_WITH_B_FRAMES,
    expected_rgb,
    remux,
    write_clip,
)
from tests.corpus._shared_frames import V1, hashes_of, stage_refused
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    encounter_of,
    group_of,
    single_group,
    stream_of,
)

_BLACK = bytes(WIDTH * HEIGHT * 3)
_WHITE = b"\xff" * (WIDTH * HEIGHT * 3)
type Content = Callable[[int, int, int], bytes]


@pytest.fixture
def import_scene(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> Callable[..., ImportResult]:
    def scene(name: str, content: Content) -> ImportResult:
        write_clip(
            media / name,
            codec="ffv1",
            pixel_format="bgr0",
            content=content,
        )
        return import_source(write_recording(name), data_root)

    return scene


def _after_lead_in(lead_in: list[bytes], shift: int) -> Content:
    """Return a scene whose first frames are `lead_in`, and whose others no other scene holds."""

    def content(index: int, width: int, height: int) -> bytes:
        if index < len(lead_in):
            return lead_in[index]
        return expected_rgb(index + shift, width, height)

    return content


def test_a_remux_in_one_group_stages_normally(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    streams = (stream_of(original, stream_id="a"), stream_of(copy, stream_id="b"))
    groups = [group_of("site-a", "development", encounter_of("enc", *streams))]
    build_corpus(write_grouped_corpus(groups), data_root)

    assert stage_corpus(V1, data_root).status == "staged"


def test_adjacent_windows_of_a_remux_share_no_frame_and_stage_normally(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    """A limit of comparing frames: `corpus-provenance` documents it, and this pins it."""
    head = {"start_frame": 0, "end_frame": 12}
    tail = {"start_frame": 12, "end_frame": FRAME_COUNT}
    groups = [
        single_group("site-a", "development", stream_of(original, stream_id="a", selection=head)),
        single_group("site-b", "locked", stream_of(copy, stream_id="b", selection=tail)),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    assert stage_corpus(V1, data_root).status == "staged"


def test_a_shared_black_frame_stages_normally(
    import_scene: Callable[..., ImportResult],
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    one = import_scene("one.mkv", _after_lead_in([_BLACK], 100))
    two = import_scene("two.mkv", _after_lead_in([_BLACK], 200))
    groups = [
        single_group("site-a", "development", stream_of(one, stream_id="a")),
        single_group("site-b", "locked", stream_of(two, stream_id="b")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    assert stage_corpus(V1, data_root).status == "staged"
    assert verify_corpus_frames(V1, data_root).status == "verified"
    shared = set(hashes_of(data_root, V1, "a")) & set(hashes_of(data_root, V1, "b"))
    assert len(shared) == 1


@pytest.mark.parametrize(
    "lead_in",
    [
        pytest.param([_BLACK] * 12, id="a-long-black-lead-in"),
        pytest.param([_BLACK] * 6 + [_WHITE] * 6, id="black-cutting-to-white"),
        pytest.param([_BLACK, _WHITE] * 6, id="a-blinking-screen"),
    ],
)
def test_a_lead_in_longer_than_a_run_stages_normally(
    import_scene: Callable[..., ImportResult],
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    lead_in: list[bytes],
) -> None:
    one = import_scene("one.mkv", _after_lead_in(lead_in, 100))
    two = import_scene("two.mkv", _after_lead_in(lead_in, 200))
    groups = [
        single_group("site-a", "development", stream_of(one, stream_id="a")),
        single_group("site-b", "locked", stream_of(two, stream_id="b")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    assert stage_corpus(V1, data_root).status == "staged"
    a, b = hashes_of(data_root, V1, "a"), hashes_of(data_root, V1, "b")
    assert a[: len(lead_in)] == b[: len(lead_in)]


def test_a_generated_case_never_compares_against_its_own_parent(
    first: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    dropped = case_of("thinned", "dropped_frames", 3, {"count": 1})
    build_corpus(write_corpus([stream_of(first, generated_cases=[dropped])]), data_root)

    assert stage_corpus(V1, data_root).status == "staged"
    assert set(hashes_of(data_root, V1, "thinned")) < set(hashes_of(data_root, V1, "one"))


def test_a_copy_with_b_frames_in_an_mp4_keeps_its_frames_when_copied_back(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    write_clip(
        media / "camera.mp4",
        codec="libx264",
        pixel_format="yuv420p",
        options=X264_WITH_B_FRAMES,
        container_options=MP4_OPTIONS,
    )
    camera = import_source(write_recording("camera.mp4"), data_root)
    remux(media / "camera.mp4", media / "archive.mkv")
    archive = import_source(write_recording("archive.mkv"), data_root)
    groups = [
        single_group("site-a", "development", stream_of(camera, stream_id="a")),
        single_group("site-b", "locked", stream_of(archive, stream_id="b")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    refusal = stage_refused(V1, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details["shared_runs"][0]["frame_count"] == FRAME_COUNT  # type: ignore[call-overload,index]
