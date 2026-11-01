"""Remuxed copies inside one corpus version, from real media through the exit status."""

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.cli import EXIT_OK, EXIT_REFUSED, main
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
from tests.corpus._shared_frames import (
    V1,
    V2,
    frame_set,
    hashes_of,
    named,
    sides,
    single,
    stage_refused,
)
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    encounter_of,
    group_of,
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


def test_a_remux_keeps_every_decoded_frame_and_changes_every_source_hash(
    copy: ImportResult,
    original: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    """The fixture is what the rule assumes, or nothing below tests it."""
    streams = [stream_of(original, stream_id="one"), stream_of(copy, stream_id="two")]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus(V1, data_root)

    assert hashes_of(data_root, V1, "one") == hashes_of(data_root, V1, "two")


@pytest.mark.parametrize(
    "splits",
    [
        pytest.param(("development", "locked"), id="across-splits"),
        pytest.param(("development", "development"), id="inside-one-split"),
    ],
)
def test_a_remux_in_two_groups_is_leakage_naming_both_streams(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    splits: tuple[str, str],
) -> None:
    groups = [
        single("site-a", splits[0], stream_of(original, stream_id="kept")),
        single("site-b", splits[1], stream_of(copy, stream_id="held-out")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    refusal = stage_refused(V1, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert sides(refusal) == [
        {
            "corpus_id": V1,
            "stream_id": "held-out",
            "group_id": "site-b",
            "split": splits[1],
            "first_shared_frame": 0,
        },
        {
            "corpus_id": V1,
            "stream_id": "kept",
            "group_id": "site-a",
            "split": splits[0],
            "first_shared_frame": 0,
        },
    ]
    runs = refusal.details["shared_runs"]
    assert runs[0]["frame_count"] == FRAME_COUNT  # type: ignore[call-overload,index]
    assert runs[0]["frame_sha256"] == hashes_of(data_root, V1, "kept")[0]  # type: ignore[call-overload,index]


def test_a_refusal_reaches_the_exit_status_and_leaves_noframe_set(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    case = case_of("shaken", "camera_shake", 1, {"amplitude": 2})
    groups = [
        single("site-a", "development", stream_of(original, stream_id="a", generated_cases=[case])),
        single("site-b", "locked", stream_of(copy, stream_id="b")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)
    monkeypatch.setenv("DATA_DIR", str(data_root))

    with caplog.at_level(logging.INFO):
        assert main(["corpus", "stage", "--corpus", V1]) == EXIT_REFUSED

    assert json.loads(caplog.messages[-1])["code"] == "SPLIT_LEAKAGE"
    assert not frame_set(data_root, V1).exists()
    assert not (data_root / "corpus" / V1 / "frames" / "shaken").exists()
    assert main(["corpus", "verify", "--corpus", V1]) == EXIT_REFUSED
    assert json.loads(caplog.messages[-1])["code"] == "BUNDLE_NOT_STAGED"


def test_a_cut_copy_names_where_each_stream_first_shows_the_frame(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    """Every MJPEG packet is a keyframe, so a copy can start anywhere, as `-ss -c copy` would."""
    write_clip(media / "whole.mkv")
    whole = import_source(write_recording("whole.mkv"), data_root)
    remux(media / "whole.mkv", media / "cut.mkv", start_packet=9)
    cut = import_source(write_recording("cut.mkv"), data_root)
    groups = [
        single("site-a", "development", stream_of(whole, stream_id="whole")),
        single("site-b", "locked", stream_of(cut, stream_id="cut")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    refusal = stage_refused(V1, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert named(refusal, "stream_id") == ["cut", "whole"]
    assert named(refusal, "first_shared_frame") == [0, 9]


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
        single("site-a", "development", stream_of(original, stream_id="a", selection=head)),
        single("site-b", "locked", stream_of(copy, stream_id="b", selection=tail)),
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
        single("site-a", "development", stream_of(one, stream_id="a")),
        single("site-b", "locked", stream_of(two, stream_id="b")),
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
        single("site-a", "development", stream_of(one, stream_id="a")),
        single("site-b", "locked", stream_of(two, stream_id="b")),
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
        single("site-a", "development", stream_of(camera, stream_id="a")),
        single("site-b", "locked", stream_of(archive, stream_id="b")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    refusal = stage_refused(V1, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details["shared_runs"][0]["frame_count"] == FRAME_COUNT  # type: ignore[call-overload,index]


def test_stage_and_verify_report_one_result_as_json(
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    groups = [single("site-a", "development", stream_of(first, stream_id="a"))]
    build_corpus(write_grouped_corpus(groups, corpus_id=V1), data_root)
    build_corpus(write_grouped_corpus(groups, corpus_id=V2, supersedes=V1), data_root)
    monkeypatch.setenv("DATA_DIR", str(data_root))

    with caplog.at_level(logging.INFO):
        assert main(["corpus", "stage", "--corpus", V2]) == EXIT_OK
        staged = json.loads(caplog.messages[-1])
        assert main(["corpus", "stage", "--corpus", V2]) == EXIT_OK
        repeated = json.loads(caplog.messages[-1])
        assert main(["corpus", "verify", "--corpus", V2]) == EXIT_OK
        verified = json.loads(caplog.messages[-1])

    expected = {
        "min_shared_frames": 8,
        "compared_versions": [],
        "not_compared": [{"corpus_id": V1, "reason": "no_frame_set", "stream_ids": []}],
    }
    assert staged["shared_frames"] == repeated["shared_frames"] == expected
    assert verified["shared_frames"] == expected
