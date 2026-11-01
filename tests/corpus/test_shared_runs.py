"""The shared-run rule on hand-written frame indexes."""

from collections.abc import Sequence

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode
from ss_track.corpus.shared_runs import (
    MIN_SHARED_FRAMES,
    StreamFrames,
    find_shared_runs,
    require_unshared_runs,
    stream_frames,
)

_MINIMUM = [f"frame{index}" for index in range(MIN_SHARED_FRAMES)]


def _stream(
    stream_id: str,
    group_id: str,
    hashes: Sequence[str],
    corpus_id: str = "pilot-v2",
    first_index: int = 0,
    split: str = "development",
) -> StreamFrames:
    record = {"stream_id": stream_id, "group_id": group_id, "split": split}
    indexed = enumerate(hashes, start=first_index)
    return stream_frames(corpus_id, record, indexed)


def _unique(prefix: str, count: int) -> list[str]:
    return [f"{prefix}{index}" for index in range(count)]


def _firsts(run: dict[str, object]) -> dict[str, int]:
    sides = run["streams"]
    assert isinstance(sides, list)
    return {side["stream_id"]: side["first_shared_frame"] for side in sides}


def test_the_minimum_run_is_found() -> None:
    runs = find_shared_runs([_stream("a", "g1", _MINIMUM), _stream("b", "g2", _MINIMUM)], [])

    assert runs == [
        {
            "frame_sha256": "frame0",
            "frame_count": MIN_SHARED_FRAMES,
            "streams": [
                {
                    "corpus_id": "pilot-v2",
                    "stream_id": "a",
                    "group_id": "g1",
                    "split": "development",
                    "first_shared_frame": 0,
                },
                {
                    "corpus_id": "pilot-v2",
                    "stream_id": "b",
                    "group_id": "g2",
                    "split": "development",
                    "first_shared_frame": 0,
                },
            ],
        }
    ]


def test_one_frame_short_of_the_minimum_is_not_a_run() -> None:
    short = _MINIMUM[:-1]
    one = _stream("a", "g1", ["before-a", *short, "after-a"])
    two = _stream("b", "g2", ["before-b", *short, "after-b"])

    assert find_shared_runs([one, two], []) == []


@pytest.mark.parametrize(
    "shared",
    [
        pytest.param(["black"] * 40, id="one-frame-held"),
        pytest.param(["black"] * 20 + ["white"] * 20, id="two-states"),
        pytest.param(["on", "off"] * 20, id="a-blinking-signal"),
        pytest.param(["a", "b", "c"] * 20, id="a-short-loop"),
        pytest.param(_MINIMUM[:-1] * 5, id="a-loop-just-under-the-minimum"),
    ],
)
def test_what_independent_clips_really_share_is_not_a_run(shared: list[str]) -> None:
    one = _stream("a", "g1", [*shared, *_unique("a", 20)])
    two = _stream("b", "g2", [*shared, *_unique("b", 20)])

    assert find_shared_runs([one, two], []) == []


def test_a_frame_held_in_place_counts_once() -> None:
    held = [frame for frame in _MINIMUM for _ in range(3)]

    runs = find_shared_runs([_stream("a", "g1", held), _stream("b", "g2", held)], [])

    assert [run["frame_count"] for run in runs] == [MIN_SHARED_FRAMES]


def test_a_copy_held_for_longer_is_still_found() -> None:
    held = [frame for frame in _MINIMUM for _ in range(2)]

    runs = find_shared_runs([_stream("a", "g1", held), _stream("b", "g2", _MINIMUM)], [])

    assert len(runs) == 1


def test_a_run_is_widened_back_over_frames_that_alone_would_not_count() -> None:
    lead_in = ["black", "white", "black"]
    shared = [*lead_in, *_unique("shared", 12)]
    one = _stream("a", "g1", ["only-a", *shared])
    two = _stream("b", "g2", ["only-b", "other-b", *shared], first_index=10)

    run = find_shared_runs([one, two], [])[0]

    assert _firsts(run) == {"a": 1, "b": 12}
    assert run["frame_sha256"] == "black"
    assert run["frame_count"] == 15


def test_a_run_ends_where_the_streams_part() -> None:
    shared = _unique("shared", 10)

    run = find_shared_runs(
        [_stream("a", "g1", [*shared, "x"]), _stream("b", "g2", [*shared, "y"])], []
    )[0]

    assert run["frame_count"] == 10


