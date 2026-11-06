"""Remuxed copies inside one corpus version that are leakage, from real media to the exit status."""

import logging
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import ImportResult, RefusalCode, build_corpus, import_source
from tests.corpus._media import (
    FRAME_COUNT,
    remux,
    write_clip,
)
from tests.corpus._shared_frames import V1, V2, frame_set, hashes_of, named, sides, stage_refused
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    last_record,
    single_group,
    stream_of,
)


def test_a_remux_keeps_every_decoded_frame_and_changes_every_source_hash(
    copy: ImportResult,
    original: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    """The fixture is what the rule assumes, or nothing below tests it."""
    streams = [stream_of(original, stream_id="one"), stream_of(copy, stream_id="two")]
    build_corpus(write_corpus(streams), data_root)
    stage_refused(V1, data_root, RefusalCode.STREAM_OVERLAP)

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
        single_group("site-a", splits[0], stream_of(original, stream_id="kept")),
        single_group("site-b", splits[1], stream_of(copy, stream_id="held-out")),
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
        single_group(
            "site-a", "development", stream_of(original, stream_id="a", generated_cases=[case])
        ),
        single_group("site-b", "locked", stream_of(copy, stream_id="b")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)
    monkeypatch.setenv("DATA_DIR", str(data_root))

    with caplog.at_level(logging.INFO):
        assert main(["corpus", "stage", "--corpus", V1]) == EXIT_REFUSED

    assert last_record(caplog)["code"] == "SPLIT_LEAKAGE"
    assert not frame_set(data_root, V1).exists()
    assert not (data_root / "corpus" / V1 / "frames" / "shaken").exists()
    assert main(["corpus", "verify", "--corpus", V1]) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "BUNDLE_NOT_STAGED"


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
        single_group("site-a", "development", stream_of(whole, stream_id="whole")),
        single_group("site-b", "locked", stream_of(cut, stream_id="cut")),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    refusal = stage_refused(V1, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert named(refusal, "stream_id") == ["cut", "whole"]
    assert named(refusal, "first_shared_frame") == [0, 9]


def test_stage_and_verify_report_one_result_as_json(
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    groups = [single_group("site-a", "development", stream_of(first, stream_id="a"))]
    build_corpus(write_grouped_corpus(groups, corpus_id=V1), data_root)
    build_corpus(write_grouped_corpus(groups, corpus_id=V2, supersedes=V1), data_root)
    monkeypatch.setenv("DATA_DIR", str(data_root))

    with caplog.at_level(logging.INFO):
        assert main(["corpus", "stage", "--corpus", V2]) == EXIT_OK
        staged = last_record(caplog)
        assert main(["corpus", "stage", "--corpus", V2]) == EXIT_OK
        repeated = last_record(caplog)
        assert main(["corpus", "verify", "--corpus", V2]) == EXIT_OK
        verified = last_record(caplog)

    expected = {
        "min_shared_frames": 8,
        "compared_versions": [],
        "not_compared": [{"corpus_id": V1, "reason": "no_frame_set", "stream_ids": []}],
    }
    assert staged["shared_frames"] == repeated["shared_frames"] == expected
    assert verified["shared_frames"] == expected
