"""The candidates of one stream: pool windows that tile its bundle, sibling windows, and the audit draw.

The adapter ranks nothing, so its selection is the empty deterministic one: every window is
`not_selected` with probability 0, and SSL selection replaces it with scores of its own. The audit
sample is simple random sampling without replacement inside each encounter group: each pool window
gets a rank from the SHA-256 of the seed, its group, stream and candidate id, and the lowest ranks are
drawn. That rank is the same in any language and Python version, so a seed always draws one sample.
"""

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ss_track.core.refusal import JsonValue
from ss_track.corpus.discovery.inventory_rules import SIBLING_TIME, pool_windows
from ss_track.corpus.discovery.run_rules import NOT_SAMPLED, POOL, SAMPLED
from ss_track.corpus.siblings.video_hints import HintWindow

SELECTION_METHOD = "unranked"
SELECTION_REVISION = 1
AUDIT_DESIGN = "stratified_fixed_size"
AUDIT_REVISION = 1
_MIN_ID_DIGITS = 3
_SLOT_DIGITS = 8
_UNRANKED: dict[str, JsonValue] = {"status": "not_selected", "probability": 0.0}
_INELIGIBLE: dict[str, JsonValue] = {"status": "ineligible", "reason": "no_inclusion_probability"}


def unranked_selection() -> dict[str, JsonValue]:
    """Return the run's selection when the adapter ranks nothing."""
    return {
        "method": SELECTION_METHOD,
        "revision": SELECTION_REVISION,
        "seed": None,
        "budget": 0,
        "score_ids": [],
    }


@dataclass(frozen=True, slots=True)
class PoolWindow:
    """One pool window and the audit stratum, its stream's encounter group, it belongs to."""

    stratum_id: str
    stream_id: str
    candidate_id: str
    start_frame: int
    end_frame: int


def stream_pool(
    stream_id: str, group_id: str, bundle: Mapping[str, int], window_frames: int
) -> list[PoolWindow]:
    """Tile a bundle at the run's window length, naming each window so ids sort in frame order."""
    windows = pool_windows(bundle, window_frames)
    digits = max(_MIN_ID_DIGITS, len(str(len(windows) - 1)))
    return [
        PoolWindow(group_id, stream_id, f"pool-{index:0{digits}d}", start, end)
        for index, (start, end) in enumerate(windows)
    ]


def _rank(seed: int, window: PoolWindow) -> str:
    key = "\0".join((str(seed), window.stratum_id, window.stream_id, window.candidate_id))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditDraw:
    """The strata of the audit design and which pool windows it drew."""

    strata: list[JsonValue]
    sampled: frozenset[tuple[str, str]]  # stream and candidate id
    probability: dict[str, float]  # by stratum


def draw_audit(windows: Iterable[PoolWindow], seed: int, sample_size: int) -> AuditDraw:
    """Draw `sample_size` pool windows from each stratum, all of a smaller one."""
    by_stratum: dict[str, list[PoolWindow]] = {}
    for window in windows:
        by_stratum.setdefault(window.stratum_id, []).append(window)
    strata: list[JsonValue] = []
    sampled: set[tuple[str, str]] = set()
    probability: dict[str, float] = {}
    for stratum_id in sorted(by_stratum):
        members = by_stratum[stratum_id]
        size = min(sample_size, len(members))
        drawn = sorted(members, key=lambda window: _rank(seed, window))[:size]
        sampled.update((window.stream_id, window.candidate_id) for window in drawn)
        probability[stratum_id] = size / len(members)
        strata.append(
            {"stratum_id": stratum_id, "eligible_count": len(members), "sample_size": size}
        )
    return AuditDraw(strata, frozenset(sampled), probability)


def audit_design(draw: AuditDraw, seed: int) -> dict[str, JsonValue]:
    """Return the run's audit section."""
    return {"design": AUDIT_DESIGN, "revision": AUDIT_REVISION, "seed": seed, "strata": draw.strata}


def _window(start: int, end: int) -> dict[str, JsonValue]:
    return {"start_frame": start, "end_frame": end}


def pool_candidate(window: PoolWindow, draw: AuditDraw) -> dict[str, JsonValue]:
    """Return one pool window as a candidate, with its audit status and inclusion probability."""
    status = SAMPLED if (window.stream_id, window.candidate_id) in draw.sampled else NOT_SAMPLED
    return {
        "candidate_id": window.candidate_id,
        "window": _window(window.start_frame, window.end_frame),
        "origin": {"source": POOL},
        "scores": [],
        "selection": dict(_UNRANKED),
        "audit": {
            "status": status,
            "stratum_id": window.stratum_id,
            "inclusion_probability": draw.probability[window.stratum_id],
        },
    }


def sibling_candidate(hint_source_id: str, window: HintWindow) -> dict[str, JsonValue]:
    """Return one window a sibling time named; no inclusion probability, so never audited."""
    return {
        "candidate_id": f"sibling-{hint_source_id}-{window.slot:0{_SLOT_DIGITS}d}",
        "window": _window(window.start_frame, window.end_frame),
        "origin": {"source": SIBLING_TIME, "hint_source_id": hint_source_id, "slot": window.slot},
        "scores": [],
        "selection": dict(_UNRANKED),
        "audit": dict(_INELIGIBLE),
    }


def stream_candidates(
    pool: Sequence[PoolWindow],
    draw: AuditDraw,
    hints: Mapping[str, Iterable[HintWindow]],
    stream_id: str,
) -> list[JsonValue]:
    """Return one stream's candidates in candidate_id order."""
    candidates = [pool_candidate(window, draw) for window in pool]
    for hint_source_id in sorted(hints):
        candidates += [
            sibling_candidate(hint_source_id, window)
            for window in sorted(hints[hint_source_id])
            if window.stream_id == stream_id
        ]
    candidates.sort(key=lambda item: str(item["candidate_id"]))
    ordered: list[JsonValue] = list(candidates)
    return ordered
