"""Apply one `track_status` entry to the frame it names.

`unknown` stays unknown and is never absent. A shift frame is out of view. The
target returns once, so the first re-entry frame records re-entry and the later
ones only keep their box. A region names the painted rectangle. On a distractor
frame that rectangle is the copy, and the target box stays.
"""

from collections.abc import Mapping
from dataclasses import replace

from ss_track.annotate.derivation.edit import (
    add_instance,
    frame_at,
    mark_reentry,
    put_frame,
    reconcile_events,
    wipe,
)
from ss_track.annotate.derivation.fields import integer, rect, text
from ss_track.annotate.derivation.geom import Rect, from_box, unlocalizable
from ss_track.annotate.derivation.status import apply_region, translate_frame
from ss_track.annotate.labels.model import Instance, LabeledFrame, LabelSet
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.corpus.declarations.fields import invalid

_TARGET_STAYS = "distractor"


def apply_track(
    labels: LabelSet, frames: list[Mapping[str, object]], instance_id: str, pack: ScenarioPack
) -> LabelSet:
    """Apply each role, then record the one re-entry after the other edits."""
    reentries: list[int] = []
    copies: list[tuple[int, Rect]] = []
    for entry in frames:
        role = text(entry, "role")
        index = _index(entry)
        if role == "reentry":
            reentries.append(index)
        if role == "region" and entry.get("added_objects") == _TARGET_STAYS:
            copies.append((index, _region_of(entry)))
        labels = _role(labels, entry, role, instance_id)
    if copies:
        labels = add_instance(labels, _copy(labels, instance_id, copies, pack))
    labels = reconcile_events(labels)
    if reentries:
        labels = mark_reentry(labels, instance_id, min(reentries))
    return labels


def _role(labels: LabelSet, entry: Mapping[str, object], role: str, instance_id: str) -> LabelSet:
    index = _index(entry)
    frame = frame_at(labels, instance_id, index)
    if role == "unknown":
        return _unknown(labels, instance_id, index, frame)
    if frame is None:
        raise invalid(f"{instance_id} frame {index} has no label for role {role}")
    if role == "unchanged":
        _require_box(frame, _region_of(entry), index)
        return labels
    if role == "shift":
        return _shift(labels, entry, instance_id, frame)
    if role == "reentry":
        _require_box(frame, _region_of(entry), index)
        return labels
    if role == "region":
        return _region(labels, entry, instance_id, index)
    raise invalid(f"track role {role} is not a stored role")


def _unknown(
    labels: LabelSet, instance_id: str, index: int, frame: LabeledFrame | None
) -> LabelSet:
    if frame is None:
        donor = _donor(labels, instance_id)
        frame = LabeledFrame(index, "unknown", "unknown", donor.annotator_id, unlocalizable())
    else:
        frame = wipe(frame, "unknown")
    return put_frame(labels, instance_id, frame)


def _shift(
    labels: LabelSet, entry: Mapping[str, object], instance_id: str, target: LabeledFrame
) -> LabelSet:
    dx, dy = integer(entry.get("dx"), "dx"), integer(entry.get("dy"), "dy")
    width, height = labels.space.width, labels.space.height
    for instance in labels.instances:
        frame = next(
            (item for item in instance.frames if item.frame_index == target.frame_index), None
        )
        if frame is None:
            continue
        moved = translate_frame(frame, dx, dy, width, height)
        if instance.instance_id == instance_id:
            moved = wipe(moved, "out_of_view")
        labels = put_frame(labels, instance.instance_id, moved)
    return labels


def _region(
    labels: LabelSet, entry: Mapping[str, object], instance_id: str, index: int
) -> LabelSet:
    region = _region_of(entry)
    inside, overlap = text(entry, "inside"), text(entry, "overlap")
    keep_target = entry.get("added_objects") == _TARGET_STAYS
    for instance in labels.instances:
        if keep_target and instance.instance_id == instance_id:
            continue
        frame = next((item for item in instance.frames if item.frame_index == index), None)
        if frame is None:
            continue
        labels = put_frame(
            labels, instance.instance_id, apply_region(frame, region, inside, overlap)
        )
    return labels


def _copy(
    labels: LabelSet, instance_id: str, copies: list[tuple[int, Rect]], pack: ScenarioPack
) -> Instance:
    class_id = _distractor_class(pack)
    frames = []
    for index, region in copies:
        source = frame_at(labels, instance_id, index)
        if source is None or source.geometry.box is None or source.geometry.uncertainty_px is None:
            raise invalid(f"{instance_id} frame {index} has no box to copy")
        geometry = replace(
            source.geometry,
            box=replace(
                source.geometry.box,
                x=region.x,
                y=region.y,
                width=region.width,
                height=region.height,
            ),
            amodal_box=None,
        )
        frames.append(replace(source, geometry=geometry))
    return Instance(f"copy-{instance_id}", class_id, "reviewed", "distractor", tuple(frames))


def _distractor_class(pack: ScenarioPack) -> str:
    found = pack.distractor_class_ids()
    if len(found) != 1:
        raise invalid("the pack must name one distractor class for a copied box")
    return found[0]


def _require_box(frame: LabeledFrame, region: Rect, index: int) -> None:
    box = frame.geometry.box
    if box is None or from_box(box) != region:
        raise invalid(f"frame {index} box does not match the track status")


def _donor(labels: LabelSet, instance_id: str) -> LabeledFrame:
    instance = next((item for item in labels.instances if item.instance_id == instance_id), None)
    if instance is None or not instance.frames:
        raise invalid(f"{instance_id} is not in the parent's frozen revision")
    return instance.frames[0]


def _region_of(entry: Mapping[str, object]) -> Rect:
    return rect(entry.get("region"), "track frame region")


def _index(entry: Mapping[str, object]) -> int:
    return integer(entry.get("frame_index"), "frame_index")
