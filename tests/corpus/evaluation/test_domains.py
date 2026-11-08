"""Hand-calculated mixed-source estimates, shared-stratum covariance and missing evidence."""

import json
import math
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from typing import Any

import pytest

from ss_track.corpus.evaluation.domains import (
    CollectionId,
    DomainStratum,
    SampledWindow,
    estimate_domains,
)
from ss_track.corpus.evaluation.report import COMPARISON_LIMITS
from ss_track.corpus.evaluation.statistics import (
    NO_REVIEWED_SAMPLE,
    NO_VARIANCE,
    Z95,
    AuditWindow,
    Stratum,
    estimate,
)
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations

BIRDS = CollectionId("zenodo", "wetlandbirds")
DRONES = CollectionId("huggingface", "drones")
_COSTS = {
    "withheld_windows": {"diverse": 0, "uniform": 0},
    "offered_windows": {"diverse": 0, "uniform": 0},
    "selected": {"diverse": 0, "uniform": 0},
    "sibling_offers": {"diverse": 0, "uniform": 0},
    "exclusions": {"diverse": {}, "uniform": {}},
}


@lru_cache(maxsize=1)
def _command_schema() -> tuple[Mapping[str, Any], Any]:
    contracts = load_contract_set()
    contract = contracts.named("result/command")
    schema = contracts.frozen_schema(contract, contract.versions[-1])
    return schema, contracts.schema_registry()


def _accepts(report: dict[str, Any]) -> None:
    """The command stamps costs onto this report. The frozen schema must accept that shape."""
    stamped: dict[str, Any] = deepcopy(report)
    stamped["reasons"] = []
    incomplete = stamped["incomplete"]
    assert isinstance(incomplete, dict)
    incomplete.update(_COSTS)
    collections = stamped["collections"]
    assert isinstance(collections, list)
    for collection in collections:
        assert isinstance(collection, dict)
        collection.update(_COSTS)
    document = {"status": "estimated", "by_source": stamped, "limits": list(COMPARISON_LIMITS)}
    payload = json.loads(json.dumps(document, allow_nan=False))
    schema, registry = _command_schema()
    found = violations(payload, schema, registry)
    assert not found, found


def _window(
    observation: str | None, diverse: bool, uniform: bool, *collections: CollectionId
) -> SampledWindow:
    return SampledWindow(observation, diverse, uniform, collections)


def _collection(result: dict[str, object], provider: str, collection_id: str) -> dict[str, object]:
    rows = result["collections"]
    assert isinstance(rows, list)
    found = next(
        row for row in rows if row["provider"] == provider and row["collection_id"] == collection_id
    )
    assert isinstance(found, dict)
    return found


def _target(collection: dict[str, object]) -> float:
    total = collection["target_total"]
    assert isinstance(total, dict)
    estimate_value = total["estimate"]
    assert isinstance(estimate_value, float)
    return estimate_value


def _shared_result() -> dict[str, Any]:
    # N=8, n=4, weight=2. Birds has 5 windows and 1 draw; drones has 3 and 3 draws.
    # An independent weight would score the bird target as 5 and the drone target as 1.
    stratum = DomainStratum(
        "group",
        8,
        (
            _window("target_present", True, False, BIRDS),
            _window("target_present", False, True, DRONES),
            _window("target_absent", False, False, DRONES),
            _window("target_absent", False, False, DRONES),
        ),
        ((BIRDS, 5), (DRONES, 3)),
        0,
    )
    return estimate_domains((stratum,))


def test_shared_stratum_uses_design_weight_and_reports_covariance() -> None:
    result = _shared_result()
    assert result["partitions_population"] is True
    assert result["shared_strata"] == ["group"]
    birds = _collection(result, "zenodo", "wetlandbirds")
    drones = _collection(result, "huggingface", "drones")
    assert birds["status"] == "estimated"
    assert drones["status"] == "estimated"
    bird_stratum = birds["strata"]
    assert isinstance(bird_stratum, list)
    assert bird_stratum[0]["design_weight"] == 2
    assert bird_stratum[0]["population"] == 5
    assert bird_stratum[0]["sample_size"] == 1
    assert bird_stratum[0]["stratum_population"] == 8
    assert bird_stratum[0]["stratum_sample_size"] == 4
    assert _target(birds) == 2
    assert _target(drones) == 2
    _accepts(result)


