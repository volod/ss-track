"""The rules of one stream's candidate inventory, checked against the run that wrote it.

Every window names ss-track frames of its bundle. Pool windows tile the bundle, so the eligible pool
and its unprocessed exposure are known; a sibling window names a declared hint source, so its ffmpeg
version and sampling rate are known. Each candidate carries every score of the run, a selection
probability its method can produce, and the audit status its origin allows.
"""

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from ss_track.corpus.discovery.findings import Finding, inventory_label
from ss_track.corpus.discovery.run_rules import (
    NOT_SAMPLED,
    POOL,
    SAMPLED,
    SELECTED,
    ids,
    ordered,
)

SIBLING_TIME = "sibling_time"
NOT_SELECTED = "not_selected"
COMPUTED = "computed"
_RANKED = (SELECTED, NOT_SELECTED)
_AUDITED = (SAMPLED, NOT_SAMPLED)
# Relative: a writer in another language may round the last bit of n / N differently.
PROBABILITY_TOLERANCE = 1e-12
_DETERMINISTIC = {SELECTED: 1.0, NOT_SELECTED: 0.0}


@dataclass(frozen=True, slots=True)
class _Run:
    """What every candidate is checked against, looked up once per inventory."""

    hint_sources: frozenset[str]
    score_ids: list[str]
    selection_scores: frozenset[str]
    deterministic: bool
    strata: dict[str, Mapping[str, Any]]

    @classmethod
    def of(cls, run: Mapping[str, Any]) -> "_Run":
        return cls(
            hint_sources=frozenset(ids(run["hint_sources"], "hint_source_id")),
            score_ids=ids(run["scores"], "score_id"),
            selection_scores=frozenset(run["selection"]["score_ids"]),
            deterministic=run["selection"]["seed"] is None,
            strata={stratum["stratum_id"]: stratum for stratum in run["audit"]["strata"]},
        )


def inventory_findings(inventory: Mapping[str, Any], run: Mapping[str, Any]) -> list[Finding]:
    """Check one inventory's candidates and its binding to the run."""
    label = inventory_label(inventory["stream_id"])
    candidates = inventory["candidates"]
    found = [*_binding(inventory, run, label)]
    found += ordered(ids(candidates, "candidate_id"), label, "/candidates", "candidate_id")
    found += _windows(inventory, label)
    found += _pool(inventory, run["pool"]["window_frames"], label)
    facts = _Run.of(run)
    for index, candidate in enumerate(candidates):
        found += _candidate(candidate, facts, label, f"/candidates/{index}")
    return found


def _binding(inventory: Mapping[str, Any], run: Mapping[str, Any], label: str) -> Iterator[Finding]:
    for key in ("run_id", "corpus_id"):
        if inventory[key] != run[key]:
            yield Finding(label, f"/{key}", "binding", f"{key} differs from the run's")


def _windows(inventory: Mapping[str, Any], label: str) -> Iterator[Finding]:
    bundle = inventory["bundle_frames"]
    if bundle["start_frame"] >= bundle["end_frame"]:
        yield Finding(label, "/bundle_frames", "frames", "the bundle window is empty")
    for index, candidate in enumerate(inventory["candidates"]):
        window = candidate["window"]
        pointer = f"/candidates/{index}/window"
        if window["start_frame"] >= window["end_frame"]:
            yield Finding(label, pointer, "frames", "a window names no frame")
        elif window["start_frame"] < bundle["start_frame"] or (
            window["end_frame"] > bundle["end_frame"]
        ):
            yield Finding(label, pointer, "frames", "the window names frames outside the bundle")


def pool_windows(bundle: Mapping[str, int], window_frames: int) -> list[tuple[int, int]]:
    """Return the windows that tile a bundle at the run's length, the last possibly shorter."""
    start, end = bundle["start_frame"], bundle["end_frame"]
    return [(first, min(first + window_frames, end)) for first in range(start, end, window_frames)]


def _pool(inventory: Mapping[str, Any], window_frames: int, label: str) -> Iterator[Finding]:
    found = sorted(
        (candidate["window"]["start_frame"], candidate["window"]["end_frame"])
        for candidate in inventory["candidates"]
        if candidate["origin"]["source"] == POOL
    )
    expected = pool_windows(inventory["bundle_frames"], window_frames)
    if found != expected:
        missing = sorted(set(expected) - set(found))
        stray = sorted(set(found) - set(expected))
        message = (
            f"pool windows must tile the bundle at {window_frames} frames: "
            f"{len(missing)} missing, {len(stray)} not on the tiling, "
            f"{len(found) - len(set(found))} repeated"
        )
        yield Finding(label, "/candidates", "pool", message)


def _candidate(
    candidate: Mapping[str, Any], run: _Run, label: str, pointer: str
) -> Iterator[Finding]:
    yield from _origin(candidate["origin"], run, label, f"{pointer}/origin")
    yield from _scores(candidate, run, label, pointer)
    yield from _selection(candidate, run, label, pointer)
    yield from _audit(candidate, run, label, pointer)


def _origin(origin: Mapping[str, Any], run: _Run, label: str, pointer: str) -> Iterator[Finding]:
    if origin["source"] == SIBLING_TIME and origin["hint_source_id"] not in run.hint_sources:
        message = "a sibling window must name a hint source of the run, with its ffmpeg and rate"
        yield Finding(label, f"{pointer}/hint_source_id", "sibling", message)


def _scores(candidate: Mapping[str, Any], run: _Run, label: str, pointer: str) -> Iterator[Finding]:
    if ids(candidate["scores"], "score_id") != run.score_ids:
        message = f"scores must name every score of the run once, in order: {run.score_ids}"
        yield Finding(label, f"{pointer}/scores", "order", message)


def _selection(
    candidate: Mapping[str, Any], run: _Run, label: str, pointer: str
) -> Iterator[Finding]:
    selection = candidate["selection"]
    status = selection["status"]
    if status not in _RANKED:
        return
    computed = {score["score_id"] for score in candidate["scores"] if score["status"] == COMPUTED}
    if not run.selection_scores <= computed:
        message = "a ranked window needs every score selection reads; exclude it instead"
        yield Finding(label, f"{pointer}/selection", "selection", message)
    if run.deterministic and selection["probability"] != _DETERMINISTIC[status]:
        message = f"deterministic selection gives {status} probability {_DETERMINISTIC[status]}"
        yield Finding(label, f"{pointer}/selection/probability", "selection", message)


def _audit(candidate: Mapping[str, Any], run: _Run, label: str, pointer: str) -> Iterator[Finding]:
    audit = candidate["audit"]
    pool = candidate["origin"]["source"] == POOL
    if pool != (audit["status"] in _AUDITED):
        message = "a pool window is sampled or not_sampled; a sibling window is ineligible"
        yield Finding(label, f"{pointer}/audit/status", "audit", message)
    if audit["status"] not in _AUDITED:
        return
    stratum = run.strata.get(audit["stratum_id"])
    if stratum is None:
        message = f"stratum {audit['stratum_id']!r} is not in the run's audit design"
        yield Finding(label, f"{pointer}/audit/stratum_id", "audit", message)
        return
    if stratum["sample_size"] > stratum["eligible_count"]:
        return  # the run's own finding names the stratum; no window can match an impossible design
    expected = stratum["sample_size"] / stratum["eligible_count"]
    if not math.isclose(audit["inclusion_probability"], expected, rel_tol=PROBABILITY_TOLERANCE):
        message = f"the stratum's design gives inclusion probability {expected!r}"
        yield Finding(label, f"{pointer}/audit/inclusion_probability", "audit", message)
