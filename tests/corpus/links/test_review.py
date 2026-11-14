"""Flags and decisions become links between recordings in different groups; related ones refuse."""

from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.links.decisions import Decisions, read_decisions
from ss_track.corpus.links.review import Flag, require_no_related_links, review_links
from tests.corpus.links._links import A, B, C, D, decided, stream, write_decisions

STREAMS = [
    stream("a0", A, "site-a"),
    stream("a1", A, "site-a"),
    stream("b0", B, "site-b"),
    stream("c0", C, "held", "locked"),
    stream("d0", D, "site-a"),
]


def _decisions(tmp_path: Path, *entries: dict[str, object]) -> Decisions:
    return read_decisions(write_decisions(tmp_path / "decisions.yaml", *entries))


def test_an_undecided_flag_across_splits_is_an_unresolved_link_of_its_two_recordings() -> None:
    flags = [
        Flag("luma-grid-16", None, 0.95, ("a1", "c0")),
        Flag("luma-grid-16", None, 0.97, ("a0", "c0")),
        Flag("background-cosine", "clip", 0.9, ("a0", "c0")),
    ]

    review = review_links(STREAMS, flags, None)

    assert review.status == "unresolved"
    assert [link.to_record() for link in review.links] == [
        {
            "sources": [
                {
                    "source_sha256": A,
                    "group_id": "site-a",
                    "split": "development",
                    "stream_ids": ["a0", "a1"],
                },
                {"source_sha256": C, "group_id": "held", "split": "locked", "stream_ids": ["c0"]},
            ],
            "cross_split": True,
            "evidence": [
                {
                    "method": "background-cosine",
                    "extractor_id": "clip",
                    "similarity": 0.9,
                    "stream_ids": ["a0", "c0"],
                },
                {"method": "luma-grid-16", "similarity": 0.97, "stream_ids": ["a0", "c0"]},
            ],
            "status": "unresolved",
        }
    ]


def test_a_flag_inside_one_group_is_no_link() -> None:
    review = review_links(STREAMS, [Flag("luma-grid-16", None, 0.99, ("a0", "d0"))], None)

    assert review.links == ()
    assert review.status == "clear"


def test_an_unrelated_decision_keeps_the_groups_apart_and_clears_the_link(tmp_path: Path) -> None:
    flags = [Flag("luma-grid-16", None, 0.95, ("b0", "c0"))]

    review = review_links(STREAMS, flags, _decisions(tmp_path, decided(C, B, "unrelated")))

    require_no_related_links("pilot-v1", review)
    assert [link.status for link in review.links] == ["unrelated"]
    assert review.links[0].to_record()["decision"] == {"decision": "unrelated"}
    assert review.status == "clear"


@pytest.mark.parametrize(("other", "cross_split"), [(B, False), (C, True)])
def test_a_related_decision_across_groups_refuses_in_one_split_or_two(
    tmp_path: Path, other: str, cross_split: bool
) -> None:
    decisions = _decisions(tmp_path, decided(A, other, "related", note="same flight"))
    review = review_links(STREAMS, [], decisions)

    with pytest.raises(CorpusRefusal) as caught:
        require_no_related_links("pilot-v1", review)

    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    links: Any = caught.value.details["links"]
    assert [link["cross_split"] for link in links] == [cross_split]
    assert links[0]["evidence"] == []
    assert links[0]["decision"] == {"decision": "related", "note": "same flight"}


def test_a_decision_that_names_no_link_is_reported_with_why(tmp_path: Path) -> None:
    decisions = _decisions(
        tmp_path,
        decided(A, D, "related"),
        decided(A, "e" * 64, "unrelated"),
    )

    review = review_links(STREAMS, [], decisions)

    require_no_related_links("pilot-v1", review)
    assert review.links == ()
    assert review.outside_records() == [
        {"sources": [A, D], "decision": "related", "reason": "same_group"},
        {"sources": [A, "e" * 64], "decision": "unrelated", "reason": "not_in_corpus"},
    ]


def test_the_strongest_flag_of_a_method_wins_and_a_tie_goes_to_the_first_pair() -> None:
    flags = [
        Flag("luma-grid-16", None, 0.93, ("a1", "b0")),
        Flag("luma-grid-16", None, 0.93, ("a0", "b0")),
        Flag("luma-grid-16", None, 0.91, ("a0", "b0")),
    ]

    (link,) = review_links(STREAMS, flags, None).links

    assert [flag.stream_ids for flag in link.evidence] == [("a0", "b0")]
