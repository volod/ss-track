"""The candidate windows one discovery run offers a reviewer, and the ones review withholds.

Review is bounded by the run: it offers the windows selection ranked, the windows the audit sample
drew and the sibling windows, and nothing else, so its cost is the budget plus the audit sample and
an excluded or unselected window reaches a reviewer only through the independent audit sample. A
window of a stream in the locked split is never offered while no custodian policy allows it, even
though the audit sample draws from locked groups' strata; the queue names each such stream and how
many windows it withheld.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.discovery.inventory_rules import SIBLING_TIME
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.discovery.run_rules import SAMPLED, SELECTED

OFFER_SELECTED = "selected"
OFFER_AUDIT = "audit_sample"
OFFER_SIBLING = "sibling"
LOCKED_SPLIT = "locked"
LOCKED_WITHOUT_POLICY = "locked_without_policy"

type CandidateKey = tuple[str, str]  # stream and candidate id


@dataclass(frozen=True, slots=True)
class Offered:
    """One candidate window review offers, and why."""

    stream_id: str
    candidate_id: str
    start_frame: int
    end_frame: int
    offers: tuple[str, ...]
    candidate: Mapping[str, Any]

    @property
    def key(self) -> CandidateKey:
        return (self.stream_id, self.candidate_id)

    def to_record(self) -> dict[str, JsonValue]:
        """Return the candidate as the freeze record names it."""
        return {
            "stream_id": self.stream_id,
            "candidate_id": self.candidate_id,
            "window": {"start_frame": self.start_frame, "end_frame": self.end_frame},
            "offers": list(self.offers),
        }


@dataclass(frozen=True, slots=True)
class ReviewQueue:
    """What one run offers for review, keyed by stream and candidate, and what it withholds."""

    run_id: str
    offered: dict[CandidateKey, Offered]
    withheld: frozenset[CandidateKey]  # offered windows of locked streams
    not_offered: int  # pool windows neither selected nor sampled

    def withheld_records(self) -> list[dict[str, JsonValue]]:
        """Return each withheld stream with its reason, ascending by stream."""
        per_stream = Counter(stream_id for stream_id, _ in self.withheld)
        return [
            {"stream_id": stream_id, "reason": LOCKED_WITHOUT_POLICY, "count": count}
            for stream_id, count in sorted(per_stream.items())
        ]

    def counts(self) -> dict[str, JsonValue]:
        """Return how many windows review offers by reason, withholds and does not offer."""
        reasons = Counter(reason for item in self.offered.values() for reason in item.offers)
        return {
            "offered": len(self.offered),
            "offers": [{"offer": name, "count": reasons[name]} for name in sorted(reasons)],
            "withheld": list[JsonValue](self.withheld_records()),
            "not_offered": self.not_offered,
        }


def offers_of(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    """Return why review offers one candidate, ascending; empty when it does not."""
    found: list[str] = []
    if candidate["audit"]["status"] == SAMPLED:
        found.append(OFFER_AUDIT)
    if candidate["selection"]["status"] == SELECTED:
        found.append(OFFER_SELECTED)
    if candidate["origin"]["source"] == SIBLING_TIME:
        found.append(OFFER_SIBLING)
    return tuple(found)


def review_queue(records: DiscoveryRecords, corpus: Mapping[str, Any]) -> ReviewQueue:
    """Return what a run, bound to the corpus version it read, offers for review."""
    splits = {str(stream["stream_id"]): str(stream["split"]) for stream in corpus["streams"]}
    offered: dict[CandidateKey, Offered] = {}
    withheld: set[CandidateKey] = set()
    not_offered = 0
    for stream_id, inventory in sorted(records.inventories.items()):
        candidates: Any = inventory["candidates"]
        for candidate in candidates:
            offers = offers_of(candidate)
            if not offers:
                not_offered += 1
            elif splits[stream_id] == LOCKED_SPLIT:
                withheld.add((stream_id, str(candidate["candidate_id"])))
            else:
                window = candidate["window"]
                item = Offered(
                    stream_id,
                    str(candidate["candidate_id"]),
                    int(window["start_frame"]),
                    int(window["end_frame"]),
                    offers,
                    candidate,
                )
                offered[item.key] = item
    return ReviewQueue(records.run_id, offered, frozenset(withheld), not_offered)
