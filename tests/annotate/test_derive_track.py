"""Track roles, plate refusals and a track that is not the frozen instance.

The parent box is `(1, 2, 4, 3)`. A shift of one pixel would leave that box in frame;
the target is still `out_of_view`. A distractor copy is a second instance.
"""

from pathlib import Path
from typing import Any

from ss_track.annotate.derive import prepare_case_labels
from ss_track.annotate.geometry import Box
from ss_track.annotate.pack import load_scenario_pack
from ss_track.annotate.pack_model import ScenarioPack
from tests.annotate.derive_files import (
    BOX,
    REVISION,
    box_frame,
    case_of,
    labels_of,
    other_instance,
    point_frame,
    rect,
)
from tests.annotate.documents import refused
from tests.annotate.support import changed

_COPY = rect(20, 10, 6, 6)


def test_unchanged_reentry_shift_and_unknown(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(tmp_path, pack, [box_frame()], extra=[other_instance()])
    unchanged = _apply(labels, pack, [_boxed(0, "unchanged")], [_track_box(0)])
    reentry = _apply(labels, pack, [_boxed(0, "reentry")], [_track_box(0)])
    shifted = _apply(labels, pack, [_shift(0, 1, 0)], [_track_box(0)])
    invented = _apply(
        labels,
        pack,
        [_boxed(0, "unchanged"), {"frame_index": 1, "role": "unknown"}],
        [_track_box(0)],
        window=(0, 2),
    )

    assert _box(unchanged) == (1, 2, 4, 3)
    assert unchanged.motion_events[0].reentry is False
    assert reentry.motion_events[0].reentry is True
    assert reentry.motion_events[0].visibility == "visible"
    assert shifted.instances[0].frames[0].visibility == "out_of_view"
    other = shifted.instances[1].frames[0].geometry.box
    assert other == Box(21, 10, 6, 6)
    invented_frame = invented.instances[0].frames[1]
    assert invented_frame.visibility == "unknown"
    assert invented_frame.camera_motion == "unknown"
    assert invented_frame.annotator_id == "ann-a"
    assert invented_frame.geometry.kind == "unlocalizable"


def test_a_distractor_copy_is_not_the_target_box(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(tmp_path, pack, [box_frame()])
    applied = _apply(labels, pack, [_distractor(0, _COPY)], [_track_box(0)])
    target = applied.instances[0]
    copy = applied.instances[1]

    assert target.instance_id == "target-1"
    assert target.frames[0].geometry.box == Box(1, 2, 4, 3)
    assert copy.instance_id == "copy-target-1"
    assert copy.class_id == "insect"
    assert copy.non_scoring_mark == "distractor"
    assert copy.identity == "reviewed"
    assert copy.frames[0].geometry.box == Box(20, 10, 6, 6)
    assert copy.frames[0].geometry.amodal_box is None
    assert copy.frames[0].geometry.uncertainty_px == 1


def test_overlap_stays_unknown_and_a_covered_plate_is_refused(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(), box_frame(1)])
    partial = _apply(
        labels,
        pack,
        [_removal(0, rect(0, 0, 3, 48)), _removal(1, rect(40, 30, 4, 4))],
        [_track_box(0), _track_box(1)],
        window=(0, 2),
        plate_frame=0,
    )
    assert partial.instances[0].frames[0].visibility == "unknown"
    assert partial.instances[0].frames[1].visibility == "visible"
    refused(
        lambda: _apply(
            labels,
            pack,
            [_removal(0, rect(40, 30, 4, 4)), _removal(1, dict(BOX))],
            [_track_box(0), _track_box(1)],
            window=(0, 2),
            plate_frame=0,
        ),
        "plate frame 0 shows a target inside the region",
    )
    refused(
        lambda: prepare_case_labels(
            labels_of(tmp_path / "point", pack, [point_frame(x=2, y=2, extent=4)]),
            case_of(_status_region(rect(0, 0, 10, 10)), parameters={"plate_frame": 0}),
            pack,
            REVISION,
        ),
        "plate frame 0 shows a target inside the region",
    )


def test_a_track_that_is_not_the_frozen_instance_is_refused(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(), box_frame(1)])
    refused(
        lambda: _apply(labels, pack, [_boxed(0, "unchanged")], [_track_box(0)], revision="cd" * 32),
        "label_revision does not match",
    )
    refused(
        lambda: _apply(labels, pack, [_boxed(0, "unchanged")], [_track_box(0, x=9, y=9)]),
        "track box does not match",
    )
    refused(
        lambda: _apply(
            labels,
            pack,
            [_boxed(0, "unchanged"), {"frame_index": 1, "role": "unknown"}],
            [_track_box(0)],
            window=(0, 2),
        ),
        "track box does not match",
    )
    refused(
        lambda: _apply(labels, pack, [_boxed(0, "unchanged", x=2)], [_track_box(0)]),
        "frame 0 box does not match the track status",
    )


