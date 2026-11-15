"""Derived labels for every stored transform except a track.

Boxes below are computed by hand from the parent `(1, 2, 4, 3)` on a 64 by 48 frame.
A scale of factor 2 maps a half-open span `[start, stop)` to `[start // 2, (stop - 1) // 2 + 1]`.
"""

from pathlib import Path

from ss_track.annotate.derive import prepare_case_labels
from ss_track.annotate.derive_document import checked_document
from ss_track.annotate.derive_geom import output_size
from ss_track.annotate.geometry import Box, Point
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.pack import load_scenario_pack
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.corpus.cases.scale import reduced_size
from tests.annotate.derive_files import (
    REVISION,
    box_frame,
    case_of,
    labels_of,
    point_frame,
    rect,
)
from tests.annotate.documents import frame, refused
from tests.annotate.support import changed


def test_identity_compression_and_timing_keep_the_box(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(tmp_path, pack, [box_frame()])
    identity = prepare_case_labels(labels, case_of({"kind": "identity"}), pack, REVISION)
    compression = prepare_case_labels(
        labels,
        case_of(
            {
                "kind": "compression",
                "encoder": "block-quant-rgb24-v1",
                "block": 8,
                "steps": [{"frame_index": 0, "step": 4}],
            }
        ),
        pack,
        REVISION,
    )
    timing = prepare_case_labels(
        labels,
        case_of(
            {
                "kind": "timing",
                "timestamp_quality": "derived",
                "gaps": [{"frame_index": 1, "scale": 2}],
            }
        ),
        pack,
        REVISION,
    )

    assert _box(identity.labels) == (1, 2, 4, 3)
    assert identity.timestamp_quality is None
    assert identity.labels.label_id == "case-1"
    assert _box(compression.labels) == (1, 2, 4, 3)
    assert compression.timestamp_quality is None
    assert _box(timing.labels) == (1, 2, 4, 3)
    assert timing.timestamp_quality == "derived"


def test_a_translation_clips_and_a_box_that_leaves_is_out_of_view(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(), point_frame(1, x=60, y=10, extent=4)])
    clipped = prepare_case_labels(labels, case_of(_translate(60, 0)), pack, REVISION)
    gone = prepare_case_labels(labels, case_of(_translate(70, 0)), pack, REVISION)
    point = prepare_case_labels(
        labels_of(tmp_path / "point", pack, [point_frame(x=60, y=10, extent=4)]),
        case_of(_translate(2, 0)),
        pack,
        REVISION,
    )
    left = prepare_case_labels(
        labels_of(tmp_path / "left", pack, [point_frame(x=60, y=10, extent=4)]),
        case_of(_translate(5, 0)),
        pack,
        REVISION,
    )

    assert _box(clipped.labels) == (61, 2, 3, 3)
    assert clipped.labels.instances[0].frames[0].visibility == "visible"
    assert clipped.labels.instances[0].frames[0].camera_motion == "shake"
    assert clipped.labels.instances[0].frames[1].visibility == "out_of_view"
    assert gone.labels.instances[0].frames[0].visibility == "out_of_view"
    assert gone.labels.instances[0].frames[0].geometry.kind == "unlocalizable"
    assert point.labels.instances[0].frames[0].geometry.point == Point(62, 10)
    assert left.labels.instances[0].frames[0].visibility == "out_of_view"


