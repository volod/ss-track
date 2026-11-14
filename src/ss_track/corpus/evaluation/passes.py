"""Account for the selection pass of each run in a paired comparison.

A pass is review work, and what it finds is review yield, so the comparison shows both. Its
observations never join the audit observations the population estimate weights: an audit
observation stays authoritative for its window, and a pass that disagrees with the run's review
is listed, not resolved. A pass that leaves a selected window out is incomplete, which leaves the
work unmeasured. Unknown is a reviewed window whose content the reviewer could not tell; it counts
as work and is never target absence.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.discovery.run_rules import SAMPLED
from ss_track.corpus.evaluation.inputs import Evidence
from ss_track.corpus.review.queue import CandidateKey
from ss_track.corpus.review.selection_pass import require_pass_windows, selected_offered

OBSERVATIONS = ("confuser", "target_absent", "target_present", "unknown")
TARGET_PRESENT = "target_present"
UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PassAccount:
    """Hand-countable work and yield of one run's selection pass."""

    reviewer: str
    reviewer_minutes: int | None
    expected: int
    reviewed: int
    audit_repeats: int
    observations: dict[str, int]
    targets_outside_audit: int

    @property
    def complete(self) -> bool:
        return self.reviewed == self.expected

    def to_record(self) -> dict[str, JsonValue]:
        """Return the account a command result carries; unrecorded minutes stay absent."""
        record: dict[str, JsonValue] = {"reviewer": self.reviewer}
        if self.reviewer_minutes is not None:
            record["reviewer_minutes"] = self.reviewer_minutes
        return record | {
            "expected_windows": self.expected,
            "reviewed_windows": self.reviewed,
            "missing_windows": self.expected - self.reviewed,
            "audit_repeats": self.audit_repeats,
            "observations": dict[str, JsonValue](self.observations),
            "targets_outside_audit": self.targets_outside_audit,
        }


def _sampled(item: Mapping[str, Any]) -> bool:
    return bool(item["audit"]["status"] == SAMPLED)


def pass_account(
    evidence: Evidence, windows: Mapping[CandidateKey, Mapping[str, Any]]
) -> PassAccount | None:
    """Count one run's pass against the selected windows it offers, or None without a pass."""
    selection_pass = evidence.selection_pass
    if selection_pass is None:
        return None
    expected = selected_offered(windows.items(), evidence.withheld)
    require_pass_windows(selection_pass, expected, evidence.withheld, str(evidence.records.run_id))
    seen = selection_pass.observations
    counts = {name: 0 for name in OBSERVATIONS}
    for observation in seen.values():
        counts[observation] += 1
    return PassAccount(
        selection_pass.reviewer,
        selection_pass.reviewer_minutes,
        len(expected),
        len(seen),
        sum(_sampled(windows[key]) for key in seen),
        counts,
        sum(
            observation == TARGET_PRESENT and not _sampled(windows[key])
            for key, observation in seen.items()
        ),
    )


def disagreements(
    side: str, evidence: Evidence, windows: Mapping[CandidateKey, Mapping[str, Any]]
) -> list[JsonValue]:
    """List each pass window whose observation differs from the run's review of it.

    An unknown on either side is not a disagreement: one reviewer could not tell.
    """
    if evidence.selection_pass is None:
        return []
    rows: list[JsonValue] = []
    for key, seen in sorted(evidence.selection_pass.observations.items()):
        reviewed = evidence.observations.get(key)
        if reviewed is None or reviewed == seen or UNKNOWN in (reviewed, seen):
            continue
        rows.append(
            {
                "run": side,
                "stream_id": key[0],
                "candidate_id": key[1],
                "audit_sampled": _sampled(windows[key]),
                "review_observation": reviewed,
                "pass_observation": seen,
            }
        )
    return rows


def pass_report(
    paired: bool,
    shared: int,
    accounts: tuple[PassAccount | None, PassAccount | None],
    disagreed: list[JsonValue],
) -> dict[str, JsonValue] | None:
    """Return the pass accounts and disagreements, or None when neither review recorded a pass.

    `review_exposures` is the shared audit plus both passes, the windows reviewers looked at in
    all; it is null unless both passes ran over one shared audit.
    """
    left, right = accounts
    if left is None and right is None:
        return None
    exposures = None
    if paired and left is not None and right is not None:
        exposures = shared + left.reviewed + right.reviewed
    return {
        "diverse": None if left is None else left.to_record(),
        "uniform": None if right is None else right.to_record(),
        "review_exposures": exposures,
        "disagreements": disagreed,
    }
