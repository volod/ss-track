"""Covariance of collection target totals that share an audit stratum."""

from collections.abc import Sequence
from typing import Any

from ss_track.corpus.evaluation.domains import (
    CollectionId,
    DomainStratum,
    _population,
    _reviewed,
    _unknown,
)
from ss_track.corpus.evaluation.statistics import (
    NO_AUDIT_SAMPLE,
    NO_REVIEWED_SAMPLE,
    NO_VARIANCE,
    UNKNOWN_OBSERVATIONS,
    pair_covariance,
)


def source_covariance(
    strata: Sequence[DomainStratum], collections: Sequence[CollectionId]
) -> list[dict[str, Any]]:
    """Return each pair that shares a stratum. A missing sample stays null, not zero."""
    rows: list[dict[str, Any]] = []
    for index, left in enumerate(collections):
        for right in collections[index + 1 :]:
            if _shares(strata, left, right):
                rows.append(_pair(strata, left, right))
    return rows


def _shares(strata: Sequence[DomainStratum], left: CollectionId, right: CollectionId) -> bool:
    return any(
        _population(stratum, left) > 0 and _population(stratum, right) > 0 for stratum in strata
    )


def _pair(
    strata: Sequence[DomainStratum], left: CollectionId, right: CollectionId
) -> dict[str, Any]:
    reasons = _pair_reasons(strata, left, right)
    frames = [] if reasons else _pair_frames(strata, left, right)
    value = None if reasons else pair_covariance(frames)
    if not reasons and value is None:
        reasons.append(NO_VARIANCE)
    return {
        "left": left.to_record(),
        "right": right.to_record(),
        "status": "unavailable" if reasons else "estimated",
        "target_totals": value,
        "reasons": reasons,
    }


def _pair_reasons(
    strata: Sequence[DomainStratum], left: CollectionId, right: CollectionId
) -> list[str]:
    reasons: list[str] = []
    if _reviewed(strata, left) == 0 or _reviewed(strata, right) == 0:
        reasons.append(NO_REVIEWED_SAMPLE)
    for stratum in strata:
        if _population(stratum, left) <= 0 or _population(stratum, right) <= 0:
            continue
        if not stratum.sample:
            reasons.append(f"{stratum.name}: {NO_AUDIT_SAMPLE}")
        elif _unknown(stratum, left) or _unknown(stratum, right):
            reasons.append(f"{stratum.name}: {UNKNOWN_OBSERVATIONS}")
    return reasons


def _pair_frames(
    strata: Sequence[DomainStratum], left: CollectionId, right: CollectionId
) -> list[tuple[int, list[float], list[float]]]:
    frames: list[tuple[int, list[float], list[float]]] = []
    for stratum in strata:
        if _population(stratum, left) <= 0 or _population(stratum, right) <= 0:
            continue
        frames.append((stratum.population, _indicator(stratum, left), _indicator(stratum, right)))
    return frames


def _indicator(stratum: DomainStratum, collection: CollectionId) -> list[float]:
    return [
        float(collection in item.collections and item.observation == "target_present")
        for item in stratum.sample
    ]
