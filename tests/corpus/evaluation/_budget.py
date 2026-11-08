"""Build paired selection fixtures with hand-counted review queues."""

from dataclasses import dataclass
from typing import Any

from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.evaluation.inputs import Evidence
from ss_track.corpus.evaluation.report import compare

STREAM = "stream"
_HASH = "a" * 64


@dataclass(frozen=True, slots=True)
class Window:
    """One candidate and the two selection decisions."""

    candidate_id: str
    sampled: bool = False
    sibling: bool = False
    diverse_selected: bool = False
    uniform_selected: bool = False
    observation: str | None = None
    on: tuple[str, ...] = ("diverse", "uniform")
    slot: int = 1


def _item(window: Window, selected: bool) -> dict[str, Any]:
    if window.sibling:
        origin: dict[str, Any] = {
            "source": "sibling_time",
            "hint_source_id": "hints",
            "slot": window.slot,
        }
        audit: dict[str, Any] = {"status": "ineligible", "reason": "no_inclusion_probability"}
    else:
        origin = {"source": "pool"}
        audit = {
            "status": "sampled" if window.sampled else "not_sampled",
            "stratum_id": "group",
            "inclusion_probability": 0.5,
        }
    return {
        "candidate_id": window.candidate_id,
        "window": {"start_frame": 0, "end_frame": 8},
        "origin": origin,
        "audit": audit,
        "selection": {
            "status": "selected" if selected else "not_selected",
            "probability": 1.0 if selected else 0.0,
        },
        "scores": [],
    }


def _records(method: str, side: str, windows: tuple[Window, ...]) -> DiscoveryRecords:
    pool = [window for window in windows if not window.sibling]
    sampled = [window for window in pool if window.sampled]
    items = [
        _item(window, window.diverse_selected if side == "diverse" else window.uniform_selected)
        for window in windows
        if side in window.on
    ]
    run = {
        "run_id": side,
        "corpus_id": "corpus",
        "frame_set_sha256": _HASH,
        "pool": {"window_frames": 8},
        "audit": {
            "design": "stratified_fixed_size",
            "revision": 1,
            "seed": 1,
            "strata": [
                {
                    "stratum_id": "group",
                    "eligible_count": len(pool),
                    "sample_size": len(sampled),
                }
            ],
        },
        "selection": {
            "method": method,
            "budget": 4,
            "seed": None if method == "ssl-diverse" else 1,
            "score_ids": [],
        },
        "manifest_sha256": _HASH,
    }
    return DiscoveryRecords(run, {STREAM: {"group_id": "group", "candidates": items}})


def _evaluate(
    windows: tuple[Window, ...],
    *,
    diverse_withheld: frozenset[tuple[str, str]] = frozenset(),
    uniform_withheld: frozenset[tuple[str, str]] = frozenset(),
    diverse_audit: str | None = None,
    uniform_audit: str | None = None,
    diverse_minutes: int | None = 10,
    uniform_minutes: int | None = 10,
) -> dict[str, Any]:
    observations = {
        (STREAM, window.candidate_id): window.observation
        for window in windows
        if window.observation is not None
    }
    diverse = Evidence(
        _records("ssl-diverse", "diverse", windows),
        observations,
        "reviewer",
        _HASH,
        frozenset(),
        diverse_withheld,
        reviewer_minutes=diverse_minutes,
        audit_id=diverse_audit,
    )
    uniform = Evidence(
        _records("uniform", "uniform", windows),
        observations,
        "reviewer",
        _HASH,
        frozenset(),
        uniform_withheld,
        reviewer_minutes=uniform_minutes,
        audit_id=uniform_audit,
    )
    return compare(diverse, uniform).to_record()


def _budget(result: dict[str, Any]) -> dict[str, Any]:
    budget = result["review_budget"]
    assert isinstance(budget, dict)
    return budget


def _run(result: dict[str, Any], side: str) -> dict[str, Any]:
    runs = result["runs"]
    assert isinstance(runs, dict)
    run = runs[side]
    assert isinstance(run, dict)
    return run


def _gain(result: dict[str, Any]) -> float:
    audit = result["audit"]
    assert isinstance(audit, dict)
    gain = audit["gain"]
    assert isinstance(gain, dict)
    estimate = gain["estimate"]
    assert isinstance(estimate, float)
    return estimate
