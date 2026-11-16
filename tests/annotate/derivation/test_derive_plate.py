"""The plate a removal or an absence copies must show no target where it is painted.

The parent box is `(1, 2, 4, 3)`. A plate frame is refused when any part of a scoring
target lies inside a painted region, or when a target there has no known location.
On a case frame, a target the region only overlaps stays `unknown`.
"""

from pathlib import Path

from ss_track.annotate.derivation.derive import prepare_case_labels
from ss_track.annotate.packs.model import ScenarioPack
from tests.annotate.derive_files import (
    BOX,
    REVISION,
    apply_track_case,
    box_frame,
    case_of,
    labels_of,
    point_frame,
    rect,
    removal,
    status_region,
    track_box,
)
from tests.annotate.documents import frame, refused

_SHOWN = "plate frame 2 shows a target inside the region"
_AWAY = {"x": 50, "y": 40}


def test_a_case_frame_the_region_only_overlaps_stays_unknown(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(), box_frame(1), box_frame(2, **_AWAY)])
    partial = apply_track_case(
        labels,
        pack,
        [removal(0, rect(0, 0, 3, 48)), removal(1, rect(40, 30, 4, 4))],
        [track_box(0), track_box(1)],
        window=(0, 2),
        plate_frame=2,
    )

    assert partial.instances[0].frames[0].visibility == "unknown"
    assert partial.instances[0].frames[0].geometry.kind == "unlocalizable"
    assert partial.instances[0].frames[1].visibility == "visible"


def test_a_plate_that_shows_any_part_of_a_target_is_refused(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(), box_frame(1), box_frame(2)])
    for region in (dict(BOX), rect(0, 0, 3, 48), rect(4, 4, 30, 30)):
        refused(
            lambda region=region: apply_track_case(
                labels,
                pack,
                [removal(0, rect(40, 30, 4, 4)), removal(1, region)],
                [track_box(0), track_box(1)],
                window=(0, 2),
                plate_frame=2,
            ),
            _SHOWN,
        )
    refused(
        lambda: prepare_case_labels(
            labels_of(tmp_path / "point", pack, [point_frame(x=2, y=2, extent=4)]),
            case_of(status_region(rect(0, 0, 10, 10)), parameters={"plate_frame": 0}),
            pack,
            REVISION,
        ),
        "plate frame 0 shows a target inside the region",
    )


def test_a_slowly_moving_target_cannot_be_its_own_plate(tmp_path: Path, pack: ScenarioPack) -> None:
    frames = [box_frame(index, x=1 + index) for index in range(3)]
    labels = labels_of(tmp_path, pack, frames)
    refused(
        lambda: apply_track_case(
            labels,
            pack,
            [removal(0, rect(1, 2, 4, 3)), removal(1, rect(2, 2, 4, 3))],
            [track_box(0, x=1), track_box(1, x=2)],
            window=(0, 2),
            plate_frame=2,
        ),
        _SHOWN,
    )


def test_a_plate_target_of_unknown_location_is_refused(tmp_path: Path, pack: ScenarioPack) -> None:
    absence = case_of(status_region(rect(40, 30, 10, 10)), parameters={"plate_frame": 1})
    unlocated = frame(1)
    unlocated["geometry"] = {"kind": "unlocalizable"}
    for name, plate in (("unknown", frame(1, "unknown")), ("unlocated", unlocated)):
        labels = labels_of(tmp_path / name, pack, [box_frame(), plate])
        refused(
            lambda labels=labels: prepare_case_labels(labels, absence, pack, REVISION),
            "plate frame 1 has a target of unknown location",
        )
    for visibility in ("fully_occluded", "out_of_view", "absent"):
        labels = labels_of(tmp_path / visibility, pack, [box_frame(), frame(1, visibility)])
        applied = prepare_case_labels(labels, absence, pack, REVISION)
        assert applied.labels.instances[0].frames[0].visibility == "visible"


def test_a_plate_distractor_is_not_a_target(tmp_path: Path, pack: ScenarioPack) -> None:
    insect = {
        "instance_id": "insect-1",
        "class_id": "insect",
        "identity": "reviewed",
        "non_scoring_mark": "distractor",
        "frames": [box_frame(1, x=40, y=30)],
    }
    labels = labels_of(tmp_path, pack, [box_frame()], extra=[insect])
    absence = case_of(status_region(rect(38, 28, 10, 10)), parameters={"plate_frame": 1})

    applied = prepare_case_labels(labels, absence, pack, REVISION)
    assert applied.labels.instances[0].frames[0].geometry.box is not None
