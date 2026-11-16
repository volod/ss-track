"""Frozen frames of one label revision.

An unknown frame is visibility ``unknown`` and geometry ``unlocalizable``. Camera
motion stays independent of that wipe: an unknown camera is stored as ``unknown``
and an agreed camera is kept. Any other unknown frame field wipes visibility and
geometry together.
"""

from collections.abc import Iterable

from ss_track.annotate.labels.model import Instance, LabeledFrame
from ss_track.annotate.review.model import PRESENCE, Disagreement, ReviewKey, review_key
from ss_track.annotate.review.values import frame_values
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import invalid


def unknown_frames(rows: Iterable[Disagreement]) -> frozenset[tuple[str, int]]:
    """Return each instance frame that a decision left unknown in a field other than the camera."""
    return frozenset(
        (row.instance_id, row.frame_index)
        for row in rows
        if row.subject == "frame"
        and row.instance_id is not None
        and row.frame_index is not None
        and row.field != "camera_motion"
        and row.outcome == "unknown"
    )


def frozen_frames(
    instance_id: str,
    left: Instance,
    right: Instance,
    by_key: dict[ReviewKey, Disagreement],
    unknown: frozenset[tuple[str, int]],
    authority: str,
) -> list[JsonValue]:
    """Return the frames this instance keeps, in frame-index order."""
    left_map = {frame.frame_index: frame for frame in left.frames}
    right_map = {frame.frame_index: frame for frame in right.frames}
    built: list[JsonValue] = []
    for index in sorted(set(left_map) | set(right_map)):
        wiped = (instance_id, index) in unknown
        frozen = _frame(
            instance_id, index, left_map.get(index), right_map.get(index), by_key, wiped, authority
        )
        if frozen is not None:
            built.append(frozen)
    return built


def frame_document(
    instance_id: str, index: int, values: dict[str, JsonValue], authority: str
) -> dict[str, JsonValue]:
    """Return one frozen frame from settled field values."""
    return {
        "frame_index": index,
        "visibility": settled_text(values["visibility"]),
        "camera_motion": settled_text(values["camera_motion"]),
        "annotator_id": authority,
        "geometry": _geometry(f"{instance_id} frame {index}", values),
    }


def unknown_frame(index: int, camera: str, authority: str) -> dict[str, JsonValue]:
    """Return a frame whose location was not settled."""
    return {
        "frame_index": index,
        "visibility": "unknown",
        "camera_motion": camera,
        "annotator_id": authority,
        "geometry": {"kind": "unlocalizable"},
    }


def settled_value(left: JsonValue, right: JsonValue, row: Disagreement | None) -> JsonValue:
    """Return the left value, including when the outcome is unknown or there is no row."""
    if row is None or row.outcome in ("left", "unknown"):
        return left
    if row.outcome == "right":
        return right
    raise TypeError(f"outcome {row.outcome} is not a settlement")


def settled_text(value: JsonValue) -> str:
    """Return a settled string."""
    if not isinstance(value, str):
        raise TypeError("settled text is not a string")
    return value


def _frame(
    instance_id: str,
    index: int,
    left: LabeledFrame | None,
    right: LabeledFrame | None,
    by_key: dict[ReviewKey, Disagreement],
    wiped: bool,
    authority: str,
) -> dict[str, JsonValue] | None:
    if left is None or right is None:
        presence = by_key[review_key("frame", instance_id, index, None, PRESENCE)]
        return _one_frame(presence, left, right, authority)
    if wiped:
        return unknown_frame(index, _camera(instance_id, index, left, right, by_key), authority)
    chosen = _chosen_frame(instance_id, index, left, right, by_key)
    return frame_document(instance_id, index, chosen, authority)


def _one_frame(
    presence: Disagreement,
    left: LabeledFrame | None,
    right: LabeledFrame | None,
    authority: str,
) -> dict[str, JsonValue] | None:
    if presence.instance_id is None:
        raise TypeError("frame presence has no instance")
    if presence.outcome == "unknown":
        source = left if left is not None else right
        if source is None:
            raise TypeError("a presence disagreement has no frame")
        return unknown_frame(source.frame_index, "unknown", authority)
    source = left if presence.outcome == "left" else right
    if source is None:
        return None
    return frame_document(presence.instance_id, source.frame_index, frame_values(source), authority)


def _chosen_frame(
    instance_id: str,
    index: int,
    left: LabeledFrame,
    right: LabeledFrame,
    by_key: dict[ReviewKey, Disagreement],
) -> dict[str, JsonValue]:
    left_values = frame_values(left)
    right_values = frame_values(right)
    chosen: dict[str, JsonValue] = {}
    for field, left_value in left_values.items():
        row = by_key.get(review_key("frame", instance_id, index, None, field))
        if field == "camera_motion" and row is not None and row.outcome == "unknown":
            chosen[field] = "unknown"
            continue
        chosen[field] = settled_value(left_value, right_values[field], row)
    return chosen


def _camera(
    instance_id: str,
    index: int,
    left: LabeledFrame,
    right: LabeledFrame,
    by_key: dict[ReviewKey, Disagreement],
) -> str:
    row = by_key.get(review_key("frame", instance_id, index, None, "camera_motion"))
    if row is None:
        return left.camera_motion
    if row.outcome == "unknown":
        return "unknown"
    return left.camera_motion if row.outcome == "left" else right.camera_motion


def _geometry(where: str, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    kind = settled_text(values["geometry.kind"])
    if kind == "unlocalizable":
        return {"kind": "unlocalizable"}
    if kind == "box":
        return _box_geometry(where, values)
    if kind == "point_only":
        return _point_geometry(where, values)
    raise invalid(f"{where} geometry {kind} is not a label geometry")


def _box_geometry(where: str, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    box = values["geometry.box"]
    amodal = values["geometry.amodal_box"]
    uncertainty = values["geometry.uncertainty_px"]
    if not isinstance(box, dict) or not _number(uncertainty):
        raise invalid(f"{where} box settlement has no box")
    if amodal is not None and not isinstance(amodal, dict):
        raise invalid(f"{where} amodal settlement is not a box")
    return {
        "kind": "box",
        "box": box,
        "amodal_box": amodal,
        "uncertainty_px": uncertainty,
        "plausible_extent_px": None,
    }


def _point_geometry(where: str, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    point = values["geometry.point"]
    uncertainty = values["geometry.uncertainty_px"]
    extent = values["geometry.plausible_extent_px"]
    if not isinstance(point, dict) or not _number(uncertainty):
        raise invalid(f"{where} point settlement has no point")
    if extent is not None and not isinstance(extent, int):
        raise invalid(f"{where} point settlement has no extent")
    return {
        "kind": "point_only",
        "point": point,
        "uncertainty_px": uncertainty,
        "plausible_extent_px": extent,
    }


def _number(value: JsonValue) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
