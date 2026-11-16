"""Rules the label schema cannot state, and the rows a mask must repeat."""

from ss_track.annotate.declarations.checks import require_unique
from ss_track.annotate.labels.disposition import VISIBLE, Disposition, frame_disposition
from ss_track.annotate.labels.geometry import require_box, require_point
from ss_track.annotate.labels.model import Instance, LabeledFrame, LabelSet, MotionEvent
from ss_track.annotate.packs.model import PackClass, ScenarioPack
from ss_track.annotate.sources.declared_space import require_space, require_stored_orientation
from ss_track.annotate.sources.frame_space import FrameSpace
from ss_track.corpus.declarations.fields import invalid

_MARKS = {
    "scoring": frozenset({None}),
    "distractor": frozenset({"distractor", "unknown"}),
    "ignore": frozenset({"ignore_region", "unknown"}),
}


def check_label_set(labels: LabelSet, pack: ScenarioPack, space: FrameSpace) -> None:
    """Refuse a label set whose pack, space, classes, geometry or events disagree."""
    _require_pack(labels, pack)
    require_space(labels.space, space, labels.label_id)
    _check_content(labels, pack)


def check_label_rules(labels: LabelSet, pack: ScenarioPack) -> None:
    """Apply every rule but the source: the pack, classes, geometry and events of one document.

    The caller joins the document to what it was drawn on, a decoded source or a corpus stream.
    """
    _require_pack(labels, pack)
    require_stored_orientation(labels.space, labels.label_id)
    _check_content(labels, pack)


def pack_class(pack: ScenarioPack, class_id: str) -> PackClass:
    """Return the class a label names, refusing an id the pinned pack does not state."""
    found = pack.class_named(class_id)
    if found is None:
        raise invalid(f"class-id: {class_id} is not in the pack")
    return found


def label_dispositions(labels: LabelSet) -> dict[tuple[str, int], Disposition]:
    """Return the status of every labeled frame, keyed by instance and frame index."""
    return {
        (instance.instance_id, frame.frame_index): _disposition(instance, frame)
        for instance in labels.instances
        for frame in instance.frames
    }


def _check_content(labels: LabelSet, pack: ScenarioPack) -> None:
    space = labels.space
    require_unique([item.instance_id for item in labels.instances], "instance id")
    by_id = {item.instance_id: item for item in labels.instances}
    for instance in labels.instances:
        _check_instance(instance, pack, space.width, space.height, space.frame_count)
    require_unique([item.event_id for item in labels.motion_events], "motion event")
    for event in labels.motion_events:
        _check_event(event, by_id)


def _require_pack(labels: LabelSet, pack: ScenarioPack) -> None:
    if labels.pack_id != pack.pack_id:
        raise invalid(f"pack_id {labels.pack_id} is not {pack.pack_id}")
    if labels.pack_hash != pack.pack_hash:
        raise invalid("pack_hash does not match the pack")


def _check_instance(
    instance: Instance, pack: ScenarioPack, width: int, height: int, frame_count: int
) -> None:
    _require_mark(pack_class(pack, instance.class_id), instance.non_scoring_mark)
    require_unique([str(frame.frame_index) for frame in instance.frames], "frame index")
    for frame in instance.frames:
        where = f"{instance.instance_id} frame {frame.frame_index}"
        if frame.frame_index >= frame_count:
            raise invalid(f"{where} is outside the source")
        _require_visible_extent(frame, where)
        _require_inside(frame, width, height, where)


def _require_mark(item: PackClass, mark: str | None) -> None:
    allowed = _MARKS.get(item.role)
    if allowed is None:
        raise TypeError(f"role {item.role} is not in the contract")
    if mark not in allowed:
        raise invalid(
            f"class-id: {item.class_id} role {item.role} cannot use mark {mark or 'absent'}"
        )


def _require_visible_extent(frame: LabeledFrame, where: str) -> None:
    if frame.visibility not in VISIBLE and frame.geometry.kind != "unlocalizable":
        raise invalid(f"{where} visibility {frame.visibility} cannot carry {frame.geometry.kind}")


def _require_inside(frame: LabeledFrame, width: int, height: int, where: str) -> None:
    geometry = frame.geometry
    if geometry.box is not None:
        require_box(geometry.box, width, height, f"{where} box")
    if geometry.amodal_box is not None:
        require_box(geometry.amodal_box, width, height, f"{where} amodal box")
    if geometry.point is not None:
        require_point(geometry.point, width, height, f"{where} point")


def _check_event(event: MotionEvent, instances: dict[str, Instance]) -> None:
    instance = instances.get(event.instance_id)
    if instance is None:
        raise invalid(f"motion event {event.event_id} names unknown instance {event.instance_id}")
    frame = next((item for item in instance.frames if item.frame_index == event.onset_frame), None)
    if frame is None:
        raise invalid(f"motion event {event.event_id} onset {event.onset_frame} has no label")
    if event.visibility != frame.visibility:
        raise invalid(
            f"motion event {event.event_id} visibility {event.visibility} "
            f"is not the frame visibility {frame.visibility}"
        )
    if event.reentry and frame.visibility not in VISIBLE:
        raise invalid(f"motion event {event.event_id} reentry requires a visible frame")


def _disposition(instance: Instance, frame: LabeledFrame) -> Disposition:
    return frame_disposition(
        identity=instance.identity,
        mark=instance.non_scoring_mark,
        visibility=frame.visibility,
        kind=frame.geometry.kind,
        plausible_extent_px=frame.geometry.plausible_extent_px,
    )