def test_scale_divides_a_box_and_writes_an_integer_uncertainty(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(
        tmp_path,
        pack,
        [box_frame(x=10, y=12, width=8, height=6, uncertainty=4, amodal=rect(0, 0, 8, 6))],
    )
    applied = prepare_case_labels(labels, case_of({"kind": "scale", "factor": 2}), pack, REVISION)
    document, _digest = checked_document(applied.labels, pack)
    geometry = document["instances"][0]["frames"][0]["geometry"]

    assert applied.labels.space.width == 32
    assert applied.labels.space.height == 24
    assert _box(applied.labels) == (5, 6, 4, 3)
    assert applied.labels.instances[0].frames[0].geometry.amodal_box == Box(0, 0, 4, 3)
    assert applied.timestamp_quality is None
    assert isinstance(geometry, dict)
    assert geometry["uncertainty_px"] == 2
    assert isinstance(geometry["uncertainty_px"], int)


def test_a_box_below_the_minimum_becomes_a_point_then_unlocalizable(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    parent = [box_frame(x=10, y=12, width=8, height=6, uncertainty=4)]
    pointed = load_scenario_pack(changed(tmp_path, _limits(4, None)))
    (tmp_path / "withheld").mkdir()
    withheld = load_scenario_pack(changed(tmp_path / "withheld", _limits(4, 4)))
    point = prepare_case_labels(
        labels_of(tmp_path / "point", pointed, parent),
        case_of({"kind": "scale", "factor": 2}),
        pointed,
        REVISION,
    )
    lost = prepare_case_labels(
        labels_of(tmp_path / "lost", withheld, parent),
        case_of({"kind": "scale", "factor": 2}),
        withheld,
        REVISION,
    )
    geometry = point.labels.instances[0].frames[0].geometry

    assert geometry.kind == "point_only"
    assert geometry.point == Point(6, 7)
    assert geometry.plausible_extent_px == 3
    assert geometry.uncertainty_px == 2
    assert lost.labels.instances[0].frames[0].visibility == "visible"
    assert lost.labels.instances[0].frames[0].geometry.kind == "unlocalizable"


def test_scale_divides_a_point_and_keeps_a_missing_extent(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    kept = prepare_case_labels(
        labels_of(tmp_path, pack, [point_frame(extent=5)]),
        case_of({"kind": "scale", "factor": 2}),
        pack,
        REVISION,
    )
    zero = prepare_case_labels(
        labels_of(tmp_path / "zero", pack, [point_frame(extent=1)]),
        case_of({"kind": "scale", "factor": 2}),
        pack,
        REVISION,
    )
    (tmp_path / "limited").mkdir()
    limited = load_scenario_pack(changed(tmp_path / "limited", _limits(None, 4)))
    below = prepare_case_labels(
        labels_of(tmp_path / "below", limited, [point_frame(extent=5)]),
        case_of({"kind": "scale", "factor": 2}),
        limited,
        REVISION,
    )
    missing = prepare_case_labels(
        labels_of(tmp_path / "missing", limited, [point_frame(extent=None)]),
        case_of({"kind": "scale", "factor": 2}),
        limited,
        REVISION,
    )

    assert kept.labels.instances[0].frames[0].geometry.point == Point(2, 3)
    assert kept.labels.instances[0].frames[0].geometry.plausible_extent_px == 2
    assert zero.labels.instances[0].frames[0].geometry.plausible_extent_px is None
    assert below.labels.instances[0].frames[0].geometry.kind == "unlocalizable"
    assert missing.labels.instances[0].frames[0].geometry.kind == "point_only"
    assert missing.labels.instances[0].frames[0].geometry.plausible_extent_px is None


def test_a_region_rewrites_only_the_frames_it_meets(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(
        tmp_path,
        pack,
        [box_frame(), box_frame(1, x=40, y=30), frame(2, visibility="unknown")],
    )
    inside = prepare_case_labels(labels, case_of(_region(rect(0, 0, 64, 48))), pack, REVISION)
    overlap = prepare_case_labels(labels, case_of(_region(rect(0, 0, 3, 48))), pack, REVISION)
    outside = prepare_case_labels(labels, case_of(_region(rect(30, 30, 4, 4))), pack, REVISION)
    point = prepare_case_labels(
        labels_of(tmp_path / "point", pack, [point_frame(x=2, y=2, extent=4)]),
        case_of(_region(rect(0, 0, 10, 10))),
        pack,
        REVISION,
    )

    assert inside.labels.instances[0].frames[0].visibility == "absent"
    assert inside.labels.instances[0].frames[0].geometry.kind == "unlocalizable"
    assert inside.labels.instances[0].frames[1].visibility == "absent"
    assert inside.labels.instances[0].frames[2].visibility == "unknown"
    assert inside.labels.motion_events[0].visibility == "absent"
    assert inside.labels.motion_events[0].reentry is False
    assert overlap.labels.instances[0].frames[0].visibility == "unknown"
    assert overlap.labels.instances[0].frames[0].geometry.kind == "unlocalizable"
    assert _box(outside.labels) == (1, 2, 4, 3)
    assert point.labels.instances[0].frames[0].visibility == "absent"
    assert len(inside.labels.instances) == 1


def test_a_frame_map_drops_a_removed_onset_and_repeats_a_frame(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels = labels_of(tmp_path, pack, [box_frame(), box_frame(1, x=8, y=8)])
    removed = prepare_case_labels(
        labels, case_of({"kind": "frame_map", "removed": [0], "repeated": []}), pack, REVISION
    )
    repeated = prepare_case_labels(
        labels,
        case_of(
            {
                "kind": "frame_map",
                "removed": [],
                "repeated": [{"frame_index": 2, "content_frame_index": 0}],
            }
        ),
        pack,
        REVISION,
    )

    assert [item.frame_index for item in removed.labels.instances[0].frames] == [1]
    assert removed.labels.motion_events == ()
    assert removed.timestamp_quality is None
    assert repeated.timestamp_quality == "derived"
    copied = repeated.labels.instances[0].frames[2]
    assert copied.frame_index == 2
    assert copied.geometry.box == Box(1, 2, 4, 3)
    refused(
        lambda: prepare_case_labels(
            labels_of(tmp_path / "empty", pack, [box_frame()]),
            case_of({"kind": "frame_map", "removed": [0], "repeated": []}),
            pack,
            REVISION,
        ),
        "derived labels have no instance",
    )


def test_scale_output_size_matches_the_pixel_reduction() -> None:
    assert output_size(64, 48, 2) == reduced_size(64, 48, 2)
    assert output_size(65, 47, 3) == reduced_size(65, 47, 3)


def test_a_scale_factor_below_two_is_refused(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = labels_of(tmp_path, pack, [box_frame()])
    refused(
        lambda: prepare_case_labels(
            labels, case_of({"kind": "scale", "factor": 1}), pack, REVISION
        ),
        "scale factor is below 2",
    )


def _box(labels: LabelSet) -> tuple[int, int, int, int]:
    box = labels.instances[0].frames[0].geometry.box
    if box is None:
        raise TypeError("frame has no box")
    return (box.x, box.y, box.width, box.height)


def _translate(dx: int, dy: int) -> dict[str, object]:
    return {
        "kind": "translate",
        "camera_motion": "shake",
        "frames": {"start_frame": 0, "end_frame": 4},
        "offsets": [{"frame_index": 0, "dx": dx, "dy": dy}, {"frame_index": 1, "dx": dx, "dy": dy}],
    }


def _region(region: dict[str, int]) -> dict[str, object]:
    return {
        "kind": "region_status",
        "frames": {"start_frame": 0, "end_frame": 3},
        "region": region,
        "inside": "absent",
        "overlap": "unknown",
        "overlap_geometry": "unlocalizable",
        "added_objects": "distractor",
    }


def _limits(box: int | None, point: int | None):
    def mutate(body: dict[str, object]) -> None:
        limits = body["limits"]
        if not isinstance(limits, dict):
            raise TypeError("limits are not an object")
        limits["min_box_extent_px"] = box
        limits["min_point_extent_px"] = point

    return mutate