@pytest.mark.parametrize("names", [("a", "b"), ("b", "a")])
def test_widening_a_run_stops_at_the_start_of_either_stream(names: tuple[str, str]) -> None:
    """The frame before one stream's run must not be matched against the other's last frame."""
    with_frame_before = _stream(names[0], "g1", ["edge", *_MINIMUM])
    with_frame_after = _stream(names[1], "g2", [*_MINIMUM, "edge"])
    ordered = sorted((with_frame_before, with_frame_after), key=lambda s: s.stream_id)

    run = find_shared_runs(ordered, [])[0]

    assert _firsts(run) == {names[0]: 1, names[1]: 0}
    assert run["frame_count"] == MIN_SHARED_FRAMES


def test_of_two_runs_the_earlier_one_is_named() -> None:
    early, late = _unique("early", 10), _unique("late", 12)
    one = _stream("a", "g1", [*early, "only-a", *late])
    two = _stream("b", "g2", [*early, "only-b", *late])

    run = find_shared_runs([one, two], [])[0]

    assert run["frame_sha256"] == "early0"
    assert run["frame_count"] == 10


def test_a_looped_predecessor_names_its_first_showing() -> None:
    looped = _stream("a", "g1", [*_MINIMUM, "x", *_MINIMUM], corpus_id="pilot-v1")

    run = find_shared_runs([_stream("b", "g2", _MINIMUM)], [looped])[0]

    assert _firsts(run) == {"a": 0, "b": 0}


def test_streams_of_one_group_are_not_compared() -> None:
    assert find_shared_runs([_stream("a", "g", _MINIMUM), _stream("b", "g", _MINIMUM)], []) == []


def test_a_group_is_the_same_group_across_versions() -> None:
    earlier = _stream("a", "g", _MINIMUM, corpus_id="pilot-v1")

    assert find_shared_runs([_stream("b", "g", _MINIMUM)], [earlier]) == []


def test_a_version_answers_only_for_itself_against_its_chain() -> None:
    one = _stream("a", "g1", _MINIMUM, corpus_id="pilot-v1")
    two = _stream("b", "g2", _MINIMUM, corpus_id="pilot-v0")

    assert find_shared_runs([_stream("c", "g3", _unique("c", 20))], [one, two]) == []


def test_every_pair_is_named_in_one_order() -> None:
    earlier = [_stream("a", "g1", _MINIMUM, corpus_id="pilot-v1")]
    current = [_stream("b", "g2", _MINIMUM), _stream("c", "g3", _MINIMUM)]

    runs = find_shared_runs(current, earlier)

    assert [sorted(_firsts(run)) for run in runs] == [["a", "b"], ["a", "c"], ["b", "c"]]
    assert runs == find_shared_runs(current, earlier)


def test_a_looped_stream_names_its_first_repeat_once() -> None:
    twice = [*_MINIMUM, "x", *_MINIMUM, "y"]

    runs = find_shared_runs([_stream("a", "g1", twice), _stream("b", "g2", twice)], [])

    assert len(runs) == 1
    assert _firsts(runs[0]) == {"a": 0, "b": 0}


@pytest.mark.parametrize("count", [0, 1, MIN_SHARED_FRAMES - 1])
def test_a_stream_too_short_to_hold_a_run_is_not_compared(count: int) -> None:
    hashes = _MINIMUM[:count]

    assert find_shared_runs([_stream("a", "g1", hashes), _stream("b", "g2", hashes)], []) == []


def test_the_refusal_names_the_rule_and_every_run() -> None:
    earlier = _stream("a", "g1", _MINIMUM, corpus_id="pilot-v1", split="development")
    current = _stream("b", "g2", _MINIMUM, split="locked")

    with pytest.raises(CorpusRefusal) as caught:
        require_unshared_runs("pilot-v2", [current], [earlier])

    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    assert caught.value.details["corpus_id"] == "pilot-v2"
    assert caught.value.details["min_shared_frames"] == MIN_SHARED_FRAMES
    assert caught.value.details["shared_runs"] == find_shared_runs([current], [earlier])


def test_nothing_shared_is_no_refusal() -> None:
    require_unshared_runs("pilot-v2", [_stream("a", "g1", _MINIMUM)], [])
