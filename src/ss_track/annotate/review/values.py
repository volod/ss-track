"""The fields a comparison reads, and the JSON values it reports.

Geometry is one value per part. A part that is absent on a side is null, so a box
against an unlocalizable frame reports the box, the kind and the uncertainty.
"""

from ss_track.annotate.labels.geometry import Box, Point
from ss_track.annotate.labels.model import Instance, LabeledFrame, LabelGeometry, MotionEvent
from ss_track.core.refusal import JsonValue

INSTANCE_FIELDS = ("class_id", "identity", "non_scoring_mark")
FRAME_FIELDS = (
    "visibility",
    "camera_motion",
    "geometry.kind",
    "geometry.box",
    "geometry.amodal_box",
    "geometry.point",
    "geometry.uncertainty_px",
    "geometry.plausible_extent_px",
)
EVENT_FIELDS = (
    "instance_id",
    "onset_frame",
    "onset_uncertainty_frames",
    "visibility",
    "selection_quality",
    "reentry",
)
COMPARED_FIELDS = (INSTANCE_FIELDS, FRAME_FIELDS, EVENT_FIELDS)


def instance_values(instance: Instance) -> dict[str, JsonValue]:
    """Return the instance fields a disagreement can name."""
    return {
        "class_id": instance.class_id,
        "identity": instance.identity,
        "non_scoring_mark": instance.non_scoring_mark,
    }


def frame_values(frame: LabeledFrame) -> dict[str, JsonValue]:
    """Return the frame fields a disagreement can name, including each geometry part."""
    return {
        "visibility": frame.visibility,
        "camera_motion": frame.camera_motion,
        **geometry_values(frame.geometry),
    }


def geometry_values(geometry: LabelGeometry) -> dict[str, JsonValue]:
    """Return each geometry part. An unused part is null."""
    return {
        "geometry.kind": geometry.kind,
        "geometry.box": _box(geometry.box),
        "geometry.amodal_box": _box(geometry.amodal_box),
        "geometry.point": _point(geometry.point),
        "geometry.uncertainty_px": geometry.uncertainty_px,
        "geometry.plausible_extent_px": geometry.plausible_extent_px,
    }


def event_values(event: MotionEvent) -> dict[str, JsonValue]:
    """Return the motion-event fields a disagreement can name."""
    return {
        "instance_id": event.instance_id,
        "onset_frame": event.onset_frame,
        "onset_uncertainty_frames": event.onset_uncertainty_frames,
        "visibility": event.visibility,
        "selection_quality": event.selection_quality,
        "reentry": event.reentry,
    }


def _box(box: Box | None) -> JsonValue:
    if box is None:
        return None
    value: dict[str, JsonValue] = {
        "x": box.x,
        "y": box.y,
        "width": box.width,
        "height": box.height,
    }
    return value


def _point(point: Point | None) -> JsonValue:
    if point is None:
        return None
    value: dict[str, JsonValue] = {"x": point.x, "y": point.y}
    return value
