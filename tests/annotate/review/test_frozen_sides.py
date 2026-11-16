"""A freeze that adopts the right side: a point frame, a one-sided frame and a one-sided event.

The left document has one box frame. The right has a point on that frame, a second frame and a
second motion event on it. Every expected value is written out by hand.
"""

from pathlib import Path
from typing import Any

from ss_track.annotate.labels.geometry import Point
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.compare import compare_label_sets
from ss_track.annotate.sources.frame_space import read_frame_space
from tests.annotate.documents import event, frame, load_labels
from tests.annotate.review_files import (
    decision_for,
    freeze_written,
    prepare_pair,
    write_review,
    write_settlement,
)


def _right(body: dict[str, Any]) -> None:
    target = body["instances"][0]
    target["frames"][0]["geometry"] = {
        "kind": "point_only",
        "point": {"x": 3, "y": 3},
        "uncertainty_px": 2,
        "plausible_extent_px": 5,
    }
    second = frame(1)
    second["annotator_id"] = "ann-b"
    target["frames"].append(second)
    later = event(onset=1)
    later["event_id"] = "onset-2"
    body["motion_events"].append(later)


def test_adopting_the_right_side_keeps_its_point_frame_and_event(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    left, right = prepare_pair(tmp_path, pack, rotated_clip, _right)
    write_review(tmp_path)
    rows = compare_label_sets(left, right)
    write_settlement(tmp_path, [decision_for(row, "right") for row in rows])
    freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))

    first, second = frozen.instances[0].frames
    assert first.geometry.kind == "point_only"
    assert first.geometry.point == Point(3, 3)
    assert first.geometry.box is None
    assert first.geometry.plausible_extent_px == 5
    assert second.frame_index == 1
    assert second.geometry.kind == "box"
    assert {item.annotator_id for item in (first, second)} == {"ada"}
    assert [item.event_id for item in frozen.motion_events] == ["onset-1", "onset-2"]


def test_omitting_one_sided_subjects_leaves_them_out(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    left, right = prepare_pair(tmp_path, pack, rotated_clip, _right)
    write_review(tmp_path)
    rows = compare_label_sets(left, right)
    write_settlement(tmp_path, [decision_for(row, "left") for row in rows])
    freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))

    assert [item.frame_index for item in frozen.instances[0].frames] == [0]
    assert frozen.instances[0].frames[0].geometry.kind == "box"
    assert [item.event_id for item in frozen.motion_events] == ["onset-1"]


def test_an_unknown_one_sided_frame_stays_and_its_event_is_uncertain(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    left, right = prepare_pair(tmp_path, pack, rotated_clip, _right)
    write_review(tmp_path)
    rows = compare_label_sets(left, right)
    decisions = [
        decision_for(row, "unknown" if row.subject == "frame" and row.frame_index == 1 else "left")
        for row in rows
    ]
    decisions = [
        item | {"outcome": "right"} if item.get("event_id") == "onset-2" else item
        for item in decisions
    ]
    write_settlement(tmp_path, decisions)
    freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))

    kept = frozen.instances[0].frames[1]
    assert (kept.visibility, kept.geometry.kind, kept.camera_motion) == (
        "unknown",
        "unlocalizable",
        "unknown",
    )
    added = next(item for item in frozen.motion_events if item.event_id == "onset-2")
    assert (added.visibility, added.selection_quality) == ("unknown", "uncertain")
