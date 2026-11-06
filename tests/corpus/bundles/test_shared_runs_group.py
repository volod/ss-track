"""Same-group runs on hand-written indexes, beside the cross-group rule."""

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode
from ss_track.corpus.bundles.shared_runs import find_shared_runs, require_unshared_runs
from tests.corpus.bundles.test_shared_runs import _MINIMUM, _firsts, _stream


def _groups(run: object) -> set[object]:
    assert isinstance(run, dict)
    sides = run["streams"]
    assert isinstance(sides, list)
    return {side["group_id"] for side in sides}


def test_the_same_group_refusal_names_both_streams_and_the_first_frame() -> None:
    current = [_stream("a", "g", _MINIMUM, first_index=3), _stream("b", "g", _MINIMUM)]

    with pytest.raises(CorpusRefusal) as caught:
        require_unshared_runs("pilot-v2", current, [])

    runs = caught.value.details["shared_runs"]
    assert caught.value.code is RefusalCode.STREAM_OVERLAP
    assert caught.value.details["corpus_id"] == "pilot-v2"
    assert runs == find_shared_runs(current, [])
    assert isinstance(runs, list)
    assert _firsts(runs[0]) == {"a": 3, "b": 0}


def test_keeping_both_copies_does_not_name_the_predecessor() -> None:
    earlier = [_stream("old", "g", _MINIMUM, corpus_id="pilot-v1")]
    current = [_stream("a", "g", _MINIMUM), _stream("b", "g", _MINIMUM)]

    runs = find_shared_runs(current, earlier)

    assert [_firsts(run) for run in runs] == [{"a": 0, "b": 0}]
    with pytest.raises(CorpusRefusal) as caught:
        require_unshared_runs("pilot-v2", current, earlier)
    assert caught.value.code is RefusalCode.STREAM_OVERLAP


def test_same_group_pairs_are_named_in_one_order() -> None:
    streams = [_stream(name, "g", _MINIMUM) for name in ("b", "a", "c")]

    runs = find_shared_runs(streams, [])

    assert [sorted(_firsts(run)) for run in runs] == [["a", "b"], ["b", "c"], ["a", "c"]]
    assert runs == find_shared_runs(streams, [])


def test_a_cross_group_run_stays_leakage_when_the_same_group_also_overlaps() -> None:
    current = [
        _stream("a", "g1", _MINIMUM),
        _stream("b", "g1", _MINIMUM),
        _stream("c", "g2", _MINIMUM),
    ]
    runs = find_shared_runs(current, [])

    with pytest.raises(CorpusRefusal) as caught:
        require_unshared_runs("pilot-v2", current, [])

    reported = caught.value.details["shared_runs"]
    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    assert isinstance(reported, list)
    assert reported == [run for run in runs if len(_groups(run)) == 2]
    assert any(len(_groups(run)) == 1 for run in runs)
