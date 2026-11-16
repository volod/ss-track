"""Track roles and a track that is not the frozen instance.

The parent box is `(1, 2, 4, 3)`. A shift of one pixel would leave that box in frame;
the target is still `out_of_view`. A distractor copy is a second instance.
"""

from pathlib import Path
from typing import Any

from ss_track.annotate.labels.geometry import Box
from ss_track.annotate.packs.load import load_scenario_pack
from ss_track.annotate.packs.model import ScenarioPack
from tests.annotate.derive_files import (
    apply_track_case,
    box_frame,
    boxed,
    distractor,
    first_box,
    labels_of,
    other_instance,
    rect,
    shift,
    track_box,
)
from tests.annotate.documents import refused
from tests.annotate.support import changed

_COPY = rect(20, 10, 6, 6)


def test_unchanged_reentry_shift_and_unknown(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(tmp_path, pack, [box_frame()], extra=[other_instance()])
    unchanged = apply_track_case(labels, pack, [boxed(0, "unchanged")], [track_box(0)])
    reentry = apply_track_case(labels, pack, [boxed(0, "reentry")], [track_box(0)])
    shifted = apply_track_case(labels, pack, [shift(0, 1, 0)], [track_box(0)])
    invented = apply_track_case(
        labels,
        pack,
        [boxed(0, "unchanged"), {"frame_index": 1, "role": "unknown"}],
        [track_box(0)],
        window=(0, 2),
    )

    assert first_box(unchanged) == (1, 2, 4, 3)
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


def test_a_return_is_one_reentry_event(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(index) for index in range(4)])
    applied = apply_track_case(
        labels,
        pack,
        [boxed(0, "unchanged"), shift(1, 70, 0), boxed(2, "reentry"), boxed(3, "reentry")],
        [track_box(index) for index in range(4)],
        window=(0, 4),
    )

    returns = [event for event in applied.motion_events if event.reentry]
    assert [event.onset_frame for event in returns] == [2]
    assert applied.instances[0].frames[1].visibility == "out_of_view"
    assert applied.instances[0].frames[3].geometry.box == Box(1, 2, 4, 3)
    assert len(applied.motion_events) == 2


def test_a_distractor_copy_is_not_the_target_box(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(tmp_path, pack, [box_frame()])
    applied = apply_track_case(labels, pack, [distractor(0, _COPY)], [track_box(0)])
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


def test_a_track_that_is_not_the_frozen_instance_is_refused(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(), box_frame(1)])
    refused(
        lambda: apply_track_case(
            labels, pack, [boxed(0, "unchanged")], [track_box(0)], revision="cd" * 32
        ),
        "label_revision does not match",
    )
    refused(
        lambda: apply_track_case(labels, pack, [boxed(0, "unchanged")], [track_box(0, x=9, y=9)]),
        "track box does not match",
    )
    refused(
        lambda: apply_track_case(
            labels,
            pack,
            [boxed(0, "unchanged"), {"frame_index": 1, "role": "unknown"}],
            [track_box(0)],
            window=(0, 2),
        ),
        "track box does not match",
    )
    refused(
        lambda: apply_track_case(labels, pack, [boxed(0, "unchanged", x=2)], [track_box(0)]),
        "frame 0 box does not match the track status",
    )


def test_a_copied_box_needs_one_distractor_class(tmp_path: Path, pack: ScenarioPack) -> None:
    none = load_scenario_pack(changed(tmp_path, _role("insect", "ignore")))
    (tmp_path / "two").mkdir()
    two = load_scenario_pack(changed(tmp_path / "two", _add_distractor))
    refused(
        lambda: apply_track_case(
            labels_of(tmp_path / "none", none, [box_frame()]),
            none,
            [distractor(0, _COPY)],
            [track_box(0)],
        ),
        "one distractor class",
    )
    refused(
        lambda: apply_track_case(
            labels_of(tmp_path / "two-labels", two, [box_frame()]),
            two,
            [distractor(0, _COPY)],
            [track_box(0)],
        ),
        "one distractor class",
    )


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
