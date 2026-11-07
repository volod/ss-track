"""ss-video matches become windows of staged frames only through the hash join and the slot rule."""

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.siblings.video_hints import (
    HintSource,
    HintWindow,
    StreamTiming,
    map_hints,
    read_hint_source,
)

SOURCE = "a" * 64
OTHER = "b" * 64
COMMIT = "703e3c943dbc960a16cbc859680172c5a7ba5255"


def _sequence(**changes: Any) -> dict[str, Any]:
    pts = [index * 40 for index in range(24)]  # 25 frames per second, in milliseconds
    return {"time_base": "1/1000", "pts": pts, "video_stream_count": 1} | changes


def _timing(stream_id: str = "one", start: int = 0, end: int = 24, **changes: Any) -> StreamTiming:
    return StreamTiming(stream_id, SOURCE, start, end, _sequence(**changes))


def _source(*matches: tuple[str, float]) -> HintSource:
    return HintSource("ss-video-1", "ss-video", COMMIT, "8.0.1", "5/1", tuple(matches))


def test_a_match_names_the_frames_of_its_slot() -> None:
    mapping = map_hints(_source((SOURCE, 0.6), (SOURCE, 0.6)), [_timing()])

    # At 25 per second, slot 3 holds the frames from 0.5 s up to 0.7 s: 13 to 17.
    assert mapping.windows == {HintWindow("one", 3, 13, 18)}
    assert (mapping.read, mapping.mapped, mapping.unmapped) == (2, 2, Counter())


def test_every_stream_of_the_joined_source_gets_its_window() -> None:
    timings = [_timing("head", 0, 12), _timing("tail", 12, 24)]

    mapping = map_hints(_source((SOURCE, 0.2), (SOURCE, 0.8)), timings)

    assert sorted(mapping.windows) == [HintWindow("head", 1, 3, 8), HintWindow("tail", 4, 18, 23)]


@pytest.mark.parametrize(
    ("match", "timing", "reason"),
    [
        ((OTHER, 0.6), _timing(), "no_hash_join"),
        ((SOURCE, 0.61), _timing(), "not_on_slot"),
        ((SOURCE, 0.6), _timing(video_stream_count=2), "multi_stream_source"),
        ((SOURCE, 0.6), _timing(time_base=None), "missing_timestamps"),
        ((SOURCE, 0.6), _timing(pts=[0, None, 80]), "missing_timestamps"),
        ((SOURCE, 4.0), _timing(), "slot_out_of_range"),
        ((SOURCE, 0.6), _timing(start=0, end=15), "outside_bundle"),
        ((SOURCE, 0.4), _timing(pts=[0, 1000, 2000]), "empty_slot"),
    ],
)
def test_a_match_that_names_no_window_is_counted_under_its_reason(
    match: tuple[str, float], timing: StreamTiming, reason: str
) -> None:
    mapping = map_hints(_source(match), [timing])

    assert mapping.windows == set()
    assert mapping.matches() == {
        "read": 1,
        "mapped": 0,
        "unmapped": [{"reason": reason, "count": 1}],
    }


def _write(path: Path, **changes: Any) -> Path:
    document = {
        "schema_version": 1,
        "project": "ss-video",
        "commit": COMMIT,
        "ffmpeg_version": "8.0.1-3ubuntu2+esm5",
        "sample_rate": "5/1",
        "matches": [{"file_sha256": SOURCE, "t_sec": 0.6}],
    } | changes
    path.write_text(yaml.safe_dump(document), encoding="ascii")
    return path


def test_a_hint_file_is_read_under_its_contract(tmp_path: Path) -> None:
    source = read_hint_source(_write(tmp_path / "hints.yaml"), "ss-video-1")

    assert source.matches == ((SOURCE, 0.6),)
    assert source.to_run(map_hints(source, [_timing()]))["matches"]["mapped"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"commit": "main"},
        {"sample_rate": "5"},
        {"matches": [{"t_sec": 0.6}]},
        {"matches": [{"file_sha256": SOURCE, "t_sec": -1}]},
        {"ffmpeg_version": " "},
    ],
)
def test_a_hint_file_without_its_join_or_sampling_facts_is_refused(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_hint_source(_write(tmp_path / "hints.yaml", **changes), "ss-video-1")

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
