"""Review workload of a paired selection comparison.

Equal selected counts are not equal review cost. The queue offers each window once, whether
selection, the audit draw, a sibling hint, or several of those name it. A per-run review pays
each queue. A shared blinded audit pays the audit windows both runs offer once, then each run's
other offers. A withheld window is counted apart and is not an offered window. Minutes a review
does not record stay unmeasured rather than zero.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.discovery.run_rules import SAMPLED, SELECTED
from ss_track.corpus.evaluation.inputs import Evidence
from ss_track.corpus.review.queue import OFFER_AUDIT, OFFER_SIBLING, CandidateKey, offers_of

PROTOCOL_PER_RUN = "per_run"
PROTOCOL_SHARED = "shared_audit"
PROTOCOL_UNRECORDED = "unrecorded"
BUDGET_MATCHED = "matched"
BUDGET_UNMATCHED = "unmatched"
BUDGET_UNMEASURED = "unmeasured"
EFFORT_EQUAL = "equal"
EFFORT_UNEQUAL = "unequal"
EFFORT_UNMEASURED = "unmeasured"
REASON_SELECTED = "actual selected counts differ"
REASON_WORKLOAD = "review workloads differ"
REASON_PROTOCOL = "review protocol is unrecorded"
REASON_MISSING = "withheld window is missing from the run"


@dataclass(frozen=True, slots=True)
class RunWorkload:
    """Hand-countable review counts of one run."""

    selected: int
    offered: frozenset[CandidateKey]
    sibling_offers: int
    audit_selected_overlap: int
    withheld: int
    missing_withheld: bool

    def counts(self) -> dict[str, int]:
        """Return the counts the comparison reports for this run."""
        return {
            "offered_windows": len(self.offered),
            "withheld_windows": self.withheld,
            "audit_selected_overlap": self.audit_selected_overlap,
            "sibling_offers": self.sibling_offers,
        }


@dataclass(frozen=True, slots=True)
class ReviewBudget:
    """The protocol, its comparable counts, and whether they match."""

    protocol: str
    status: str
    shared_audit_windows: int
    per_method_windows: dict[str, int]
    additions: dict[str, int]
    comparable_windows: dict[str, int]
    recorded_effort: str
    reasons: tuple[str, ...]
    unique_offered_windows: int
    diverse: RunWorkload
    uniform: RunWorkload

    def to_record(self) -> dict[str, Any]:
        """Return the budget a command result can carry."""
        return {
            "protocol": self.protocol,
            "status": self.status,
            "shared_audit_windows": self.shared_audit_windows,
            "per_method_windows": dict(self.per_method_windows),
            "additions": dict(self.additions),
            "comparable_windows": dict(self.comparable_windows),
            "recorded_effort": self.recorded_effort,
            "reasons": list(self.reasons),
        }


def _windows(records: DiscoveryRecords) -> dict[CandidateKey, Mapping[str, Any]]:
    """Return every candidate, including siblings the pool index leaves out."""
    found: dict[CandidateKey, Mapping[str, Any]] = {}
    for stream_id, inventory in records.inventories.items():
        entries: Any = inventory["candidates"]
        for item in entries:
            found[(stream_id, str(item["candidate_id"]))] = item
    return found


def _workload(
    windows: Mapping[CandidateKey, Mapping[str, Any]],
    pool: Mapping[CandidateKey, Mapping[str, Any]],
    withheld: frozenset[CandidateKey],
) -> RunWorkload:
    offered: set[CandidateKey] = set()
    siblings = 0
    for key, item in windows.items():
        offers = offers_of(item)
        if offers and key not in withheld:
            offered.add(key)
            if OFFER_SIBLING in offers:
                siblings += 1
    selected = 0
    overlap = 0
    for item in pool.values():
        if item["selection"]["status"] != SELECTED:
            continue
        selected += 1
        if item["audit"]["status"] == SAMPLED:
            overlap += 1
    missing = any(key not in windows for key in withheld)
    return RunWorkload(selected, frozenset(offered), siblings, overlap, len(withheld), missing)


def _protocol(left: str | None, right: str | None) -> str:
    if left is None and right is None:
        return PROTOCOL_PER_RUN
    if left is not None and left == right:
        return PROTOCOL_SHARED
    return PROTOCOL_UNRECORDED


def _effort(left: int | None, right: int | None) -> str:
    if left is None or right is None:
        return EFFORT_UNMEASURED
    if left == right:
        return EFFORT_EQUAL
    return EFFORT_UNEQUAL


def _audit_offered(
    workload: RunWorkload, windows: Mapping[CandidateKey, Mapping[str, Any]]
) -> set[CandidateKey]:
    return {key for key in workload.offered if OFFER_AUDIT in offers_of(windows[key])}


def _reasons(
    protocol: str,
    diverse: RunWorkload,
    uniform: RunWorkload,
    comparable: Mapping[str, int],
) -> tuple[str, ...]:
    found: list[str] = []
    if diverse.missing_withheld or uniform.missing_withheld:
        found.append(REASON_MISSING)
    if protocol == PROTOCOL_UNRECORDED:
        found.append(REASON_PROTOCOL)
    if found:
        return tuple(found)
    if diverse.selected != uniform.selected:
        found.append(REASON_SELECTED)
    if comparable["diverse"] != comparable["uniform"]:
        found.append(REASON_WORKLOAD)
    return tuple(found)


def _status(reasons: tuple[str, ...]) -> str:
    if REASON_MISSING in reasons or REASON_PROTOCOL in reasons:
        return BUDGET_UNMEASURED
    if reasons:
        return BUDGET_UNMATCHED
    return BUDGET_MATCHED


def apply_review_budget(metrics: dict[str, Any], budget: ReviewBudget) -> None:
    """Keep a computed gain descriptive when the review budget is not matched."""
    if budget.status == BUDGET_MATCHED:
        return
    metrics["status"] = "inconclusive"
    reasons: Any = metrics["reasons"]
    for reason in budget.reasons:
        if reason not in reasons:
            reasons.append(reason)


def review_budget(
    diverse: Evidence,
    uniform: Evidence,
    diverse_pool: Mapping[CandidateKey, Mapping[str, Any]],
    uniform_pool: Mapping[CandidateKey, Mapping[str, Any]],
) -> ReviewBudget:
    """Compare queue workload under the protocol the two reviews declare.

    Sibling windows stay out of the pool index, so population estimates never weight them.
    This count still sees them: a sibling offer is review work.
    """
    diverse_windows = _windows(diverse.records)
    uniform_windows = _windows(uniform.records)
    left = _workload(diverse_windows, diverse_pool, diverse.withheld)
    right = _workload(uniform_windows, uniform_pool, uniform.withheld)
    shared = _audit_offered(left, diverse_windows) & _audit_offered(right, uniform_windows)
    protocol = _protocol(diverse.audit_id, uniform.audit_id)
    per_method = {"diverse": len(left.offered), "uniform": len(right.offered)}
    additions = {
        "diverse": len(left.offered - shared),
        "uniform": len(right.offered - shared),
    }
    comparable = additions if protocol == PROTOCOL_SHARED else per_method
    reasons = _reasons(protocol, left, right, comparable)
    return ReviewBudget(
        protocol,
        _status(reasons),
        len(shared),
        per_method,
        additions,
        dict(comparable),
        _effort(diverse.reviewer_minutes, uniform.reviewer_minutes),
        reasons,
        len(left.offered | right.offered),
        left,
        right,
    )
