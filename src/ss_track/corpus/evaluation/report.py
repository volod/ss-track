"""Summarize paired selection runs and their reviewed audit observations."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.corpus.evaluation.inputs import Evidence, match, read_evidence
from ss_track.corpus.evaluation.statistics import AuditWindow, Stratum, estimate
from ss_track.corpus.review.queue import CandidateKey


def claim(left: str | None, right: str | None) -> str:
    """Return one shared declaration, unrecorded when both omit it, or mixed when they differ.

    A value other than unrecorded is what the reviews stated. It is not a check that the
    procedure was followed.
    """
    if left is None and right is None:
        return "unrecorded"
    if left == right:
        return str(left)
    return "mixed"


def _selected(candidate: Mapping[str, Any]) -> bool:
    return bool(candidate["selection"]["status"] == "selected")


def _method(items: Mapping[CandidateKey, Mapping[str, Any]], evidence: Evidence) -> dict[str, Any]:
    picked = [key for key, item in items.items() if _selected(item)]
    excluded = Counter(
        item["selection"]["reason"]
        for item in items.values()
        if item["selection"]["status"] == "excluded"
    )
    groups = {str(evidence.records.inventories[key[0]]["group_id"]) for key in picked}
    return {
        "selected": len(picked),
        "streams": len({key[0] for key in picked}),
        "groups": len(groups),
        "exclusions": dict(sorted(excluded.items())),
        "reviewed_pool_windows": len(set(items) & evidence.observations.keys()),
        "offered_windows": len(evidence.offered),
        "withheld_windows": len(evidence.withheld),
        "audit_selected_overlap": sum(
            _selected(item) and item["audit"]["status"] == "sampled" for item in items.values()
        ),
        "compute_cost": None,
    }


def _audit(
    left: Mapping[CandidateKey, Mapping[str, Any]],
    right: Mapping[CandidateKey, Mapping[str, Any]],
    observations: Mapping[CandidateKey, str],
    run: Mapping[str, Any],
) -> list[Stratum]:
    samples: dict[str, list[AuditWindow]] = {
        item["stratum_id"]: [] for item in run["audit"]["strata"]
    }
    for key, item in left.items():
        audit = item["audit"]
        if audit["status"] == "sampled":
            samples[audit["stratum_id"]].append(
                AuditWindow(observations.get(key), _selected(item), _selected(right[key]))
            )
    return [
        Stratum(item["stratum_id"], item["eligible_count"], tuple(samples[item["stratum_id"]]))
        for item in run["audit"]["strata"]
    ]


def _observed(
    left: Mapping[CandidateKey, Mapping[str, Any]],
    right: Mapping[CandidateKey, Mapping[str, Any]],
    observations: Mapping[CandidateKey, str],
) -> list[JsonValue]:
    rows: list[JsonValue] = []
    motion_values = sorted(
        {
            float(score["value"])
            for item in left.values()
            for score in item["scores"]
            if score["score_id"] == "motion" and score["status"] == "computed"
        },
        reverse=True,
    )
    for key, observation in sorted(observations.items()):
        if key not in left:
            continue
        item = left[key]
        motion = next(
            (
                score.get("value")
                for score in item["scores"]
                if score["score_id"] == "motion" and score["status"] == "computed"
            ),
            None,
        )
        rows.append(
            {
                "stream_id": key[0],
                "candidate_id": key[1],
                "observation": observation,
                "audit_sampled": item["audit"]["status"] == "sampled",
                "diverse_selected": _selected(item),
                "uniform_selected": _selected(right[key]),
                "motion": motion,
                "motion_rank": motion_values.index(float(motion)) + 1
                if motion is not None
                else None,
            }
        )
    return rows


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """JSON result of a paired audit comparison."""

    report: dict[str, Any]

    def to_record(self) -> dict[str, Any]:
        """Return the result without claiming labels or field accuracy."""
        return self.report


def compare(first: Evidence, second: Evidence) -> EvaluationResult:
    """Compare two validated evidence sets without writing or inferring labels."""
    left, right, observations = match(first, second)
    run: Any = first.records.run
    metrics = estimate(_audit(left, right, observations, run))
    diverse, uniform = _method(left, first), _method(right, second)
    if diverse["selected"] != uniform["selected"]:
        metrics["status"] = "inconclusive"
        reasons: Any = metrics["reasons"]
        reasons.append("actual selected counts differ")
    streams: dict[str, list[CandidateKey]] = {}
    for key in left:
        streams.setdefault(key[0], []).append(key)
    whole = sorted(
        stream
        for stream, keys in streams.items()
        if all(observations.get(key) == "target_present" for key in keys)
    )
    observed_rows = _observed(left, right, observations)
    missed: dict[str, int] = {}
    for row in observed_rows:
        item: Any = row
        if item["audit_sampled"] and not item["diverse_selected"]:
            kind = str(item["observation"])
            missed[kind] = missed.get(kind, 0) + 1
    return EvaluationResult(
        {
            "status": metrics["status"],
            "corpus_id": run["corpus_id"],
            "frame_set_sha256": run["frame_set_sha256"],
            "budget": run["selection"]["budget"],
            "runs": {
                "diverse": {
                    "run_id": first.records.run_id,
                    "run_sha256": run[SEAL_FIELD],
                    "reviewer": first.reviewer,
                    "evidence_sha256": first.evidence_sha256,
                    **diverse,
                },
                "uniform": {
                    "run_id": second.records.run_id,
                    "run_sha256": second.records.run[SEAL_FIELD],
                    "reviewer": second.reviewer,
                    "evidence_sha256": second.evidence_sha256,
                    **uniform,
                },
            },
            "unique_reviewed_pool_windows": len(set(left) & observations.keys()),
            "unique_offered_windows": len(first.offered | second.offered),
            "review_blinding": claim(first.blinding, second.blinding),
            "review_independence": claim(first.independence, second.independence),
            "review_effort_minutes": [first.reviewer_minutes, second.reviewer_minutes],
            "whole_stream_target_observed": whole,
            "audit": metrics,
            "observations": observed_rows,
            "audit_misses_by_observation": missed,
            "limits": [
                "observations are not labels",
                "compute cost was not recorded by discovery",
                "recorded blinding is a declaration, and pictures may show the source",
            ],
        }
    )


def evaluate(
    data_root: Path,
    diverse_run: str,
    uniform_run: str,
    diverse_review: Path | None,
    uniform_review: Path | None,
    diverse_freeze: str | None,
    uniform_freeze: str | None,
) -> EvaluationResult:
    """Read the paired runs and each one's review or freeze, then compare them."""
    first = read_evidence(data_root, diverse_run, diverse_review, diverse_freeze)
    second = read_evidence(data_root, uniform_run, uniform_review, uniform_freeze)
    return compare(first, second)
