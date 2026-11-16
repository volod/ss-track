"""Refuse a plate that still shows a target, or a track that is not the frozen one.

The plate check reads the parent's labels at `plate_frame`. Any part of a scoring
target inside a painted region is a refusal, because the plate's pixels are copied
there. `label_revision` is the seal of the parent's annotation revision.
"""

from collections.abc import Mapping

from ss_track.annotate.derivation.edit import frame_at
from ss_track.annotate.derivation.fields import integer, mapping, rect, text, window
from ss_track.annotate.derivation.geom import Rect, from_box
from ss_track.annotate.labels.disposition import WITHHELD
from ss_track.annotate.labels.model import LabeledFrame, LabelSet
from ss_track.corpus.declarations.fields import invalid


def require_case_labels(labels: LabelSet, case: Mapping[str, object], revision_sha256: str) -> None:
    """Check the plate and, for a track case, the revision and the boxes."""
    case_id = text(case, "case_id")
    _require_plate(labels, case, case_id)
    _require_track(labels, case, revision_sha256, case_id)


def _require_plate(labels: LabelSet, case: Mapping[str, object], case_id: str) -> None:
    """Refuse a plate frame that shows, or may show, a target where a region copies it.

    The plate's pixels are painted into every region, so any part of a target inside one puts
    target pixels on a frame the case then calls absent. A target whose location on the plate
    frame is unknown cannot be shown to lie outside.
    """
    parameters = mapping(case.get("parameters"), "parameters")
    if "plate_frame" not in parameters:
        return
    plate = integer(parameters.get("plate_frame"), "plate_frame")
    regions = _plate_regions(mapping(case.get("label_transform"), "label_transform"))
    for frame in _plate_targets(labels, plate):
        if frame.geometry.kind == "unlocalizable" and frame.visibility not in WITHHELD:
            raise invalid(
                f"generated case {case_id}: plate frame {plate} has a target of unknown location"
            )
        if any(_meets(frame, region) for region in regions):
            raise invalid(
                f"generated case {case_id}: plate frame {plate} shows a target inside the region"
            )


def _require_track(
    labels: LabelSet, case: Mapping[str, object], revision_sha256: str, case_id: str
) -> None:
    transform = mapping(case.get("label_transform"), "label_transform")
    if transform.get("kind") != "track_status":
        return
    if transform.get("label_revision") != revision_sha256:
        raise invalid(
            f"generated case {case_id}: label_revision does not match the parent's frozen revision"
        )
    instance_id = text(transform, "instance_id")
    claimed = _claimed(mapping(case.get("parameters"), "parameters"))
    for index, box in claimed.items():
        if not _same_box(labels, instance_id, index, box):
            raise invalid(
                f"generated case {case_id}: track box does not match the parent's frozen revision"
            )
    for index in window(case, "window"):
        if index in claimed:
            continue
        frame = frame_at(labels, instance_id, index)
        if frame is not None and frame.geometry.box is not None:
            raise invalid(
                f"generated case {case_id}: track box does not match the parent's frozen revision"
            )


def _plate_regions(transform: Mapping[str, object]) -> list[Rect]:
    if transform.get("kind") == "region_status":
        return [rect(transform.get("region"))]
    if transform.get("kind") != "track_status":
        return []
    frames = transform.get("frames")
    if not isinstance(frames, list):
        raise invalid("track status has no frames")
    regions = []
    for entry in frames:
        if isinstance(entry, Mapping) and entry.get("role") == "region":
            regions.append(rect(entry.get("region")))
    return regions


def _plate_targets(labels: LabelSet, plate: int) -> list[LabeledFrame]:
    """Return what each scoring instance states on the plate frame."""
    found = []
    for instance in labels.instances:
        if instance.non_scoring_mark is not None:
            continue
        frame = frame_at(labels, instance.instance_id, plate)
        if frame is not None:
            found.append(frame)
    return found


def _meets(frame: LabeledFrame, region: Rect) -> bool:
    box = frame.geometry.box
    if box is not None:
        return region.intersects(from_box(box))
    point = frame.geometry.point
    return point is not None and region.contains_point(point.x, point.y)


def _claimed(parameters: Mapping[str, object]) -> dict[int, Rect]:
    raw = parameters.get("track")
    if not isinstance(raw, list):
        raise invalid("track case has no track")
    claimed = {}
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise invalid("track entry is not an object")
        claimed[integer(entry.get("frame_index"), "frame_index")] = rect(entry.get("box"))
    return claimed


def _same_box(labels: LabelSet, instance_id: str, index: int, box: Rect) -> bool:
    frame = frame_at(labels, instance_id, index)
    if frame is None or frame.geometry.box is None:
        return False
    return from_box(frame.geometry.box) == box