def test_shared_stratum_covariance_matches_the_combined_total() -> None:
    result = _shared_result()
    birds = _collection(result, "zenodo", "wetlandbirds")
    drones = _collection(result, "huggingface", "drones")
    gain = birds["gain"]
    assert isinstance(gain, dict)
    assert gain["estimate"] == 1
    assert gain["interval_95"] == [1, 1]
    drone_gain = drones["gain"]
    assert isinstance(drone_gain, dict)
    assert drone_gain["estimate"] == -1
    assert drone_gain["interval_95"] == [-1, -1]
    covariance = result["covariance"]
    assert isinstance(covariance, list)
    assert covariance[0]["status"] == "estimated"
    assert covariance[0]["target_totals"] == pytest.approx(-2 / 3)
    assert covariance[0]["left"]["collection_id"] == "drones"
    bird_variance = birds["target_total"]
    drone_variance = drones["target_total"]
    assert isinstance(bird_variance, dict)
    assert isinstance(drone_variance, dict)
    assert bird_variance["variance"] == pytest.approx(2)
    assert drone_variance["variance"] == pytest.approx(2)
    # Var(birds) + Var(drones) + 2 Cov equals the combined target-total variance, 8/3.
    combined = (
        bird_variance["variance"] + drone_variance["variance"] + 2 * covariance[0]["target_totals"]
    )
    assert combined == pytest.approx(8 / 3)
    _accepts(result)


def test_unequal_stratum_weights_and_a_negative_gain() -> None:
    low = DomainStratum(
        "low",
        4,
        (
            _window("target_present", False, True, BIRDS),
            _window("target_absent", False, False, BIRDS),
        ),
        ((BIRDS, 4),),
        0,
    )
    high = DomainStratum(
        "high",
        6,
        (
            _window("target_present", True, False, DRONES),
            _window("target_present", False, True, DRONES),
        ),
        ((DRONES, 6),),
        0,
    )
    result = estimate_domains((low, high))
    assert result["shared_strata"] == []
    assert result["covariance"] == []
    birds = _collection(result, "zenodo", "wetlandbirds")
    drones = _collection(result, "huggingface", "drones")
    assert birds["strata"][0]["design_weight"] == 2
    assert drones["strata"][0]["design_weight"] == 3
    assert _target(birds) == 2
    assert _target(drones) == 6
    assert birds["gain"]["estimate"] == -1
    assert birds["gain"]["interval_95"] == [-1, -1]
    assert birds["status"] == "estimated"
    # Gain variance is 24, so the unclamped half-width is about 1.6 and the
    # reported interval is the clamp of that width to [-1, 1].
    assert Z95 * math.sqrt(24) / 6 > 1
    assert drones["recall"]["diverse"]["estimate"] == 0.5
    assert drones["recall"]["uniform"]["estimate"] == 0.5
    assert drones["gain"]["estimate"] == 0
    assert drones["gain"]["interval_95"] == [-1, 1]
    assert drones["status"] == "estimated"
    _accepts(result)


def test_a_source_with_no_reviewed_sample_is_not_zero() -> None:
    stratum = DomainStratum(
        "group",
        4,
        (
            _window("target_present", True, False, BIRDS),
            _window("target_absent", False, False, BIRDS),
        ),
        ((BIRDS, 2), (DRONES, 2)),
        0,
    )
    result = estimate_domains((stratum,))
    drones = _collection(result, "huggingface", "drones")
    assert drones["pool_windows"] == 2
    assert drones["sampled_windows"] == 0
    assert drones["status"] == "inconclusive"
    assert drones["weighted_observations"] is None
    assert drones["target_total"] is None
    assert drones["recall"] is None
    assert NO_REVIEWED_SAMPLE in drones["reasons"]
    assert _collection(result, "zenodo", "wetlandbirds")["status"] == "estimated"
    covariance = result["covariance"][0]
    assert covariance["status"] == "unavailable"
    assert covariance["target_totals"] is None
    assert covariance["target_totals"] != 0
    _accepts(result)


