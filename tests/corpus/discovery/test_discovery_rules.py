"""Discovery rules refuse what only a comparison of two values can state.

Each finding names its `x-rules` key, the record and the JSON pointer, so a reviewer can always tell
why a window became a candidate and whether an audit estimate may rest on it.
"""

from typing import Any

import pytest

from tests.corpus.discovery._damage import (
    Damage,
    audit,
    extractor,
    findings,
    one,
    refused,
    rules,
    selection,
    set_to,
    sibling,
)
from tests.corpus.discovery._records import EXCLUDED, SIBLING_ID, Bodies, synthetic_bodies


def _window(stream_id: str, candidate_id: str, start: int, end: int) -> Damage:
    window = {"start_frame": start, "end_frame": end}
    return set_to(lambda b: b.candidate(stream_id, candidate_id), window=window)


def _remove_candidate(stream_id: str, candidate_id: str) -> Damage:
    def damage(bodies: Bodies) -> None:
        candidates = bodies.inventory(stream_id)["candidates"]
        candidates.remove(bodies.candidate(stream_id, candidate_id))

    return damage


def _repeat_candidate(bodies: Bodies) -> None:
    candidates = one(bodies)["candidates"]
    candidates.insert(1, dict(candidates[0]))


def _overlapping_pool(bodies: Bodies) -> None:
    extra = dict(bodies.candidate("one", "pool-002"), candidate_id="pool-003")
    one(bodies)["candidates"].insert(3, extra)


@pytest.mark.parametrize(
    ("damage", "rule"),
    [
        pytest.param(_window("one", "pool-000", 8, 8), "frames", id="empty-window"),
        pytest.param(_window("one", "pool-000", 9, 4), "frames", id="reversed-window"),
        pytest.param(_window("one", SIBLING_ID, 20, 30), "frames", id="outside-bundle"),
        pytest.param(_window("one", "pool-001", 9, 16), "pool", id="pool-off-the-tiling"),
        pytest.param(_remove_candidate("two", "pool-001"), "pool", id="pool-gap"),
        pytest.param(_overlapping_pool, "pool", id="pool-repeated"),
        pytest.param(_repeat_candidate, "order", id="repeated-candidate-id"),
        pytest.param(
            set_to(lambda b: sibling(b)["origin"], hint_source_id="ss-video-9"),
            "sibling",
            id="undeclared-hint-source",
        ),
        pytest.param(
            set_to(lambda b: b.candidate("one", "pool-000"), scores=[]), "order", id="no-scores"
        ),
        pytest.param(
            set_to(lambda b: b.inventory("two"), run_id="discovery-2"), "binding", id="other-run"
        ),
    ],
)
def test_a_window_must_name_frames_unambiguously(damage: Damage, rule: str) -> None:
    assert rule in rules(refused(damage))


def _unrank_first(bodies: Bodies) -> None:
    bodies.candidate("one", "pool-001")["selection"] = {"status": "not_selected", "probability": 0}


def _rank_excluded(bodies: Bodies) -> None:
    bodies.candidate(*EXCLUDED)["selection"] = {"status": "not_selected", "probability": 0.0}


@pytest.mark.parametrize(
    ("damage", "rule"),
    [
        pytest.param(selection("one", "pool-002", probability=0.5), "selection", id="random"),
        pytest.param(selection("two", "pool-000", rank=3), "selection", id="rank-gap"),
        pytest.param(_unrank_first, "selection", id="rank-one-missing"),
        pytest.param(set_to(lambda b: b.run["selection"], budget=1), "selection", id="over-budget"),
        pytest.param(_rank_excluded, "selection", id="ranked-without-its-scores"),
        pytest.param(audit("one", "pool-002", inclusion_probability=0.5), "audit", id="pi"),
        pytest.param(audit("one", "pool-002", status="sampled"), "audit", id="over-drawn"),
        pytest.param(audit("one", "pool-002", stratum_id="other"), "audit", id="no-stratum"),
        pytest.param(
            set_to(
                sibling,
                audit={
                    "status": "sampled",
                    "stratum_id": "group-one",
                    "inclusion_probability": 1 / 3,
                },
            ),
            "audit",
            id="sibling-in-audit",
        ),
        pytest.param(
            set_to(
                lambda b: b.candidate("one", "pool-002"),
                audit={"status": "ineligible", "reason": "no_inclusion_probability"},
            ),
            "audit",
            id="pool-window-hidden-from-audit",
        ),
        pytest.param(
            set_to(lambda b: b.run["audit"]["strata"][0], sample_size=9),
            "audit",
            id="stratum-larger-than-pool",
        ),
    ],
)
def test_selection_and_audit_state_probabilities_their_design_produces(
    damage: Damage, rule: str
) -> None:
    assert rule in rules(refused(damage))


def _unsorted_scores(bodies: Bodies) -> None:
    bodies.run["scores"].reverse()


@pytest.mark.parametrize(
    ("damage", "rule"),
    [
        pytest.param(
            set_to(lambda b: b.run["scores"][0], extractor_ids=["dino-b14"]),
            "references",
            id="undeclared-extractor",
        ),
        pytest.param(
            set_to(lambda b: b.run["selection"], score_ids=["motion", "size"]),
            "references",
            id="undeclared-score",
        ),
        pytest.param(_unsorted_scores, "order", id="unsorted-scores"),
        pytest.param(
            lambda b: extractor(b)["libraries"].reverse(), "order", id="unsorted-libraries"
        ),
    ],
)
def test_a_run_names_only_what_it_declares(damage: Damage, rule: str) -> None:
    assert rule in rules(refused(damage))


def test_one_stream_has_one_inventory() -> None:
    def damage(bodies: Bodies) -> None:
        bodies.inventories.append(dict(one(bodies)))

    refusal = refused(damage)

    assert findings(refusal) == [
        {
            "record": "inventories/one",
            "pointer": "/stream_id",
            "rule": "order",
            "message": "a stream has one inventory per run",
        }
    ]


def test_a_finding_names_its_record_pointer_and_rule() -> None:
    refusal = refused(selection("one", "pool-002", probability=0.5))

    assert findings(refusal) == [
        {
            "record": "inventories/one",
            "pointer": "/candidates/2/selection/probability",
            "rule": "selection",
            "message": "deterministic selection gives not_selected probability 0.0",
        }
    ]
    assert refusal.details["run_id"] == "discovery-1"


def test_an_excluded_window_and_a_randomized_selection_are_valid() -> None:
    bodies = synthetic_bodies()
    bodies.run["selection"]["seed"] = 11
    bodies.candidate("one", "pool-002")["selection"]["probability"] = 0.25
    bodies.candidate("one", "pool-001")["selection"]["probability"] = 0.75

    records = bodies.seal()

    excluded: Any = records.inventories["two"]["candidates"]
    excluded = excluded[2]
    assert excluded["selection"]["status"] == "excluded"
    assert excluded["audit"]["status"] == "sampled"
