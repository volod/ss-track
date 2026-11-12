"""Bind discovery runs and reviewed observations to one comparison."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.discovery.selection_check import require_reproduced
from ss_track.corpus.review.decisions import read_review
from ss_track.corpus.review.freeze_record import read_freeze
from ss_track.corpus.review.queue import CandidateKey, ReviewQueue, review_queue
from ss_track.corpus.review.selection_pass import (
    SelectionPass,
    expected_windows,
    pass_from_record,
    require_pass_windows,
)
from ss_track.corpus.versions.manifests import load_corpus_manifest


@dataclass(frozen=True, slots=True)
class Evidence:
    """A verified run with observations from a review or a freeze.

    `audit_id` is present only when the review names the blinded audit it came from. Minutes are
    present only when the review recorded them. `selection_pass` is present only when the review
    recorded one; its observations are never part of `observations`.
    """

    records: DiscoveryRecords
    observations: dict[CandidateKey, str]
    reviewer: str
    evidence_sha256: str
    offered: frozenset[CandidateKey] = frozenset()
    withheld: frozenset[CandidateKey] = frozenset()
    independence: str | None = None
    blinding: str | None = None
    reviewer_minutes: int | None = None
    audit_id: str | None = None
    selection_pass: SelectionPass | None = None


def candidates(records: DiscoveryRecords) -> dict[CandidateKey, Mapping[str, Any]]:
    """Index pool candidates by stream and candidate identity."""
    found: dict[CandidateKey, Mapping[str, Any]] = {}
    for stream, inventory in records.inventories.items():
        entries: Any = inventory["candidates"]
        for item in entries:
            if item["origin"]["source"] == "pool":
                found[(stream, str(item["candidate_id"]))] = item
    return found


def read_evidence(
    data_root: Path, run_id: str, review_path: Path | None, freeze_id: str | None
) -> Evidence:
    """Validate one review or freeze against its verified run and bounded queue."""
    if (review_path is None) == (freeze_id is None):
        raise invalid("provide exactly one review or freeze for each run")
    records = verify_discovery(data_root, run_id)
    require_reproduced(records, data_root)
    pool = load_corpus_manifest(str(records.run["corpus_id"]), data_root)
    queue = review_queue(records, pool)
    observations: dict[CandidateKey, str] = {}
    if review_path is not None:
        review = read_review(review_path)
        if review.run_id != run_id or any(key not in queue.offered for key in review.decisions):
            raise invalid("review names a different run or a window not offered by the queue")
        observations = {
            key: decision.observation
            for key, decision in review.decisions.items()
            if decision.observation is not None
        }
        require_pass_windows(review.selection_pass, expected_windows(queue), queue.withheld, run_id)
        return Evidence(
            records,
            observations,
            review.reviewer,
            review.review_sha256,
            frozenset(queue.offered),
            queue.withheld,
            review.independence,
            review.blinding,
            review.reviewer_minutes,
            review.audit_id,
            review.selection_pass,
        )
    assert freeze_id is not None
    freeze = read_freeze(data_root, load_corpus_manifest(freeze_id, data_root))
    discovery: Any = freeze["discovery"]
    if discovery["run_id"] != run_id or discovery["run_sha256"] != records.run[SEAL_FIELD]:
        raise invalid("freeze does not identify this discovery run and its seal")
    observations = _freeze_observations(freeze, queue)
    review_info: Any = freeze["review"]
    selection_pass = pass_from_record(review_info.get("selection_pass"))
    require_pass_windows(selection_pass, expected_windows(queue), queue.withheld, run_id)
    return Evidence(
        records,
        observations,
        str(review_info["reviewer"]),
        str(freeze[SEAL_FIELD]),
        frozenset(queue.offered),
        queue.withheld,
        _text(review_info, "independence"),
        _text(review_info, "blinding"),
        _minutes(review_info),
        _text(review_info, "audit_id"),
        selection_pass,
    )


def _text(record: Mapping[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) else None


def _minutes(record: Mapping[str, Any]) -> int | None:
    value = record.get("reviewer_minutes")
    return value if type(value) is int else None


def _freeze_observations(freeze: Mapping[str, Any], queue: ReviewQueue) -> dict[CandidateKey, str]:
    observations: dict[CandidateKey, str] = {}
    entries: list[Any] = list(freeze["exclusions"])
    members: Any = freeze["members"]
    for member in members:
        entries.extend(member["candidates"])
    for item in entries:
        key = (str(item["stream_id"]), str(item["candidate_id"]))
        if key not in queue.offered:
            raise invalid("freeze names a window not offered by this run")
        offered = queue.offered[key]
        if item["window"] != offered.to_record()["window"]:
            raise invalid("freeze window differs from the discovery run")
        observations[key] = str(item["observation"])
    return observations


def match(
    first: Evidence, second: Evidence
) -> tuple[
    dict[CandidateKey, Mapping[str, Any]],
    dict[CandidateKey, Mapping[str, Any]],
    dict[CandidateKey, str],
]:
    """Refuse incomparable populations, audit draws, budgets or conflicting observations."""
    a: Any = first.records.run
    b: Any = second.records.run
    if a["selection"]["method"] != "ssl-diverse" or b["selection"]["method"] != "uniform":
        raise invalid("comparison requires ssl-diverse followed by uniform")
    if any(a[field] != b[field] for field in ("corpus_id", "frame_set_sha256", "pool", "audit")):
        raise invalid("runs differ in their pool, frame set or audit design")
    if a["selection"]["budget"] != b["selection"]["budget"]:
        raise invalid("runs have different selection budgets")
    left, right = candidates(first.records), candidates(second.records)
    if left.keys() != right.keys() or any(
        left[key][field] != right[key][field]
        for key in left
        for field in ("window", "origin", "audit")
    ):
        raise invalid("runs differ in pool windows or audit sample")
    observations = dict(first.observations)
    for key, value in second.observations.items():
        if (
            key in observations
            and observations[key] != value
            and "unknown" not in (value, observations[key])
        ):
            raise invalid(f"conflicting observations for {key[0]} / {key[1]}")
        if key not in observations or observations[key] == "unknown":
            observations[key] = value
    return left, right, observations