def test_a_copied_box_needs_one_distractor_class(tmp_path: Path, pack: ScenarioPack) -> None:
    none = load_scenario_pack(changed(tmp_path, _role("insect", "ignore")))
    (tmp_path / "two").mkdir()
    two = load_scenario_pack(changed(tmp_path / "two", _add_distractor))
    refused(
        lambda: _apply(
            labels_of(tmp_path / "none", none, [box_frame()]),
            none,
            [_distractor(0, _COPY)],
            [_track_box(0)],
        ),
        "one distractor class",
    )
    refused(
        lambda: _apply(
            labels_of(tmp_path / "two-labels", two, [box_frame()]),
            two,
            [_distractor(0, _COPY)],
            [_track_box(0)],
        ),
        "one distractor class",
    )


def _apply(
    labels: Any,
    pack: ScenarioPack,
    frames: list[dict[str, object]],
    track: list[dict[str, object]],
    *,
    window: tuple[int, int] = (0, 1),
    revision: str = REVISION,
    **parameters: object,
) -> Any:
    transform = {
        "kind": "track_status",
        "label_revision": revision,
        "instance_id": "target-1",
        "frames": frames,
    }
    body = case_of(
        transform,
        window=window,
        parameters={"track": track, **parameters},
    )
    return prepare_case_labels(labels, body, pack, REVISION).labels


def _box(labels: Any) -> tuple[int, int, int, int]:
    box = labels.instances[0].frames[0].geometry.box
    if box is None:
        raise TypeError("frame has no box")
    return (box.x, box.y, box.width, box.height)


def _track_box(index: int, *, x: int = 1, y: int = 2) -> dict[str, object]:
    return {"frame_index": index, "box": rect(x, y, 4, 3)}


def _boxed(index: int, role: str, *, x: int = 1, y: int = 2) -> dict[str, object]:
    return {"frame_index": index, "role": role, "region": rect(x, y, 4, 3)}


def _shift(index: int, dx: int, dy: int) -> dict[str, object]:
    return {
        "frame_index": index,
        "role": "shift",
        "dx": dx,
        "dy": dy,
        "region": dict(BOX),
        "visibility": "out_of_view",
    }


def _removal(index: int, region: dict[str, int]) -> dict[str, object]:
    return {
        "frame_index": index,
        "role": "region",
        "region": region,
        "inside": "absent",
        "overlap": "unknown",
        "overlap_geometry": "unlocalizable",
    }


def _distractor(index: int, region: dict[str, int]) -> dict[str, object]:
    return _removal(index, region) | {
        "inside": "unknown",
        "overlap": "unknown",
        "added_objects": "distractor",
    }


def _status_region(region: dict[str, int]) -> dict[str, object]:
    return {
        "kind": "region_status",
        "frames": {"start_frame": 0, "end_frame": 1},
        "region": region,
        "inside": "absent",
        "overlap": "unknown",
        "overlap_geometry": "unlocalizable",
    }


def _role(class_id: str, role: str):
    def mutate(body: dict[str, Any]) -> None:
        classes = body["classes"]
        if not isinstance(classes, list):
            raise TypeError("classes are not a list")
        for item in classes:
            if isinstance(item, dict) and item.get("class_id") == class_id:
                item["role"] = role

    return mutate


def _add_distractor(body: dict[str, Any]) -> None:
    classes = body["classes"]
    if not isinstance(classes, list):
        raise TypeError("classes are not a list")
    classes.append(
        {"class_id": "moth", "name": "moth", "role": "distractor", "parent_class_id": None}
    )
