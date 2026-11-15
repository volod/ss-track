"""Read a label document whose contract has already accepted it."""

from ss_track.annotate.geometry import Box, Point
from ss_track.annotate.label_model import (
    Instance,
    LabeledFrame,
    LabelGeometry,
    LabelSet,
    MotionEvent,
)
from ss_track.annotate.space import DeclaredSpace
from ss_track.corpus.declarations.fields import Fields


def read_label_set(fields: Fields, document_sha256: str) -> LabelSet:
    """Return the typed labels. Cross-field rules are applied by the caller."""
    return LabelSet(
        label_id=fields.string("label_id"),
        pack_id=fields.string("pack_id"),
        pack_hash=fields.string("pack_hash"),
        space=_space(fields),
        instances=tuple(
            _instance(Fields(item, fields.where)) for item in fields.items("instances")
        ),
        motion_events=tuple(
            _event(Fields(item, fields.where)) for item in fields.items("motion_events")
        ),
        document_sha256=document_sha256,
    )


def _space(fields: Fields) -> DeclaredSpace:
    return DeclaredSpace(
        source_sha256=fields.string("source_sha256"),
        width=fields.index("width"),
        height=fields.index("height"),
        frame_count=fields.index("frame_count"),
        orientation_degrees=fields.index("orientation_degrees"),
        display_rotation_degrees=fields.index("display_rotation_degrees"),
    )


def _instance(fields: Fields) -> Instance:
    mark = fields.nullable_text("non_scoring_mark")
    return Instance(
        instance_id=fields.string("instance_id"),
        class_id=fields.string("class_id"),
        identity=fields.string("identity"),
        non_scoring_mark=mark,
        frames=tuple(_frame(Fields(item, fields.where)) for item in fields.items("frames")),
    )


def _frame(fields: Fields) -> LabeledFrame:
    return LabeledFrame(
        frame_index=fields.index("frame_index"),
        visibility=fields.string("visibility"),
        camera_motion=fields.string("camera_motion"),
        annotator_id=fields.string("annotator_id"),
        geometry=_geometry(fields.child("geometry")),
    )


def _geometry(fields: Fields) -> LabelGeometry:
    kind = fields.string("kind")
    if kind == "box":
        _require_absent_extent(fields)
        return LabelGeometry(
            "box",
            _box(fields.child("box")),
            None,
            _optional_box(fields),
            fields.number("uncertainty_px"),
            None,
        )
    if kind == "point_only":
        return LabelGeometry(
            "point_only",
            None,
            _point(fields.child("point")),
            None,
            fields.number("uncertainty_px"),
            fields.nullable_index("plausible_extent_px"),
        )
    if kind == "unlocalizable":
        return LabelGeometry("unlocalizable", None, None, None, None, None)
    raise TypeError(f"{fields.where} kind {kind} is not in the contract")


def _require_absent_extent(fields: Fields) -> None:
    if fields.nullable_index("plausible_extent_px") is not None:
        raise TypeError(f"{fields.where} box has a plausible extent")


def _optional_box(fields: Fields) -> Box | None:
    nested = fields.nullable_child("amodal_box")
    return None if nested is None else _box(nested)


def _box(fields: Fields) -> Box:
    return Box(fields.index("x"), fields.index("y"), fields.index("width"), fields.index("height"))


def _point(fields: Fields) -> Point:
    return Point(fields.index("x"), fields.index("y"))


def _event(fields: Fields) -> MotionEvent:
    return MotionEvent(
        event_id=fields.string("event_id"),
        instance_id=fields.string("instance_id"),
        onset_frame=fields.index("onset_frame"),
        onset_uncertainty_frames=fields.index("onset_uncertainty_frames"),
        visibility=fields.string("visibility"),
        selection_quality=fields.string("selection_quality"),
        reentry=fields.boolean("reentry"),
    )