def test_incomplete_provenance_keeps_a_negative_source_the_combined_total_hides() -> None:
    stratum = DomainStratum(
        "group",
        2,
        (
            _window("target_present", False, True, BIRDS),
            _window("target_present", True, False),
        ),
        ((BIRDS, 1),),
        1,
    )
    result = estimate_domains((stratum,))
    assert result["provenance"] == "incomplete"
    assert result["partitions_population"] is False
    birds = _collection(result, "zenodo", "wetlandbirds")
    assert birds["status"] == "estimated"
    assert birds["gain"]["estimate"] == -1
    assert result["incomplete"]["pool_windows"] == 1
    assert result["incomplete"]["sampled_windows"] == 1
    combined = estimate(
        [
            Stratum(
                "group",
                2,
                (
                    AuditWindow("target_present", False, True),
                    AuditWindow("target_present", True, False),
                ),
            )
        ]
    )
    assert combined["gain"]["estimate"] == 0
    _accepts(result)


def test_unknown_exposure_is_not_target_absence() -> None:
    result = estimate_domains(
        (
            DomainStratum(
                "group",
                2,
                (
                    _window("target_present", True, False, BIRDS),
                    _window("unknown", False, False, BIRDS),
                ),
                ((BIRDS, 2),),
                0,
            ),
        )
    )
    birds = _collection(result, "zenodo", "wetlandbirds")
    weighted = birds["weighted_observations"]
    assert isinstance(weighted, dict)
    assert weighted["unknown"] == 1
    assert weighted["target_absent"] == 0
    assert birds["weighted_observations_complete"] is False
    assert birds["recall"] is None
    assert birds["target_total"] is None
    assert birds["status"] == "inconclusive"
    _accepts(result)


def test_a_stratum_without_a_sample_does_not_become_zero() -> None:
    result = estimate_domains(
        (
            DomainStratum(
                "seen",
                2,
                (
                    _window("target_present", True, False, BIRDS),
                    _window("target_absent", False, False, BIRDS),
                ),
                ((BIRDS, 2),),
                0,
            ),
            DomainStratum("open", 2, (), ((BIRDS, 2),), 0),
        )
    )
    birds = _collection(result, "zenodo", "wetlandbirds")
    assert birds["pool_windows"] == 4
    assert birds["weighted_observations"] is None
    assert birds["recall"] is None
    assert birds["target_total"] is None
    assert "open: no audit sample" in birds["reasons"]
    _accepts(result)


def test_a_small_stratum_does_not_remove_another_sources_interval() -> None:
    result = estimate_domains(
        (
            DomainStratum(
                "wide",
                2,
                (
                    _window("target_present", True, False, BIRDS),
                    _window("target_absent", False, True, BIRDS),
                ),
                ((BIRDS, 2),),
                0,
            ),
            DomainStratum(
                "thin",
                2,
                (_window("target_present", False, True, DRONES),),
                ((DRONES, 2),),
                0,
            ),
        )
    )
    birds = _collection(result, "zenodo", "wetlandbirds")
    drones = _collection(result, "huggingface", "drones")
    assert birds["status"] == "estimated"
    assert birds["gain"]["interval_95"] == [1, 1]
    assert drones["status"] == "inconclusive"
    assert drones["gain"]["interval_95"] is None
    assert NO_VARIANCE in drones["reasons"]
    _accepts(result)


def test_a_window_in_two_collections_is_not_a_partition() -> None:
    result = estimate_domains(
        (
            DomainStratum(
                "group",
                1,
                (_window("target_present", True, False, BIRDS, DRONES),),
                ((BIRDS, 1), (DRONES, 1)),
                0,
            ),
        )
    )
    assert result["partitions_population"] is False
    assert _target(_collection(result, "zenodo", "wetlandbirds")) == 1
    assert _target(_collection(result, "huggingface", "drones")) == 1
    assert result["covariance"][0]["target_totals"] == 0
    _accepts(result)
