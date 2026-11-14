"""The common audit sample of matched discovery runs, in a stable private order.

A window is in the sample when every named run drew it and its stream is not locked. A window
selection left unranked stays in the sample. A sibling window has no inclusion probability, so it
stays out. Locked draws are withheld and named only on the private mapping. Item ids follow the
SHA-256 of the frame set, the audit seed, the stream and the candidate, so the same runs always
assign the same ids, and the order is neither frame order nor a selection rank.
"""

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.discovery.run_rules import NOT_SAMPLED, POOL, SAMPLED, SELECTED
from ss_track.corpus.review.queue import (
    LOCKED_WITHOUT_POLICY,
    OFFER_AUDIT,
    ReviewQueue,
    review_queue,
)

_DESIGN = ("corpus_id", "frame_set_sha256", "pool", "audit")
_MIN_DIGITS = 3


@dataclass(frozen=True, slots=True)
class AuditItem:
    """One presented window and the candidate the private mapping names."""

    item_id: str
    stream_id: str
    candidate_id: str
    start_frame: int
    end_frame: int

    def to_record(self) -> dict[str, JsonValue]:
        """Return the candidate identity, without its picture hash."""
        return {
            "item_id": self.item_id,
            "stream_id": self.stream_id,
            "candidate_id": self.candidate_id,
            "window": {"start_frame": self.start_frame, "end_frame": self.end_frame},
        }


@dataclass(frozen=True, slots=True)
class AuditSample:
    """The common sample, the runs it came from, and what review withholds or leaves out."""

    corpus_id: str
    frame_set_sha256: str
    runs: tuple[tuple[str, str], ...]  # run id and seal, ascending by run id
    items: tuple[AuditItem, ...]
    withheld: tuple[dict[str, JsonValue], ...]
    outside_sample: int
    unselected: int

    def withheld_count(self) -> int:
        """Return how many audit-sample windows were withheld."""
        total = 0
        for item in self.withheld:
            count = item["count"]
            if type(count) is not int:
                raise TypeError("a withheld count is not an integer")
            total += count
        return total


def _pool_facts(records: DiscoveryRecords) -> dict[tuple[str, str], tuple[object, ...]]:
    found: dict[tuple[str, str], tuple[object, ...]] = {}
    for stream_id, inventory in records.inventories.items():
        candidates: Any = inventory["candidates"]
        for candidate in candidates:
            if candidate["origin"]["source"] != POOL:
                continue
            key = (stream_id, str(candidate["candidate_id"]))
            found[key] = (candidate["window"], candidate["origin"], candidate["audit"])
    return found


def _require_matched(runs: Sequence[DiscoveryRecords]) -> None:
    """Refuse runs that do not share one pool, frame set and audit sample."""
    if not runs:
        raise invalid("name at least one discovery run")
    first = runs[0]
    facts = _pool_facts(first)
    for other in runs[1:]:
        if any(first.run[field] != other.run[field] for field in _DESIGN):
            raise invalid("runs differ in their pool, frame set or audit design")
        if facts != _pool_facts(other):
            raise invalid("runs differ in pool windows or audit sample")


def _rank(frame_set: str, seed: int, stream_id: str, candidate_id: str) -> str:
    material = "\0".join((frame_set, str(seed), stream_id, candidate_id))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _items(records: DiscoveryRecords, queue: ReviewQueue) -> tuple[AuditItem, ...]:
    offered = [item for item in queue.offered.values() if OFFER_AUDIT in item.offers]
    frame_set = str(records.run["frame_set_sha256"])
    audit = cast(Mapping[str, Any], records.run["audit"])
    seed = int(audit["seed"])
    offered.sort(key=lambda item: _rank(frame_set, seed, item.stream_id, item.candidate_id))
    digits = max(_MIN_DIGITS, len(str(max(len(offered) - 1, 0))))
    return tuple(
        AuditItem(
            f"item-{index:0{digits}d}",
            item.stream_id,
            item.candidate_id,
            item.start_frame,
            item.end_frame,
        )
        for index, item in enumerate(offered)
    )


def _withheld(records: DiscoveryRecords, queue: ReviewQueue) -> tuple[dict[str, JsonValue], ...]:
    counts: Counter[str] = Counter()
    for stream_id, inventory in records.inventories.items():
        candidates: Any = inventory["candidates"]
        for candidate in candidates:
            key = (stream_id, str(candidate["candidate_id"]))
            sampled = candidate["audit"]["status"] == SAMPLED and key in queue.withheld
            if sampled:
                counts[stream_id] += 1
    return tuple(
        {"stream_id": stream_id, "reason": LOCKED_WITHOUT_POLICY, "count": count}
        for stream_id, count in sorted(counts.items())
    )


def _outside(records: DiscoveryRecords) -> int:
    total = 0
    for inventory in records.inventories.values():
        candidates: Any = inventory["candidates"]
        for candidate in candidates:
            outside = candidate["origin"]["source"] == POOL
            outside = outside and candidate["audit"]["status"] == NOT_SAMPLED
            total += int(outside)
    return total


def _status(records: DiscoveryRecords, item: AuditItem) -> str:
    candidates: Any = records.inventories[item.stream_id]["candidates"]
    for candidate in candidates:
        if str(candidate["candidate_id"]) == item.candidate_id:
            return str(candidate["selection"]["status"])
    raise invalid(f"candidate {item.candidate_id} of {item.stream_id} is not in {records.run_id}")


def _unselected(items: Sequence[AuditItem], runs: Sequence[DiscoveryRecords]) -> int:
    return sum(any(_status(run, item) != SELECTED for run in runs) for item in items)


def common_sample(runs: Sequence[DiscoveryRecords], corpus: Mapping[str, Any]) -> AuditSample:
    """Return the audit sample the named runs share, after refusing a sample they do not share."""
    _require_matched(runs)
    ordered = tuple(sorted(runs, key=lambda item: item.run_id))
    first = ordered[0]
    queue = review_queue(first, corpus)
    items = _items(first, queue)
    return AuditSample(
        str(first.run["corpus_id"]),
        str(first.run["frame_set_sha256"]),
        tuple((item.run_id, str(item.run[SEAL_FIELD])) for item in ordered),
        items,
        _withheld(first, queue),
        _outside(first),
        _unselected(items, ordered),
    )
