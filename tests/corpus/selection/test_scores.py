"""Scores are hand-checkable functions of a window's rows, and an impossible one says why."""

import math

import numpy as np

from ss_track.corpus.selection.catalog import ScoreSpec, score_specs
from ss_track.corpus.selection.embeddings import StreamEmbedding
from ss_track.corpus.selection.scores import WindowFacts, candidate_scores

DEVIATION = ScoreSpec("clip.deviation", "background-deviation", 1, ("clip",))
INSTABILITY = ScoreSpec("clip.instability", "temporal-instability", 1, ("clip",))
MOTION = ScoreSpec("motion", "block-difference", 1, ())


def _rows(*angles: float) -> np.ndarray:
    return np.array([[math.cos(angle), math.sin(angle)] for angle in angles])


def _facts(frames: list[int], rows: np.ndarray) -> WindowFacts:
    embedding = StreamEmbedding(np.array(frames), rows)
    return WindowFacts({"one": {1: 2.0, 2: 7.0, 3: 1.0}}, {("clip", "one"): embedding})


def test_deviation_and_instability_are_one_minus_their_cosines() -> None:
    # Background: the unit mean of rows at 0, 0, 0 and 90 degrees.
    facts = _facts([0, 1, 2, 3], _rows(0.0, 0.0, 0.0, math.pi / 2))
    window = {"start_frame": 2, "end_frame": 4}

    scores = candidate_scores([DEVIATION, INSTABILITY, MOTION], facts, "one", window)

    background = np.array([3.0, 1.0]) / math.sqrt(10.0)
    descriptor = np.array([1.0, 1.0]) / math.sqrt(2.0)
    expected = round(1.0 - float(descriptor @ background), 10)
    assert scores == [
        {"status": "computed", "score_id": "clip.deviation", "value": expected},
        {"status": "computed", "score_id": "clip.instability", "value": 1.0},
        {"status": "computed", "score_id": "motion", "value": 1.0},
    ]


def test_a_score_a_window_cannot_support_is_unavailable_with_its_reason() -> None:
    facts = _facts([0, 2], _rows(0.0, 0.1))  # embedded at a stride of 2
    one_row = {"start_frame": 2, "end_frame": 4}
    one_frame = {"start_frame": 3, "end_frame": 4}

    scores = candidate_scores([DEVIATION, INSTABILITY, MOTION], facts, "one", one_row)
    short = candidate_scores([DEVIATION, MOTION], facts, "one", one_frame)
    missing = candidate_scores([DEVIATION], facts, "two", one_row)

    assert [item["status"] for item in scores] == ["computed", "unavailable", "computed"]
    assert scores[1] == {
        "status": "unavailable",
        "score_id": "clip.instability",
        "reason": "window_too_short",
    }
    assert [item["reason"] for item in short] == ["window_too_short", "window_too_short"]
    assert missing[0]["reason"] == "extractor_failed"


def test_a_tiled_score_takes_its_most_deviating_tile() -> None:
    still = StreamEmbedding(np.array([0, 1]), _rows(0.0, 0.0))
    moving = StreamEmbedding(np.array([0, 1]), _rows(0.0, math.pi / 2))
    tiled = ScoreSpec("clip.deviation", "background-deviation", 1, ("clip.r0c0", "clip.r0c1"))
    facts = WindowFacts({}, {("clip.r0c0", "one"): still, ("clip.r0c1", "one"): moving})

    (score,) = candidate_scores([tiled], facts, "one", {"start_frame": 1, "end_frame": 2})

    assert score["value"] == round(1.0 - math.cos(math.pi / 4), 10)


def test_the_catalog_names_scores_by_plan_extractor_in_order() -> None:
    specs = score_specs([("clip", ["clip"]), ("dino", ["dino.r0c1", "dino.r0c0"])])

    assert [spec.score_id for spec in specs] == [
        "clip.deviation",
        "clip.instability",
        "dino.deviation",
        "dino.instability",
        "motion",
    ]
    assert specs[2].extractor_ids == ("dino.r0c0", "dino.r0c1")
    assert specs[4].to_record()["extractor_ids"] == []
