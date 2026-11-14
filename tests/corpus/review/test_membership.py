"""Decisions become frozen streams: runs of included windows, refusals for what review cannot hold."""

from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.review.decisions import read_review
from ss_track.corpus.review.membership import corpus_document, review_membership
from ss_track.corpus.review.queue import Offered, ReviewQueue
from tests.corpus.review._review import RUN_ID, exclude, include, write_review

POOL_STREAMS = [
    {"stream_id": "one", "group_id": "site-b", "split": "development", "source_sha256": "a" * 64},
    {"stream_id": "two", "group_id": "site-a", "split": "calibration", "source_sha256": "b" * 64},
]
POOL: Any = {
    "decode_policy_sha256": "c" * 64,
    "scenario_rights": {"sharing": "restricted", "max_sensitivity": "high"},
    "streams": POOL_STREAMS,
}


def _offered(stream_id: str, candidate_id: str, start: int, end: int) -> Offered:
    return Offered(stream_id, candidate_id, start, end, ("audit_sample",), {})


def _queue() -> ReviewQueue:
    windows = [
        _offered("one", "pool-000", 0, 8),
        _offered("one", "pool-001", 8, 16),
        _offered("one", "pool-002", 16, 24),
        _offered("one", "pool-003", 24, 32),
        _offered("one", "sibling-1", 4, 10),
        _offered("two", "pool-000", 0, 8),
        _offered("two", "pool-002", 16, 24),
    ]
    withheld = frozenset({("three", "pool-000")})
    return ReviewQueue(RUN_ID, {item.key: item for item in windows}, withheld, 1)


def _membership(tmp_path: Path, *decisions: Any) -> Any:
    return review_membership(
        _queue(), read_review(write_review(tmp_path / "r.yaml", *decisions)), POOL
    )


def test_overlapping_and_adjacent_windows_join_and_a_gap_starts_a_new_stream(
    tmp_path: Path,
) -> None:
    membership = _membership(
        tmp_path,
        include("one", "pool-001"),
        include("one", "sibling-1", "unknown"),
        include("one", "pool-003"),
        include("two", "pool-000"),
        include("two", "pool-002"),
    )

    found = [(m.stream_id, m.start_frame, m.end_frame) for m in membership.members]
    assert found == [
        ("one.24-32", 24, 32),
        ("one.4-16", 4, 16),
        ("two.0-8", 0, 8),
        ("two.16-24", 16, 24),
    ]
    joined = next(m for m in membership.members if m.stream_id == "one.4-16")
    assert [offered.candidate_id for offered, _ in joined.candidates] == ["sibling-1", "pool-001"]
    assert [item.candidate_id for item in membership.unreviewed] == [
        "pool-000",
        "pool-002",
    ]


def test_the_declaration_keeps_each_pool_group_and_split_with_one_encounter_per_stream(
    tmp_path: Path,
) -> None:
    membership = _membership(tmp_path, include("one", "pool-000"), include("two", "pool-002"))

    document: Any = corpus_document("frozen-v1", "pilot-v1", POOL, membership.members)

    assert document["decode_policy_sha256"] == "c" * 64
    assert document["supersedes"] == "pilot-v1"
    assert [(g["group_id"], g["split"]) for g in document["groups"]] == [
        ("site-a", "calibration"),
        ("site-b", "development"),
    ]
    (encounter,) = document["groups"][0]["encounters"]
    assert encounter == {
        "encounter_id": "two.16-24",
        "streams": [
            {
                "stream_id": "two.16-24",
                "source_sha256": "b" * 64,
                "selection": {"start_frame": 16, "end_frame": 24},
            }
        ],
    }


def test_excluding_a_frame_another_decision_includes_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        _membership(tmp_path, include("one", "pool-000"), exclude("one", "sibling-1", "sensitive"))

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert caught.value.details["conflicts"] == [
        {"stream_id": "one", "candidate_id": "sibling-1", "member_stream_id": "one.0-8"}
    ]


def test_a_decision_on_a_locked_or_unoffered_window_is_refused_naming_each(
    tmp_path: Path,
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        _membership(
            tmp_path,
            include("one", "pool-000"),
            include("three", "pool-000"),
            include("two", "pool-001"),
        )

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert caught.value.details == {
        "run_id": RUN_ID,
        "locked_without_policy": [{"stream_id": "three", "candidate_id": "pool-000"}],
        "not_offered": [{"stream_id": "two", "candidate_id": "pool-001"}],
    }


@pytest.mark.parametrize(
    "decisions",
    [
        pytest.param((exclude("one", "pool-000", "no_value"),), id="nothing-included"),
        pytest.param(
            (include("one", "pool-000"), exclude("one", "pool-001", "other")), id="other-no-note"
        ),
        pytest.param((include("one", "pool-000"), include("one", "pool-000")), id="twice"),
    ],
)
def test_a_review_that_cannot_make_a_version_is_refused(
    tmp_path: Path, decisions: tuple[Any, ...]
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        _membership(tmp_path, *decisions)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_review_of_another_run_is_refused(tmp_path: Path) -> None:
    review = read_review(write_review(tmp_path / "r.yaml", include("one", "pool-000"), run_id="x"))

    with pytest.raises(CorpusRefusal) as caught:
        review_membership(_queue(), review, POOL)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_pool_stream_name_without_room_for_its_window_is_refused(tmp_path: Path) -> None:
    long_name = "s" * 61  # plus ".0-8" is 65 characters, one past the limit
    queue = ReviewQueue(
        RUN_ID, {(long_name, "pool-000"): _offered(long_name, "pool-000", 0, 8)}, frozenset(), 0
    )
    pool: Any = POOL | {"streams": [POOL_STREAMS[0] | {"stream_id": long_name}]}
    review = read_review(write_review(tmp_path / "r.yaml", include(long_name, "pool-000")))

    with pytest.raises(CorpusRefusal) as caught:
        review_membership(queue, review, pool)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "not an identifier" in caught.value.message


def test_an_unreviewed_entry_needs_no_observation_and_counts_as_undecided(tmp_path: Path) -> None:
    undecided = {"stream_id": "one", "candidate_id": "pool-002", "decision": "unreviewed"}

    membership = _membership(tmp_path, include("one", "pool-000"), undecided)

    assert ("one", "pool-002") in {item.key for item in membership.unreviewed}
    assert membership.exclusions == ()
