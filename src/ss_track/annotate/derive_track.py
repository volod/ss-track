"""Apply one `track_status` entry to the frame it names.

`unknown` stays unknown and is never absent. A shift frame is out of view. A
re-entry frame records re-entry. A region names the painted rectangle. On a
distractor frame that rectangle is the copy, and the target box stays.
"""

from dataclasses import replace

from ss_track.annotate.derive_edit import (
    add_instance,
    frame_at,
    mark_reentry,
    put_frame,
    reconcile_events,
    wipe,
)
from ss_track.annotate.derive_geom import Rect, from_box
from ss_track.annotate.derive_status import apply_region, translate_frame
from ss_track.annotate.label_model import Instance, LabeledFrame, LabelSet
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.corpus.declarations.fields import invalid

_TARGET_STAYS = "distractor"


def apply_track(
    labels: LabelSet,
    frames: list[dict[str, object]],
    instance_id: str,
    pack: ScenarioPack,
    width: int,
    height: int,
) -> LabelSet:
    """Apply each role, then record re-entry after the other edits."""
    reentries: list[int] = []
    copies: list[tuple[int, Rect]] = []
    for entry in frames:
        role = str(entry["role"])
        index = _index(entry)
        if role == "reentry":
            reentries.append(index)
        if role == "region" and entry.get("added_objects") == _TARGET_STAYS:
            copies.append((index, _rect(entry)))
        labels = _role(labels, entry, instance_id, width, height)
    if copies:
        labels = add_instance(labels, _copy(labels, instance_id, copies, pack))
    labels = reconcile_events(labels)
    for index in reentries:
        labels = mark_reentry(labels, instance_id, index)
    return labels


def _role(
    labels: LabelSet, entry: dict[str, object], instance_id: str, width: int, height: int
) -> LabelSet:
    role = str(entry["role"])
    index = _index(entry)
    frame = frame_at(labels, instance_id, index)
    if role == "unknown":
        return _unknown(labels, instance_id, index, frame)
    if frame is None:
        raise invalid(f"{instance_id} frame {index} has no label for role {role}")
    if role == "unchanged":
        _require_box(frame, _rect(entry), index)
        return labels
    if role == "shift":
        return _shift(labels, entry, instance_id, frame, width, height)
    if role == "reentry":
        _require_box(frame, _rect(entry), index)
        return labels
    if role == "region":
        return _region(labels, entry, instance_id, index)
    raise invalid(f"track role {role} is not a stored role")


def _unknown(
    labels: LabelSet, instance_id: str, index: int, frame: LabeledFrame | None
) -> LabelSet:
    if frame is None:
        donor = _donor(labels, instance_id)
        frame = LabeledFrame(
            index, "unknown", "unknown", donor.annotator_id, wipe(donor, "unknown").geometry
        )
    else:
        frame = wipe(frame, "unknown")
    return put_frame(labels, instance_id, frame)


def _shift(
    labels: LabelSet,
    entry: dict[str, object],
    instance_id: str,
    target: LabeledFrame,
    width: int,
    height: int,
) -> LabelSet:
    dx, dy = _int(entry.get("dx"), "dx"), _int(entry.get("dy"), "dy")
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


def _region(labels: LabelSet, entry: dict[str, object], instance_id: str, index: int) -> LabelSet:
    region = _rect(entry)
    inside, overlap = str(entry["inside"]), str(entry["overlap"])
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
    found = sorted(item.class_id for item in pack.classes if item.role == "distractor")
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


def _rect(entry: dict[str, object]) -> Rect:
    raw = entry.get("region")
    if not isinstance(raw, dict):
        raise invalid("track frame has no region")
    return Rect(
        _int(raw.get("x"), "x"),
        _int(raw.get("y"), "y"),
        _int(raw.get("width"), "width"),
        _int(raw.get("height"), "height"),
    )


def _index(entry: dict[str, object]) -> int:
    return _int(entry.get("frame_index"), "frame_index")


def _int(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid(f"{where} is not an integer")
    return value
