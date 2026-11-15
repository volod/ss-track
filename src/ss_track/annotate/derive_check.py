"""Refuse a plate that still shows a target, or a track that is not the frozen one.

The plate check reads the parent's labels at `plate_frame`. A target the rectangle
does not fully cover is not a refusal: the transform leaves that frame `unknown`.
`label_revision` is the seal of the parent's annotation revision.
"""

from collections.abc import Mapping

from ss_track.annotate.derive_edit import frame_at
from ss_track.annotate.derive_geom import Rect, from_box
from ss_track.annotate.label_model import LabelSet
from ss_track.corpus.declarations.fields import invalid


def require_case_labels(labels: LabelSet, case: Mapping[str, object], revision_sha256: str) -> None:
    """Check the plate and, for a track case, the revision and the boxes."""
    case_id = _text(case, "case_id")
    _require_plate(labels, case, case_id)
    _require_track(labels, case, revision_sha256, case_id)


def _require_plate(labels: LabelSet, case: Mapping[str, object], case_id: str) -> None:
    parameters = _object(case.get("parameters"), "parameters")
    if "plate_frame" not in parameters:
        return
    plate = _int(parameters.get("plate_frame"), "plate_frame")
    for region in _plate_regions(_object(case.get("label_transform"), "label_transform")):
        if _shows_target(labels, plate, region):
            raise invalid(
                f"generated case {case_id}: plate frame {plate} shows a target inside the region"
            )


def _require_track(
    labels: LabelSet, case: Mapping[str, object], revision_sha256: str, case_id: str
) -> None:
    transform = _object(case.get("label_transform"), "label_transform")
    if transform.get("kind") != "track_status":
        return
    if transform.get("label_revision") != revision_sha256:
        raise invalid(
            f"generated case {case_id}: label_revision does not match the parent's frozen revision"
        )
    instance_id = _text(transform, "instance_id")
    claimed = _claimed(_object(case.get("parameters"), "parameters"))
    for index, box in claimed.items():
        if not _same_box(labels, instance_id, index, box):
            raise invalid(
                f"generated case {case_id}: track box does not match the parent's frozen revision"
            )
    start, stop = _window(case)
    for index in range(start, stop):
        if index in claimed:
            continue
        frame = frame_at(labels, instance_id, index)
        if frame is not None and frame.geometry.box is not None:
            raise invalid(
                f"generated case {case_id}: track box does not match the parent's frozen revision"
            )


def _plate_regions(transform: Mapping[str, object]) -> list[Rect]:
    if transform.get("kind") == "region_status":
        return [_rect(transform.get("region"))]
    if transform.get("kind") != "track_status":
        return []
    frames = transform.get("frames")
    if not isinstance(frames, list):
        raise invalid("track status has no frames")
    regions = []
    for entry in frames:
        if isinstance(entry, Mapping) and entry.get("role") == "region":
            regions.append(_rect(entry.get("region")))
    return regions


def _shows_target(labels: LabelSet, plate: int, region: Rect) -> bool:
    for instance in labels.instances:
        if instance.non_scoring_mark is not None:
            continue
        frame = frame_at(labels, instance.instance_id, plate)
        if frame is None:
            continue
        box = frame.geometry.box
        if box is not None and region.contains(from_box(box)):
            return True
        point = frame.geometry.point
        if point is not None and region.contains_point(point.x, point.y):
            return True
    return False


def _claimed(parameters: Mapping[str, object]) -> dict[int, Rect]:
    raw = parameters.get("track")
    if not isinstance(raw, list):
        raise invalid("track case has no track")
    claimed = {}
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise invalid("track entry is not an object")
        claimed[_int(entry.get("frame_index"), "frame_index")] = _rect(entry.get("box"))
    return claimed


def _same_box(labels: LabelSet, instance_id: str, index: int, box: Rect) -> bool:
    frame = frame_at(labels, instance_id, index)
    if frame is None or frame.geometry.box is None:
        return False
    return from_box(frame.geometry.box) == box


def _window(case: Mapping[str, object]) -> tuple[int, int]:
    raw = case.get("window")
    if not isinstance(raw, Mapping):
        raise invalid("generated case has no window")
    return _int(raw.get("start_frame"), "start_frame"), _int(raw.get("end_frame"), "end_frame")


def _rect(value: object) -> Rect:
    if not isinstance(value, Mapping):
        raise invalid("region is not a rectangle")
    return Rect(
        _int(value.get("x"), "x"),
        _int(value.get("y"), "y"),
        _int(value.get("width"), "width"),
        _int(value.get("height"), "height"),
    )


def _object(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise invalid(f"{where} is not an object")
    return value


def _text(value: Mapping[str, object], name: str) -> str:
    found = value.get(name)
    if not isinstance(found, str) or not found:
        raise invalid(f"{name} is not text")
    return found


def _int(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid(f"{where} is not an integer")
    return value
