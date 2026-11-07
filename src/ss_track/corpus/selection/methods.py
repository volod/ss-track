"""Selection methods: rank pool windows for review within a budget, stating each probability.

Every method ranks only pool windows: a sibling window keeps its scores for review but is
`not_selected` with probability 0. A pool window of a stream in the locked split is excluded as
`operator_excluded`, since no locked-test custodian policy exists to allow it; an excluded window
stays in the audit pool, which depends only on origin.

- `unranked` ranks nothing: every window is `not_selected` with probability 0.
- `uniform` is the baseline: a simple random sample of `min(budget, N)` of the `N` eligible pool
  windows, each with inclusion probability `min(budget, N) / N`. Windows rank by the SHA-256 of a
  key that names the method, so a selection seed equal to the audit seed still draws independently.
- `ssl-diverse` is deterministic. A window needs every score it reads, or it is excluded as
  `features_unavailable`. Each score becomes a percentile among eligible windows, ties averaged,
  and a window's priority is their mean. Picks are greedy: each takes the highest priority less
  half its largest cosine similarity to a window already picked, the similarity being the mean over
  the run extractors the scores read of the windows' descriptors. Ties go to the first window in
  stream and candidate order.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from ss_track.core.refusal import JsonValue
from ss_track.corpus.selection.catalog import METHOD_REVISIONS, UNIFORM, UNRANKED

DIVERSITY_WEIGHT = 0.5
_NOT_RANKED: dict[str, JsonValue] = {"status": "not_selected", "probability": 0.0}

type Key = tuple[str, str]  # stream and candidate id


@dataclass(frozen=True, slots=True)
class Window:
    """One candidate as a selection method sees it."""

    stream_id: str
    candidate_id: str
    pool: bool
    locked: bool
    values: Mapping[str, float]  # computed scores only
    descriptors: Mapping[str, np.ndarray]  # unit window mean rows, by run extractor

    @property
    def key(self) -> Key:
        return (self.stream_id, self.candidate_id)


@dataclass(frozen=True, slots=True)
class SelectionSpec:
    """The run's selection section, which a method reproduces from the run alone."""

    method: str
    budget: int
    seed: int | None
    score_ids: tuple[str, ...]
    extractor_ids: tuple[str, ...]  # what diversity compares, from the scores read


def select(spec: SelectionSpec, windows: Sequence[Window]) -> dict[Key, dict[str, JsonValue]]:
    """Return every window's selection under the run's method."""
    decided = {window.key: dict(_NOT_RANKED) for window in windows}
    if spec.method == UNRANKED:
        return decided
    eligible: list[Window] = []
    for window in sorted((item for item in windows if item.pool), key=lambda item: item.key):
        reason = _exclusion(spec, window)
        if reason is None:
            eligible.append(window)
        else:
            decided[window.key] = {"status": "excluded", "reason": reason}
    picks = _uniform(spec, eligible) if spec.method == UNIFORM else _diverse(spec, eligible)
    count = len(picks)
    probability = count / len(eligible) if spec.method == UNIFORM and eligible else 0.0
    for window in eligible:
        decided[window.key] = {"status": "not_selected", "probability": probability}
    for rank, window in enumerate(picks, start=1):
        chance = probability if spec.method == UNIFORM else 1.0
        decided[window.key] = {"status": "selected", "rank": rank, "probability": chance}
    return decided


def _exclusion(spec: SelectionSpec, window: Window) -> str | None:
    """Return why a pool window cannot be ranked, or None when it can."""
    if window.locked:
        return "operator_excluded"
    if not all(score_id in window.values for score_id in spec.score_ids):
        return "features_unavailable"
    return None


def _uniform(spec: SelectionSpec, eligible: Sequence[Window]) -> list[Window]:
    def rank(window: Window) -> str:
        key = "\0".join((UNIFORM, str(spec.seed), window.stream_id, window.candidate_id))
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    return sorted(eligible, key=rank)[: min(spec.budget, len(eligible))]


def _percentiles(values: np.ndarray) -> np.ndarray:
    """Return each value's rank among all, ties averaged, from 0 for the least to 1 for the most."""
    if len(values) == 1:
        return np.ones(1)
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values))
    ranks[order] = np.arange(len(values), dtype=np.float64)
    _, inverse = np.unique(values, return_inverse=True)
    averaged = np.bincount(inverse, weights=ranks) / np.bincount(inverse)
    percentiles: np.ndarray = averaged[inverse] / (len(values) - 1)
    return percentiles


def _diverse(spec: SelectionSpec, eligible: Sequence[Window]) -> list[Window]:
    if not eligible:
        return []
    priority = np.mean(
        [
            _percentiles(np.array([window.values[score_id] for window in eligible]))
            for score_id in spec.score_ids
        ],
        axis=0,
    )
    descriptors = [
        np.stack([window.descriptors[extractor_id] for window in eligible])
        for extractor_id in spec.extractor_ids
    ]
    nearest = np.zeros(len(eligible))
    open_ = np.ones(len(eligible), dtype=bool)
    picks: list[Window] = []
    for _ in range(min(spec.budget, len(eligible))):
        gain = np.where(open_, priority - DIVERSITY_WEIGHT * nearest, -np.inf)
        best = int(np.argmax(gain))
        picks.append(eligible[best])
        open_[best] = False
        if descriptors:
            similarity = np.mean([matrix @ matrix[best] for matrix in descriptors], axis=0)
            nearest = np.maximum(nearest, np.maximum(similarity, 0.0))
    return picks


def known_selection(method: str, revision: int) -> bool:
    """Say whether this ss-track can reproduce a selection of this method and revision."""
    return METHOD_REVISIONS.get(method) == revision
