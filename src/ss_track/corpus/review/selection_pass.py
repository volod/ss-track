"""A selection pass: one recorded review of every window one run selected.

A shared blinded audit reviews its sample once for both runs, so each run's further work is the
selected windows outside that sample. Equal selection counts then cost different work when the
audit overlaps the selections differently. A selection pass removes that dependence on the audit
draw: the reviewer reviews every selected window of the run again, including the ones the audit
already showed, so each run's pass has exactly its selected count of exposures. The pass never
changes selection or the audit draw, and its observations never replace the audit observation of
a window in the population estimate. They are reported as the run's review yield, with every
window that disagrees with the run's review.

A pass names only windows the run selected and offers. A selected window of a locked stream is
withheld and cannot be in a pass. A pass that leaves a selected window out is incomplete, which
the comparison reports as unmeasured work, never as a reviewed absence.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.corpus.discovery.run_rules import SELECTED
from ss_track.corpus.review.queue import OFFER_SELECTED, CandidateKey, ReviewQueue

PASS_FIELD = "selection_pass"


@dataclass(frozen=True, slots=True)
class SelectionPass:
    """Who reviewed a run's selected windows again, the minutes they recorded and what they saw."""

    reviewer: str
    observations: dict[CandidateKey, str]
    reviewer_minutes: int | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the pass as a freeze record carries it, windows ascending."""
        record: dict[str, JsonValue] = {"reviewer": self.reviewer}
        if self.reviewer_minutes is not None:
            record["reviewer_minutes"] = self.reviewer_minutes
        record["windows"] = [
            {"stream_id": key[0], "candidate_id": key[1], "observation": observation}
            for key, observation in sorted(self.observations.items())
        ]
        return record


def read_pass(fields: Fields) -> SelectionPass | None:
    """Read the optional pass of a review, refusing a window listed twice."""
    if not fields.has(PASS_FIELD):
        return None
    block = fields.child(PASS_FIELD)
    observations: dict[CandidateKey, str] = {}
    for position, raw in enumerate(block.items("windows")):
        entry = Fields(raw, f"{block.where}.windows[{position}]")
        key = (entry.text("stream_id"), entry.text("candidate_id"))
        if key in observations:
            raise invalid(f"{block.where} lists candidate {key[1]} of {key[0]} twice")
        observations[key] = entry.text("observation")
    minutes = block.index("reviewer_minutes") if block.has("reviewer_minutes") else None
    return SelectionPass(block.text("reviewer"), observations, minutes)


def pass_from_record(record: Mapping[str, Any] | None) -> SelectionPass | None:
    """Return the pass a freeze record carries, or None when the review had none."""
    if record is None:
        return None
    minutes = record.get("reviewer_minutes")
    return SelectionPass(
        str(record["reviewer"]),
        {
            (str(item["stream_id"]), str(item["candidate_id"])): str(item["observation"])
            for item in record["windows"]
        },
        minutes if type(minutes) is int else None,
    )


def expected_windows(queue: ReviewQueue) -> frozenset[CandidateKey]:
    """Return the selected windows a run offers: what a complete pass reviews."""
    return frozenset(key for key, item in queue.offered.items() if OFFER_SELECTED in item.offers)


def selected_offered(
    candidates: Iterable[tuple[CandidateKey, Mapping[str, Any]]],
    withheld: frozenset[CandidateKey],
) -> frozenset[CandidateKey]:
    """Return the selected windows outside the withheld ones, from raw inventory candidates."""
    return frozenset(
        key
        for key, item in candidates
        if item["selection"]["status"] == SELECTED and key not in withheld
    )


def _named(keys: Iterable[CandidateKey]) -> list[JsonValue]:
    return [{"stream_id": key[0], "candidate_id": key[1]} for key in sorted(keys)]


def require_pass_windows(
    selection_pass: SelectionPass | None,
    expected: frozenset[CandidateKey],
    withheld: frozenset[CandidateKey],
    run_id: str,
) -> None:
    """Refuse a pass that names a withheld window or one the run did not select and offer."""
    if selection_pass is None:
        return
    held = [key for key in selection_pass.observations if key in withheld]
    other = [
        key for key in selection_pass.observations if key not in expected and key not in withheld
    ]
    if held or other:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "the selection pass names windows its run did not select and offer",
            {
                "run_id": run_id,
                "locked_without_policy": _named(held),
                "not_selected": _named(other),
            },
        )
