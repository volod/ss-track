"""Attach review costs to design-weighted per-collection estimates."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ss_track.corpus.discovery.run_rules import POOL, SAMPLED, SELECTED
from ss_track.corpus.evaluation.domains import (
    WEIGHTING,
    CollectionId,
    DomainStratum,
    SampledWindow,
    estimate_domains,
)
from ss_track.corpus.evaluation.inputs import Evidence
from ss_track.corpus.evaluation.membership import UNREAD, BoundStream
from ss_track.corpus.evaluation.workload import ReviewBudget, apply_review_budget
from ss_track.corpus.review.queue import OFFER_SIBLING, CandidateKey, offers_of

_EXCLUDED = "excluded"
_MISMATCH = "stratum population does not match its sealed sample frame"


@dataclass(slots=True)
class _Cost:
    selected: int = 0
    offered: int = 0
    sibling_offers: int = 0
    withheld: int = 0
    exclusions: Counter[str] = field(default_factory=Counter)


def source_report(
    left: Mapping[CandidateKey, Mapping[str, Any]],
    right: Mapping[CandidateKey, Mapping[str, Any]],
    observations: Mapping[CandidateKey, str],
    run: Mapping[str, Any],
    diverse: Evidence,
    uniform: Evidence,
    membership: Mapping[str, BoundStream] | None,
    budget: ReviewBudget,
) -> dict[str, Any]:
    """Report each collection beside the combined population, with review costs.

    ``membership`` None leaves every stream unbound. An unbound window is not
    given a collection, and its totals are not zeros.
    """
    bound = _bound(left, diverse, uniform, membership)
    strata, mismatch, incomplete_streams = _strata(left, right, observations, run, bound)
    diverse_costs, diverse_gap, diverse_streams = _costs(diverse, bound)
    uniform_costs, uniform_gap, uniform_streams = _costs(uniform, bound)
    reasons = _incomplete_reasons(bound, incomplete_streams | diverse_streams | uniform_streams)
    report = _unestimated(strata, reasons) if mismatch else estimate_domains(strata)
    report["reasons"] = [_MISMATCH] if mismatch else []
    if not mismatch:
        report["incomplete"]["reasons"] = reasons
    _attach(report, diverse_costs, uniform_costs, diverse_gap, uniform_gap)
    for collection in report["collections"]:
        apply_review_budget(collection, budget)
    return report


def _bound(
    left: Mapping[CandidateKey, Mapping[str, Any]],
    diverse: Evidence,
    uniform: Evidence,
    membership: Mapping[str, BoundStream] | None,
) -> dict[str, BoundStream]:
    streams = {key[0] for key in left}
    streams.update(diverse.records.inventories)
    streams.update(uniform.records.inventories)
    if membership is None:
        return {stream: BoundStream((), UNREAD) for stream in streams}
    return {stream: membership.get(stream, BoundStream((), UNREAD)) for stream in streams}


def _strata(
    left: Mapping[CandidateKey, Mapping[str, Any]],
    right: Mapping[CandidateKey, Mapping[str, Any]],
    observations: Mapping[CandidateKey, str],
    run: Mapping[str, Any],
    bound: Mapping[str, BoundStream],
) -> tuple[list[DomainStratum], bool, set[str]]:
    grouped: dict[str, list[tuple[CandidateKey, Mapping[str, Any]]]] = {}
    for key, item in left.items():
        grouped.setdefault(str(item["audit"]["stratum_id"]), []).append((key, item))
    sealed: Any = run["audit"]["strata"]
    names = {str(item["stratum_id"]) for item in sealed}
    mismatch = set(grouped) != names
    incomplete: set[str] = set()
    strata: list[DomainStratum] = []
    for item in sealed:
        name = str(item["stratum_id"])
        windows = grouped.get(name, [])
        population = int(item["eligible_count"])
        if len(windows) != population:
            mismatch = True
        strata.append(_stratum(name, population, windows, right, observations, bound, incomplete))
    return strata, mismatch, incomplete


def _stratum(
    name: str,
    population: int,
    windows: list[tuple[CandidateKey, Mapping[str, Any]]],
    right: Mapping[CandidateKey, Mapping[str, Any]],
    observations: Mapping[CandidateKey, str],
    bound: Mapping[str, BoundStream],
    incomplete: set[str],
) -> DomainStratum:
    counts: dict[CollectionId, int] = {}
    missing = 0
    sample: list[SampledWindow] = []
    for key, item in windows:
        collections = _collections(key[0], bound, incomplete)
        if collections:
            for collection in collections:
                counts[collection] = counts.get(collection, 0) + 1
        else:
            missing += 1
        if item["audit"]["status"] == SAMPLED:
            sample.append(
                SampledWindow(
                    observations.get(key),
                    item["selection"]["status"] == SELECTED,
                    right[key]["selection"]["status"] == SELECTED,
                    collections,
                )
            )
    listed = tuple(
        sorted(counts.items(), key=lambda item: (item[0].provider, item[0].collection_id))
    )
    return DomainStratum(name, population, tuple(sample), listed, missing)


def _collections(
    stream: str, bound: Mapping[str, BoundStream], incomplete: set[str]
) -> tuple[CollectionId, ...]:
    found = bound.get(stream, BoundStream((), UNREAD))
    if found.reason is not None or not found.collections:
        incomplete.add(stream)
        return ()
    return found.collections


def _costs(
    evidence: Evidence, bound: Mapping[str, BoundStream]
) -> tuple[dict[CollectionId, _Cost], _Cost, set[str]]:
    per: dict[CollectionId, _Cost] = {}
    gap = _Cost()
    incomplete: set[str] = set()
    for stream_id, inventory in evidence.records.inventories.items():
        collections = _collections(str(stream_id), bound, incomplete)
        entries: Any = inventory["candidates"]
        for item in entries:
            key = (str(stream_id), str(item["candidate_id"]))
            buckets = _buckets(per, gap, collections)
            _add(buckets, item, key, evidence.withheld)
    return per, gap, incomplete


def _buckets(
    per: dict[CollectionId, _Cost], gap: _Cost, collections: tuple[CollectionId, ...]
) -> list[_Cost]:
    if not collections:
        return [gap]
    found: list[_Cost] = []
    for collection in collections:
        bucket = per.get(collection)
        if bucket is None:
            bucket = _Cost()
            per[collection] = bucket
        found.append(bucket)
    return found


def _add(
    buckets: list[_Cost],
    item: Mapping[str, Any],
    key: CandidateKey,
    withheld: frozenset[CandidateKey],
) -> None:
    offers = offers_of(item)
    offered = bool(offers) and key not in withheld
    selected = item["origin"]["source"] == POOL and item["selection"]["status"] == SELECTED
    reason = item["selection"].get("reason") if item["selection"]["status"] == _EXCLUDED else None
    for bucket in buckets:
        if key in withheld:
            bucket.withheld += 1
        elif offered:
            bucket.offered += 1
            if OFFER_SIBLING in offers:
                bucket.sibling_offers += 1
        if selected:
            bucket.selected += 1
        if isinstance(reason, str) and reason:
            bucket.exclusions[reason] += 1


def _incomplete_reasons(bound: Mapping[str, BoundStream], streams: set[str]) -> list[str]:
    return sorted(
        {
            found.reason
            for stream, found in bound.items()
            if stream in streams and found.reason is not None
        }
    )


def _unestimated(strata: Sequence[DomainStratum], reasons: list[str]) -> dict[str, Any]:
    """Withhold estimates when the sealed frame and the pool windows disagree."""
    return {
        "weighting": WEIGHTING,
        "provenance": "incomplete"
        if any(stratum.incomplete_population for stratum in strata)
        else "complete",
        "partitions_population": False,
        "incomplete": {
            "pool_windows": sum(stratum.incomplete_population for stratum in strata),
            "sampled_windows": 0,
            "reviewed_windows": 0,
            "unknown_sampled": 0,
            "reasons": reasons,
        },
        "shared_strata": [],
        "covariance": [],
        "collections": [],
    }


def _attach(
    report: dict[str, Any],
    diverse: Mapping[CollectionId, _Cost],
    uniform: Mapping[CollectionId, _Cost],
    diverse_gap: _Cost,
    uniform_gap: _Cost,
) -> None:
    report["incomplete"].update(_fields(diverse_gap, uniform_gap))
    for collection in report["collections"]:
        key = CollectionId(str(collection["provider"]), str(collection["collection_id"]))
        collection.update(_fields(diverse.get(key, _Cost()), uniform.get(key, _Cost())))


def _fields(left: _Cost, right: _Cost) -> dict[str, Any]:
    return {
        "withheld_windows": {"diverse": left.withheld, "uniform": right.withheld},
        "offered_windows": {"diverse": left.offered, "uniform": right.offered},
        "selected": {"diverse": left.selected, "uniform": right.selected},
        "sibling_offers": {
            "diverse": left.sibling_offers,
            "uniform": right.sibling_offers,
        },
        "exclusions": {
            "diverse": _exclusions(left.exclusions),
            "uniform": _exclusions(right.exclusions),
        },
    }


def _exclusions(counts: Counter[str]) -> dict[str, int]:
    return {reason: count for reason, count in sorted(counts.items()) if count > 0}
