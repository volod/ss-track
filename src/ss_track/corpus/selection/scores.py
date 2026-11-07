"""Score every candidate window: motion, background deviation and temporal instability.

- `motion` (`block-difference`) is the largest block luma change between consecutive frames
  (`motion.py`); a window of one frame has none.
- `<extractor>.deviation` (`background-deviation`) is how far a window's descriptor is from its
  stream's background, `1 - cos`, the most of any run extractor the score reads. On a fixed camera
  a rare or unfamiliar object stands out from what the stream usually shows; with tiles, it
  stands out in its own tile.
- `<extractor>.instability` (`temporal-instability`) is the mean `1 - cos` between consecutive
  embedded frames of a window, the most of any run extractor the score reads. A frozen backbone has
  no classifier and so no calibrated uncertainty; how much its account of a window changes from
  frame to frame stands in for it. It needs two embedded frames in the window.

A score that cannot be computed is `unavailable` with its reason, never a guessed value. Values are
rounded to ten decimals, so a recomputation on the same host compares exactly.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from ss_track.core.refusal import JsonValue
from ss_track.corpus.selection.catalog import SCORE_METHODS, ScoreSpec
from ss_track.corpus.selection.embeddings import StreamEmbedding, unit
from ss_track.corpus.selection.motion import window_motion

DECIMALS = 10
WINDOW_TOO_SHORT = "window_too_short"
EXTRACTOR_FAILED = "extractor_failed"
_MEASURES = {method: measure for measure, method in SCORE_METHODS.items()}


@dataclass(frozen=True, slots=True)
class WindowFacts:
    """What scoring knows of a run: each stream's frame changes and each extractor's rows."""

    changes: Mapping[str, Mapping[int, float]]
    embeddings: Mapping[tuple[str, str], StreamEmbedding]


def _deviation(embedding: StreamEmbedding, rows: np.ndarray) -> float:
    return 1.0 - float(unit(rows.mean(axis=0)) @ embedding.background())


def _instability(_: StreamEmbedding, rows: np.ndarray) -> float:
    return float(np.mean(1.0 - np.sum(rows[1:] * rows[:-1], axis=1)))


_EMBEDDING_SCORES = {"deviation": (_deviation, 1), "instability": (_instability, 2)}


def _value(value: float) -> float:
    return round(max(0.0, value), DECIMALS)


def _embedding_score(
    spec: ScoreSpec, measure: str, facts: WindowFacts, stream_id: str, window: Mapping[str, int]
) -> float | str:
    function, needed = _EMBEDDING_SCORES[measure]
    values: list[float] = []
    for extractor_id in spec.extractor_ids:
        embedding = facts.embeddings.get((extractor_id, stream_id))
        if embedding is None:
            return EXTRACTOR_FAILED
        rows = embedding.window(window["start_frame"], window["end_frame"])
        if len(rows) < needed:
            return WINDOW_TOO_SHORT
        values.append(function(embedding, rows))
    return _value(max(values))


def score_value(
    spec: ScoreSpec, facts: WindowFacts, stream_id: str, window: Mapping[str, int]
) -> float | str:
    """Return one window's value of one score, or the reason it is unavailable."""
    measure = _MEASURES[(spec.method, spec.revision)]
    if measure != "motion":
        return _embedding_score(spec, measure, facts, stream_id, window)
    motion = window_motion(facts.changes[stream_id], window["start_frame"], window["end_frame"])
    return WINDOW_TOO_SHORT if motion is None else _value(motion)


def candidate_scores(
    specs: Sequence[ScoreSpec], facts: WindowFacts, stream_id: str, window: Mapping[str, int]
) -> list[JsonValue]:
    """Return a candidate's scores in the run's score order."""
    scores: list[JsonValue] = []
    for spec in specs:
        value = score_value(spec, facts, stream_id, window)
        if isinstance(value, str):
            scores.append({"status": "unavailable", "score_id": spec.score_id, "reason": value})
        else:
            scores.append({"status": "computed", "score_id": spec.score_id, "value": value})
    return scores


def known_method(method: str, revision: int) -> bool:
    """Say whether this ss-track can compute a score of this method and revision."""
    return (method, revision) in _MEASURES
