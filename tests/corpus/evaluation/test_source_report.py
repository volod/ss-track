"""Per-source costs, exclusions and the paired review budget on a comparison."""

import pytest

from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.evaluation.domains import CollectionId
from ss_track.corpus.evaluation.inputs import Evidence
from ss_track.corpus.evaluation.membership import UNREAD, BoundStream
from ss_track.corpus.evaluation.report import compare
from tests.corpus.evaluation._budget import _HASH, STREAM, Window, _evaluate

_MATCHED = (
    Window("a", sampled=True, uniform_selected=True, observation="target_present"),
    Window("b", sampled=True, diverse_selected=True, observation="target_absent"),
)
_OVERLAP = (
    Window("a", sampled=True, diverse_selected=True, observation="target_present"),
    Window("b", sampled=True, diverse_selected=True, observation="target_present"),
    Window("c", uniform_selected=True, observation="target_absent"),
    Window("d", uniform_selected=True, observation="target_absent"),
)

_BIRDS = CollectionId("zenodo", "wetlandbirds")


def test_an_unmatched_budget_keeps_the_source_gain_descriptive() -> None:
    result = _evaluate(_OVERLAP, membership={STREAM: BoundStream((_BIRDS,), None)})
    by_source = result["by_source"]
    assert isinstance(by_source, dict)
    assert by_source["provenance"] == "complete"
    assert by_source["partitions_population"] is True
    collection = by_source["collections"][0]
    assert collection["status"] == "inconclusive"
    assert "review workloads differ" in collection["reasons"]
    assert collection["gain"]["estimate"] == pytest.approx(1)
    assert result["status"] == "inconclusive"


def test_unbound_membership_is_incomplete_and_leaves_the_combined_estimate() -> None:
    result = _evaluate(_MATCHED)
    by_source = result["by_source"]
    assert isinstance(by_source, dict)
    assert result["status"] == "estimated"
    assert by_source["provenance"] == "incomplete"
    assert by_source["collections"] == []
    assert by_source["reasons"] == []
    incomplete = by_source["incomplete"]
    assert incomplete["pool_windows"] == 2
    assert incomplete["sampled_windows"] == 2
    assert incomplete["reasons"] == [UNREAD]
    assert "recall" not in incomplete


def _counted() -> dict[str, object]:
    windows = (
        Window("a", sampled=True, diverse_selected=True, uniform_selected=True),
        Window("b"),
        Window("s", sibling=True),
    )
    observations = {(STREAM, "a"): "target_present"}
    diverse = _evidence("ssl-diverse", "diverse", windows, observations, frozenset({(STREAM, "a")}))
    uniform = _evidence("uniform", "uniform", windows, observations, frozenset({(STREAM, "a")}))
    return compare(diverse, uniform, {STREAM: BoundStream((_BIRDS,), None)}).to_record()


def _evidence(
    method: str,
    side: str,
    windows: tuple[Window, ...],
    observations: dict[tuple[str, str], str],
    withheld: frozenset[tuple[str, str]],
) -> Evidence:
    pool = [window for window in windows if not window.sibling]
    sampled = [window for window in pool if window.sampled]
    items = []
    for window in windows:
        selected = window.diverse_selected if side == "diverse" else window.uniform_selected
        item = _candidate(window, selected)
        if window.candidate_id == "b":
            item["selection"] = {"status": "excluded", "reason": "operator_excluded"}
        items.append(item)
    run = {
        "run_id": side,
        "corpus_id": "corpus",
        "frame_set_sha256": _HASH,
        "pool": {"window_frames": 8},
        "audit": {
            "design": "stratified_fixed_size",
            "revision": 1,
            "seed": 1,
            "strata": [
                {"stratum_id": "group", "eligible_count": len(pool), "sample_size": len(sampled)}
            ],
        },
        "selection": {
            "method": method,
            "budget": 1,
            "seed": None if method == "ssl-diverse" else 1,
            "score_ids": [],
        },
        "manifest_sha256": _HASH,
    }
    records = DiscoveryRecords(run, {STREAM: {"group_id": "group", "candidates": items}})
    return Evidence(
        records,
        observations,
        "reviewer",
        _HASH,
        frozenset(),
        withheld,
        reviewer_minutes=10,
    )


def _candidate(window: Window, selected: bool) -> dict[str, object]:
    if window.sibling:
        origin: dict[str, object] = {"source": "sibling_time", "hint_source_id": "hints", "slot": 1}
        audit: dict[str, object] = {"status": "ineligible", "reason": "no_inclusion_probability"}
    else:
        origin = {"source": "pool"}
        audit = {
            "status": "sampled" if window.sampled else "not_sampled",
            "stratum_id": "group",
            "inclusion_probability": 0.5,
        }
    return {
        "candidate_id": window.candidate_id,
        "window": {"start_frame": 0, "end_frame": 8},
        "origin": origin,
        "audit": audit,
        "selection": {"status": "selected" if selected else "not_selected", "probability": 1.0},
        "scores": [],
    }


def test_withheld_exclusion_and_sibling_costs_are_counted_per_source() -> None:
    result = _counted()
    by_source = result["by_source"]
    assert isinstance(by_source, dict)
    collection = by_source["collections"][0]
    assert collection["pool_windows"] == 2
    assert collection["withheld_windows"] == {"diverse": 1, "uniform": 1}
    assert collection["offered_windows"] == {"diverse": 1, "uniform": 1}
    assert collection["selected"] == {"diverse": 1, "uniform": 1}
    assert collection["sibling_offers"] == {"diverse": 1, "uniform": 1}
    assert collection["exclusions"] == {
        "diverse": {"operator_excluded": 1},
        "uniform": {"operator_excluded": 1},
    }
    assert collection["status"] == "inconclusive"
    assert "uncertainty unavailable" in collection["reasons"][0]
