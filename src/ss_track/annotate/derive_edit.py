"""Replace one frame of a label set and drop an instance that no longer has a frame."""

from dataclasses import replace

from ss_track.annotate.label_model import (
    Instance,
    LabeledFrame,
    LabelGeometry,
    LabelSet,
    MotionEvent,
)
from ss_track.corpus.declarations.fields import invalid

_VISIBLE = frozenset({"visible", "partially_occluded"})


def frame_at(labels: LabelSet, instance_id: str, index: int) -> LabeledFrame | None:
    """Return one labeled frame, or ``None`` when that instance does not mark it."""
    instance = _instance(labels, instance_id)
    if instance is None:
        return None
    return next((frame for frame in instance.frames if frame.frame_index == index), None)


def put_frame(labels: LabelSet, instance_id: str, frame: LabeledFrame) -> LabelSet:
    """Replace or add one frame, keeping frame order by index."""
    instances = []
    for instance in labels.instances:
        if instance.instance_id != instance_id:
            instances.append(instance)
            continue
        kept = [item for item in instance.frames if item.frame_index != frame.frame_index]
        kept.append(frame)
        kept.sort(key=lambda item: item.frame_index)
        instances.append(replace(instance, frames=tuple(kept)))
    return replace(labels, instances=tuple(instances))


def drop_frame(labels: LabelSet, index: int) -> LabelSet:
    """Remove one frame from every instance, and drop an instance that then has none."""
    instances = []
    for instance in labels.instances:
        kept = tuple(frame for frame in instance.frames if frame.frame_index != index)
        if kept:
            instances.append(replace(instance, frames=kept))
    return replace(labels, instances=tuple(instances))


def copy_frame(labels: LabelSet, index: int, content: int) -> LabelSet:
    """Give `index` the labels of `content`. A content frame with no label leaves none."""
    built = drop_frame(labels, index) if _any_frame(labels, index) else labels
    additions: list[tuple[str, LabeledFrame]] = []
    for instance in labels.instances:
        source = next((frame for frame in instance.frames if frame.frame_index == content), None)
        if source is None:
            continue
        additions.append((instance.instance_id, replace(source, frame_index=index)))
    for instance_id, frame in additions:
        if _instance(built, instance_id) is None:
            continue
        built = put_frame(built, instance_id, frame)
    return built


def add_instance(labels: LabelSet, instance: Instance) -> LabelSet:
    """Append one instance. A duplicate id is a writer defect."""
    if _instance(labels, instance.instance_id) is not None:
        raise invalid(f"derived instance {instance.instance_id} already exists")
    return replace(labels, instances=(*labels.instances, instance))


def reconcile_events(labels: LabelSet) -> LabelSet:
    """Make each event follow the frame it names, and drop an event whose frame is gone."""
    kept: list[MotionEvent] = []
    for event in labels.motion_events:
        frame = frame_at(labels, event.instance_id, event.onset_frame)
        if frame is None:
            continue
        reentry = event.reentry and frame.visibility in _VISIBLE
        kept.append(replace(event, visibility=frame.visibility, reentry=reentry))
    return replace(labels, motion_events=tuple(kept))


def mark_reentry(labels: LabelSet, instance_id: str, index: int) -> LabelSet:
    """Record re-entry on the event for one frame, adding the event when the parent has none."""
    frame = frame_at(labels, instance_id, index)
    if frame is None or frame.visibility not in _VISIBLE:
        raise invalid(f"{instance_id} frame {index} cannot record re-entry")
    found = False
    events: list[MotionEvent] = []
    for event in labels.motion_events:
        if event.instance_id == instance_id and event.onset_frame == index:
            events.append(replace(event, reentry=True, visibility=frame.visibility))
            found = True
        else:
            events.append(event)
    if not found:
        events.append(
            MotionEvent(
                f"reentry-{instance_id}-{index}",
                instance_id,
                index,
                0,
                frame.visibility,
                "reviewed",
                True,
            )
        )
    return replace(labels, motion_events=tuple(events))


def wipe(frame: LabeledFrame, visibility: str) -> LabeledFrame:
    """Return the frame with no box and no point."""
    geometry = LabelGeometry("unlocalizable", None, None, None, None, None)
    return replace(frame, visibility=visibility, geometry=geometry)


def require_instances(labels: LabelSet) -> LabelSet:
    """Refuse a derivation that removed every instance."""
    if not labels.instances:
        raise invalid("derived labels have no instance")
    return labels


def _instance(labels: LabelSet, instance_id: str) -> Instance | None:
    return next((item for item in labels.instances if item.instance_id == instance_id), None)


def _any_frame(labels: LabelSet, index: int) -> bool:
    return any(
        frame.frame_index == index for instance in labels.instances for frame in instance.frames
    )
