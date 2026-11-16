"""Build the frozen label document from two label sets and a settlement.

An unknown frame is visibility ``unknown`` and geometry ``unlocalizable``. An unknown
class or identity keeps the instance unscorable. A class and a mark that the pack
cannot combine are left for the label check to refuse. The frozen annotator id is
the review authority, because the revision is the adjudication.
"""

from ss_track.annotate.declarations.contracts import SCHEMA_MAJOR
from ss_track.annotate.labels.model import Instance, LabelSet
from ss_track.annotate.labels.rules import pack_class
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.frozen_events import frozen_events
from ss_track.annotate.review.frozen_frames import (
    frame_document,
    frozen_frames,
    settled_text,
    settled_value,
    unknown_frame,
    unknown_frames,
)
from ss_track.annotate.review.model import PRESENCE, Disagreement, ReviewKey, review_key
from ss_track.annotate.review.values import frame_values, instance_values
from ss_track.annotate.sources.declared_space import STORED_ORIENTATION_DEGREES
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import invalid


def build_frozen_document(
    left: LabelSet,
    right: LabelSet,
    rows: tuple[Disagreement, ...],
    pack: ScenarioPack,
    *,
    revision_id: str,
    authority: str,
) -> dict[str, JsonValue]:
    """Return one label document. It is not yet schema-checked."""
    by_key = {row.key: row for row in rows}
    instances = _instances(left, right, by_key, unknown_frames(rows), pack, authority)
    if not instances:
        raise invalid("frozen revision has no instance")
    frames = _frame_index(instances)
    return {
        "schema_version": SCHEMA_MAJOR,
        "label_id": revision_id,
        "pack_id": left.pack_id,
        "pack_hash": left.pack_hash,
        "source_sha256": left.space.source_sha256,
        "frame_count": left.space.frame_count,
        "width": left.space.width,
        "height": left.space.height,
        "orientation_degrees": STORED_ORIENTATION_DEGREES,
        "display_rotation_degrees": left.space.display_rotation_degrees,
        "instances": instances,
        "motion_events": frozen_events(left, right, rows, frames),
    }


def _instances(
    left: LabelSet,
    right: LabelSet,
    by_key: dict[ReviewKey, Disagreement],
    unknown: frozenset[tuple[str, int]],
    pack: ScenarioPack,
    authority: str,
) -> list[JsonValue]:
    left_map = {item.instance_id: item for item in left.instances}
    right_map = {item.instance_id: item for item in right.instances}
    built: list[JsonValue] = []
    for instance_id in sorted(set(left_map) | set(right_map)):
        one = left_map.get(instance_id)
        other = right_map.get(instance_id)
        frozen = _instance(instance_id, one, other, by_key, unknown, pack, authority)
        if frozen is not None:
            built.append(frozen)
    return built


def _instance(
    instance_id: str,
    left: Instance | None,
    right: Instance | None,
    by_key: dict[ReviewKey, Disagreement],
    unknown: frozenset[tuple[str, int]],
    pack: ScenarioPack,
    authority: str,
) -> dict[str, JsonValue] | None:
    presence = by_key.get(review_key("instance", instance_id, None, None, PRESENCE))
    if presence is not None:
        return _one_sided(presence, left, right, pack, authority)
    if left is None or right is None:
        raise TypeError(f"instance {instance_id} has no presence disagreement")
    class_id, identity, mark = _fields(instance_id, left, right, by_key, pack)
    frames = frozen_frames(instance_id, left, right, by_key, unknown, authority)
    if not frames:
        raise invalid(f"instance {instance_id} has no frozen frame")
    return _instance_document(instance_id, class_id, identity, mark, frames)


def _one_sided(
    presence: Disagreement,
    left: Instance | None,
    right: Instance | None,
    pack: ScenarioPack,
    authority: str,
) -> dict[str, JsonValue] | None:
    if presence.outcome == "unknown":
        source = left if left is not None else right
        if source is None:
            raise TypeError("a presence disagreement has no instance")
        return _unknown_instance(source, pack, authority)
    source = left if presence.outcome == "left" else right
    if source is None:
        return None
    return _copy_instance(source, authority)


