"""A decisions file is read under its contract, and a pair is decided once, by two sources."""

from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.links.decisions import Decision, read_decisions
from tests.corpus.links._links import A, B, C, decided, write_decisions


def test_a_pair_is_keyed_in_ascending_order_whichever_order_names_it(tmp_path: Path) -> None:
    path = write_decisions(
        tmp_path / "decisions.yaml",
        decided(B, A, "related", note="same session"),
        decided(A, C, "unrelated"),
        reviewer="site lead",
    )

    decisions = read_decisions(path)

    assert decisions.reviewer == "site lead"
    assert decisions.by_pair == {
        (A, B): Decision((A, B), "related", "same session"),
        (A, C): Decision((A, C), "unrelated", None),
    }


def test_a_pair_decided_twice_is_refused_in_either_order(tmp_path: Path) -> None:
    path = write_decisions(
        tmp_path / "decisions.yaml", decided(A, B, "related"), decided(B, A, "unrelated")
    )

    with pytest.raises(CorpusRefusal) as caught:
        read_decisions(path)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "already decided" in caught.value.message


def test_a_source_paired_with_itself_is_refused(tmp_path: Path) -> None:
    path = write_decisions(tmp_path / "decisions.yaml", decided(A, A, "unrelated"))

    with pytest.raises(CorpusRefusal) as caught:
        read_decisions(path)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "one source twice" in caught.value.message


@pytest.mark.parametrize(
    ("entry", "reviewer"),
    [
        (decided(A, B, "maybe"), "reviewer"),
        (decided(A, B, "related", note="   "), "reviewer"),
        (decided(A, B, "related"), "  "),
        ({"sources": [A], "decision": "related"}, "reviewer"),
        (decided(A, B, "related", score=0.9), "reviewer"),
    ],
)
def test_a_file_outside_its_contract_is_refused(
    tmp_path: Path, entry: dict[str, object], reviewer: str
) -> None:
    path = write_decisions(tmp_path / "decisions.yaml", entry, reviewer=reviewer)

    with pytest.raises(CorpusRefusal) as caught:
        read_decisions(path)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
