"""Weighted recall of one collection, using the stratum design weight."""

from collections.abc import Sequence
from typing import Any

from ss_track.corpus.evaluation.domains import (
    OBSERVATIONS,
    CollectionId,
    DomainStratum,
    SampledWindow,
    _population,
    _reviewed,
    _spans,
    _unknown,
)
from ss_track.corpus.evaluation.statistics import (
    NO_AUDIT_SAMPLE,
    NO_OBSERVED_TARGETS,
    NO_REVIEWED_SAMPLE,
    NO_VARIANCE,
    UNKNOWN_OBSERVATIONS,
    normal_interval,
    total_variance,
)


def collection_metrics(strata: Sequence[DomainStratum], collection: CollectionId) -> dict[str, Any]:
    """Return one collection's counts, weights and recall. Missing evidence stays null."""
    rows: list[dict[str, Any]] = []
    for stratum in strata:
        row = _row(stratum, collection)
        if row is not None:
            rows.append(row)
    reasons = _blocking(strata, collection)
    reviewed = _reviewed(strata, collection)
    if reviewed == 0:
        reasons.append(NO_REVIEWED_SAMPLE)
    measurable = bool(rows) and all(int(row["stratum_sample_size"]) > 0 for row in rows)
    result: dict[str, Any] = {
        "provider": collection.provider,
        "collection_id": collection.collection_id,
        "status": "inconclusive",
        "pool_windows": sum(int(row["population"]) for row in rows),
        "sampled_windows": sum(int(row["sample_size"]) for row in rows),
        "reviewed_windows": reviewed,
        "unknown_sampled": sum(int(row["observations"]["unknown"]) for row in rows),
        "strata": rows,
        "weighted_observations": None,
        "weighted_observations_complete": False,
        "weighted_selected_targets": None,
        "target_total": None,
        "reasons": reasons,
        "recall": None,
        "gain": None,
    }
    if reviewed == 0 or not measurable:
        return result
    totals, selected = _accumulate(strata, collection)
    result["weighted_observations"] = totals
    result["weighted_selected_targets"] = selected
    result["weighted_observations_complete"] = not reasons
    if reasons:
        return result
    denominator = totals["target_present"]
    if denominator == 0:
        reasons.append(NO_OBSERVED_TARGETS)
        result["target_total"] = {"estimate": 0.0, "variance": None, "interval_95": None}
        return result
    result["target_total"] = _target_total(strata, collection, denominator, result["pool_windows"])
    _ratios(result, strata, collection, selected, denominator)
    return result


def _row(stratum: DomainStratum, collection: CollectionId) -> dict[str, Any] | None:
    population = _population(stratum, collection)
    members = [item for item in stratum.sample if collection in item.collections]
    if population <= 0 and not members:
        return None
    counts = {name: 0 for name in OBSERVATIONS}
    for item in members:
        observation = item.observation if item.observation in counts else "unknown"
        counts[observation] += 1
    sample = len(stratum.sample)
    return {
        "stratum_id": stratum.name,
        "population": population,
        "sample_size": len(members),
        "design_weight": stratum.population / sample if sample else None,
        "stratum_population": stratum.population,
        "stratum_sample_size": sample,
        "spans_sources": _spans(stratum),
        "observations": counts,
    }


def _blocking(strata: Sequence[DomainStratum], collection: CollectionId) -> list[str]:
    reasons: list[str] = []
    for stratum in strata:
        if _population(stratum, collection) <= 0:
            continue
        if not stratum.sample:
            reasons.append(f"{stratum.name}: {NO_AUDIT_SAMPLE}")
        elif _unknown(stratum, collection):
            reasons.append(f"{stratum.name}: {UNKNOWN_OBSERVATIONS}")
    return reasons


def _accumulate(
    strata: Sequence[DomainStratum], collection: CollectionId
) -> tuple[dict[str, float], dict[str, float]]:
    totals = {name: 0.0 for name in OBSERVATIONS}
    selected = {"diverse": 0.0, "uniform": 0.0}
    for stratum in strata:
        _accumulate_stratum(stratum, collection, totals, selected)
    return totals, selected


def _accumulate_stratum(
    stratum: DomainStratum,
    collection: CollectionId,
    totals: dict[str, float],
    selected: dict[str, float],
) -> None:
    if _population(stratum, collection) <= 0 or not stratum.sample:
        return
    weight = stratum.population / len(stratum.sample)
    for item in stratum.sample:
        _add_window(item, collection, weight, totals, selected)


def _add_window(
    item: SampledWindow,
    collection: CollectionId,
    weight: float,
    totals: dict[str, float],
    selected: dict[str, float],
) -> None:
    if collection not in item.collections:
        return
    observation = item.observation if item.observation in totals else "unknown"
    totals[observation] += weight
    if observation != "target_present":
        return
    selected["diverse"] += weight * item.diverse
    selected["uniform"] += weight * item.uniform


def _frames(
    strata: Sequence[DomainStratum],
    collection: CollectionId,
    coefficients: tuple[float, float, float],
) -> list[tuple[int, list[float]]]:
    frames: list[tuple[int, list[float]]] = []
    for stratum in strata:
        if _population(stratum, collection) <= 0:
            continue
        values = [_residual(item, collection, coefficients) for item in stratum.sample]
        frames.append((stratum.population, values))
    return frames


def _residual(
    item: SampledWindow, collection: CollectionId, coefficients: tuple[float, float, float]
) -> float:
    target = float(collection in item.collections and item.observation == "target_present")
    return target * (
        coefficients[0] * item.diverse + coefficients[1] * item.uniform + coefficients[2]
    )


def _target_total(
    strata: Sequence[DomainStratum], collection: CollectionId, estimate: float, pool: int
) -> dict[str, Any]:
    variance = total_variance(_frames(strata, collection, (0.0, 0.0, 1.0)))
    return {
        "estimate": estimate,
        "variance": variance,
        "interval_95": normal_interval(estimate, variance, 1.0, 0.0, float(pool)),
    }


def _ratios(
    result: dict[str, Any],
    strata: Sequence[DomainStratum],
    collection: CollectionId,
    selected: dict[str, float],
    denominator: float,
) -> None:
    diverse = selected["diverse"] / denominator
    uniform = selected["uniform"] / denominator
    gain = diverse - uniform
    gain_variance = total_variance(_frames(strata, collection, (1.0, -1.0, -gain)))
    result["recall"] = {
        "diverse": _endpoint(strata, collection, (1.0, 0.0, -diverse), diverse, denominator, 0.0),
        "uniform": _endpoint(strata, collection, (0.0, 1.0, -uniform), uniform, denominator, 0.0),
    }
    result["gain"] = {
        "estimate": gain,
        "interval_95": normal_interval(gain, gain_variance, denominator, -1.0, 1.0),
    }
    reasons: list[str] = result["reasons"]
    if gain_variance is None:
        reasons.append(NO_VARIANCE)
    else:
        result["status"] = "estimated"


def _endpoint(
    strata: Sequence[DomainStratum],
    collection: CollectionId,
    coefficients: tuple[float, float, float],
    estimate: float,
    denominator: float,
    low: float,
) -> dict[str, Any]:
    variance = total_variance(_frames(strata, collection, coefficients))
    return {
        "estimate": estimate,
        "interval_95": normal_interval(estimate, variance, denominator, low, 1.0),
    }
