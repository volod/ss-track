"""Apply one stored label transform to a parent's frozen labels.

The label id becomes the case id. Nothing here writes a file or reads a revision.
`compression` and `timing` do not move geometry. `timing`, and a repeated frame,
record that presentation time is derived.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from ss_track.annotate.derivation.edit import (
    copy_frame,
    drop_frame,
    map_frames,
    reconcile_events,
    require_instances,
)
from ss_track.annotate.derivation.fields import integer, integers, rect, rows, text, window
from ss_track.annotate.derivation.geom import output_size
from ss_track.annotate.derivation.status import apply_region, scale_frame, translate_frame
from ss_track.annotate.derivation.track import apply_track
from ss_track.annotate.labels.model import LabeledFrame, LabelSet
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.corpus.declarations.fields import invalid

_DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class Applied:
    """Labels after one transform, and a presentation claim when the case retimes frames."""

    labels: LabelSet
    timestamp_quality: str | None


def apply_label_transform(
    labels: LabelSet, transform: Mapping[str, object], pack: ScenarioPack, case_id: str
) -> Applied:
    """Return the case's labels. The caller checks plates and track boxes first."""
    renamed = replace(labels, label_id=case_id, document_sha256="")
    kind = text(transform, "kind")
    if kind in {"identity", "compression"}:
        return Applied(require_instances(renamed), None)
    if kind == "timing":
        return Applied(require_instances(renamed), _DERIVED)
    if kind == "scale":
        return _scale(renamed, transform, pack)
    if kind == "translate":
        return Applied(_translate(renamed, transform), None)
    if kind == "frame_map":
        return _frames(renamed, transform)
    if kind == "region_status":
        return Applied(_region(renamed, transform), None)
    if kind == "track_status":
        return Applied(_track(renamed, transform, pack), None)
    raise invalid(f"label transform {kind} is not a stored kind")


def _scale(labels: LabelSet, transform: Mapping[str, object], pack: ScenarioPack) -> Applied:
    factor = integer(transform.get("factor"), "factor")
    if factor < 2:
        raise invalid("scale factor is below 2")
    width, height = output_size(labels.space.width, labels.space.height, factor)
    reduced = replace(labels, space=replace(labels.space, width=width, height=height))
    scaled = map_frames(reduced, lambda frame: scale_frame(frame, factor, pack, width, height))
    return Applied(require_instances(reconcile_events(scaled)), None)


def _translate(labels: LabelSet, transform: Mapping[str, object]) -> LabelSet:
    offsets = {
        integer(item.get("frame_index"), "frame_index"): (
            integer(item.get("dx"), "dx"),
            integer(item.get("dy"), "dy"),
        )
        for item in rows(transform, "offsets")
    }
    camera = text(transform, "camera_motion")
    width, height = labels.space.width, labels.space.height

    def move(frame: LabeledFrame) -> LabeledFrame:
        shift = offsets.get(frame.frame_index)
        if shift is None:
            return frame
        moved = translate_frame(frame, shift[0], shift[1], width, height)
        return replace(moved, camera_motion=camera)

    return require_instances(reconcile_events(map_frames(labels, move)))


def _frames(labels: LabelSet, transform: Mapping[str, object]) -> Applied:
    mapped = labels
    for index in integers(transform, "removed"):
        mapped = drop_frame(mapped, index)
    for item in rows(transform, "repeated"):
        mapped = copy_frame(
            mapped,
            integer(item.get("frame_index"), "frame_index"),
            integer(item.get("content_frame_index"), "content_frame_index"),
        )
    quality = _DERIVED if rows(transform, "repeated") else None
    return Applied(require_instances(reconcile_events(mapped)), quality)


def _region(labels: LabelSet, transform: Mapping[str, object]) -> LabelSet:
    frames = window(transform, "frames")
    region = rect(transform.get("region"))
    inside, overlap = text(transform, "inside"), text(transform, "overlap")

    def paint(frame: LabeledFrame) -> LabeledFrame:
        if frame.frame_index not in frames:
            return frame
        return apply_region(frame, region, inside, overlap)

    return require_instances(reconcile_events(map_frames(labels, paint)))


def _track(labels: LabelSet, transform: Mapping[str, object], pack: ScenarioPack) -> LabelSet:
    return require_instances(
        apply_track(labels, rows(transform, "frames"), text(transform, "instance_id"), pack)
    )
