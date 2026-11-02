"""Comparing corpus versions, over hand-built records so each expected list is readable here."""

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode
from ss_track.corpus.lineage import (
    Manifest,
    Placement,
    compare_versions,
    lineage_record,
    link_field,
    read_predecessors,
    require_same_places,
    trace_lineage,
)
from tests.corpus.conftest import place_of

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64


def _stream(source: str, group: str = "site-a", split: str = "development") -> dict[str, str]:
    return {"source_sha256": source, "group_id": group, "split": split}


def _version(corpus_id: str, *streams: dict[str, str], **fields: object) -> dict[str, object]:
    return {
        "corpus_id": corpus_id,
        "manifest_sha256": f"seal-of-{corpus_id}",
        "streams": list(streams),
    } | fields


def _moved(
    corpus_id: str, streams: list[dict[str, str]], *predecessors: Manifest
) -> dict[str, object]:
    with pytest.raises(CorpusRefusal) as caught:
        require_same_places(corpus_id, streams, predecessors)
    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    return dict(caught.value.details)


def test_a_comparison_lists_what_was_added_removed_and_kept() -> None:
    delta = compare_versions([_stream(_B), _stream(_C)], [_stream(_A), _stream(_B)])

    assert delta.added == (Placement(_C, "site-a", "development"),)
    assert delta.removed == (Placement(_A, "site-a", "development"),)
    assert delta.kept == (Placement(_B, "site-a", "development"),)


def test_a_comparison_counts_sources_and_not_the_streams_cut_from_them() -> None:
    delta = compare_versions([_stream(_A), _stream(_A)], [_stream(_A)])

    assert (delta.added, delta.removed) == ((), ())
    assert delta.kept == (Placement(_A, "site-a", "development"),)


def test_a_comparison_is_sorted_by_hash_whatever_the_stream_order() -> None:
    delta = compare_versions([_stream(_C), _stream(_A), _stream(_B)], [])

    assert [place.source_sha256 for place in delta.added] == [_A, _B, _C]


def test_a_source_in_the_same_place_is_not_moved() -> None:
    earlier = _version("v1", _stream(_A))

    require_same_places("v2", [_stream(_A), _stream(_B, group="site-b", split="locked")], [earlier])


def test_a_source_moved_to_another_split_names_both_versions() -> None:
    details = _moved(
        "v2", [_stream(_A, split="locked")], _version("v1", _stream(_A, split="development"))
    )

    assert details["corpus_id"] == "v2"
    assert details["moved_sources"] == [
        {
            "source_sha256": _A,
            "from": place_of("v1", "site-a", "development"),
            "to": place_of("v2", "site-a", "locked"),
        }
    ]


def test_a_source_moved_to_another_group_in_one_split_is_refused() -> None:
    details = _moved("v2", [_stream(_A, group="site-b")], _version("v1", _stream(_A)))

    assert details["moved_sources"] == [
        {
            "source_sha256": _A,
            "from": place_of("v1", "site-a", "development"),
            "to": place_of("v2", "site-b", "development"),
        }
    ]
    assert details["moved_groups"] == []


def test_a_group_may_not_change_split_even_holding_only_new_sources() -> None:
    details = _moved("v2", [_stream(_B, split="locked")], _version("v1", _stream(_A)))

    assert details["moved_sources"] == []
    assert details["moved_groups"] == [
        {"from": place_of("v1", "site-a", "development"), "to": place_of("v2", "site-a", "locked")}
    ]


def test_every_move_is_named_at_once_in_hash_order() -> None:
    details = _moved(
        "v2",
        [_stream(_B, split="locked"), _stream(_A, split="locked")],
        _version("v1", _stream(_A), _stream(_B)),
    )

    moved = details["moved_sources"]
    assert isinstance(moved, list)
    assert [item["source_sha256"] for item in moved] == [_A, _B]


def test_a_source_dropped_and_brought_back_elsewhere_is_refused() -> None:
    v1 = _version("v1", _stream(_A), _stream(_B))
    v2 = _version("v2", _stream(_B))

    details = _moved("v3", [_stream(_A, group="held", split="locked")], v2, v1)

    moved = details["moved_sources"]
    assert isinstance(moved, list)
    assert moved[0]["from"] == place_of("v1", "site-a", "development")


def test_a_move_names_the_nearest_version_that_held_the_source() -> None:
    v1 = _version("v1", _stream(_A))
    v2 = _version("v2", _stream(_A))

    details = _moved("v3", [_stream(_A, group="held", split="locked")], v2, v1)

    moved = details["moved_sources"]
    assert isinstance(moved, list)
    assert [item["from"]["corpus_id"] for item in moved] == ["v2"]


def test_a_group_move_names_the_nearest_version_that_held_it() -> None:
    v1 = _version("v1", _stream(_A))
    v2 = _version("v2", _stream(_A))

    details = _moved("v3", [_stream(_B, split="locked")], v2, v1)

    moved = details["moved_groups"]
    assert isinstance(moved, list)
    assert [item["from"]["corpus_id"] for item in moved] == ["v2"]


def test_a_chain_links_and_reports_only_against_the_version_it_named() -> None:
    v1 = _version("v1", _stream(_A), _stream(_B))
    v2 = _version("v2", _stream(_B), _stream(_C))

    lineage = trace_lineage([_stream(_C)], [v2, v1])

    assert lineage is not None
    assert lineage.to_record() == {
        "status": "linked",
        "supersedes": "v2",
        "supersedes_manifest_sha256": "seal-of-v2",
        "compared_versions": ["v2", "v1"],
        "added": [],
        "removed": [{"source_sha256": _B, "group_id": "site-a", "split": "development"}],
        "kept": [{"source_sha256": _C, "group_id": "site-a", "split": "development"}],
    }
    assert link_field([v2, v1]) == {
        "supersedes": {"corpus_id": "v2", "manifest_sha256": "seal-of-v2"}
    }


def test_no_predecessor_compares_nothing() -> None:
    require_same_places("v1", [_stream(_A, split="locked")], [])

    assert trace_lineage([_stream(_A)], []) is None
    assert lineage_record(None) == {"status": "no_lineage"}
    assert link_field([]) == {}


def test_a_chain_is_read_nearest_first_through_each_sealed_link() -> None:
    v1 = _version("v1")
    v2 = _version("v2", supersedes={"corpus_id": "v1", "manifest_sha256": "seal-of-v1"})
    v3 = _version("v3", supersedes={"corpus_id": "v2", "manifest_sha256": "seal-of-v2"})
    versions: dict[str, Manifest] = {"v1": v1, "v2": v2, "v3": v3}

    assert read_predecessors("v3", versions.__getitem__) == [v3, v2, v1]


def test_no_named_predecessor_loads_nothing() -> None:
    assert read_predecessors(None, {}.__getitem__) == []


def test_a_link_to_a_version_that_has_since_changed_is_refused() -> None:
    v1 = _version("v1", manifest_sha256="seal-of-a-later-v1")
    v2 = _version("v2", supersedes={"corpus_id": "v1", "manifest_sha256": "seal-of-v1"})
    versions: dict[str, Manifest] = {"v1": v1, "v2": v2}

    with pytest.raises(CorpusRefusal) as caught:
        read_predecessors("v2", versions.__getitem__)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert caught.value.details == {
        "corpus_id": "v1",
        "successor_corpus_id": "v2",
        "pinned_manifest_sha256": "seal-of-v1",
        "manifest_sha256": "seal-of-a-later-v1",
    }