def _fields(
    instance_id: str,
    left: Instance,
    right: Instance,
    by_key: dict[ReviewKey, Disagreement],
    pack: ScenarioPack,
) -> tuple[str, str, str | None]:
    left_values = instance_values(left)
    right_values = instance_values(right)
    class_key = review_key("instance", instance_id, None, None, "class_id")
    identity_key = review_key("instance", instance_id, None, None, "identity")
    mark_key = review_key("instance", instance_id, None, None, "non_scoring_mark")
    class_id = settled_text(
        settled_value(left_values["class_id"], right_values["class_id"], by_key.get(class_key))
    )
    identity = settled_text(
        settled_value(left_values["identity"], right_values["identity"], by_key.get(identity_key))
    )
    mark = _mark(
        settled_value(
            left_values["non_scoring_mark"], right_values["non_scoring_mark"], by_key.get(mark_key)
        )
    )
    if _unknown(by_key, class_key):
        return left.class_id, "identity_ambiguous", _retained_mark(pack, left.class_id)
    if _unknown(by_key, identity_key):
        identity = "identity_ambiguous"
    if _unknown(by_key, mark_key):
        retained = _retained_mark(pack, class_id)
        if retained == "unknown":
            mark = "unknown"
        else:
            identity = "identity_ambiguous"
            mark = retained
    return class_id, identity, mark


def _copy_instance(instance: Instance, authority: str) -> dict[str, JsonValue]:
    frames: list[JsonValue] = [
        frame_document(instance.instance_id, frame.frame_index, frame_values(frame), authority)
        for frame in sorted(instance.frames, key=lambda item: item.frame_index)
    ]
    return _instance_document(
        instance.instance_id,
        instance.class_id,
        instance.identity,
        instance.non_scoring_mark,
        frames,
    )


def _unknown_instance(
    instance: Instance, pack: ScenarioPack, authority: str
) -> dict[str, JsonValue]:
    frames: list[JsonValue] = [
        unknown_frame(frame.frame_index, "unknown", authority)
        for frame in sorted(instance.frames, key=lambda item: item.frame_index)
    ]
    return _instance_document(
        instance.instance_id,
        instance.class_id,
        "identity_ambiguous",
        _retained_mark(pack, instance.class_id),
        frames,
    )


def _instance_document(
    instance_id: str, class_id: str, identity: str, mark: str | None, frames: list[JsonValue]
) -> dict[str, JsonValue]:
    return {
        "instance_id": instance_id,
        "class_id": class_id,
        "identity": identity,
        "non_scoring_mark": mark,
        "frames": frames,
    }


def _frame_index(instances: list[JsonValue]) -> dict[tuple[str, int], dict[str, JsonValue]]:
    found: dict[tuple[str, int], dict[str, JsonValue]] = {}
    for instance in instances:
        if not isinstance(instance, dict):
            raise TypeError("frozen instance is not an object")
        instance_id = instance["instance_id"]
        frames = instance["frames"]
        if not isinstance(instance_id, str) or not isinstance(frames, list):
            raise TypeError("frozen instance fields are not the contract types")
        for frame in frames:
            index = frame.get("frame_index") if isinstance(frame, dict) else None
            if not isinstance(frame, dict) or not isinstance(index, int):
                raise TypeError("frozen frame is not an object")
            found[(instance_id, index)] = frame
    return found


def _retained_mark(pack: ScenarioPack, class_id: str) -> str | None:
    return None if pack_class(pack, class_id).role == "scoring" else "unknown"


def _unknown(by_key: dict[ReviewKey, Disagreement], key: ReviewKey) -> bool:
    row = by_key.get(key)
    return row is not None and row.outcome == "unknown"


def _mark(value: JsonValue) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("settled mark is not a string")
    return value
