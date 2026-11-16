"""Differences between two label documents of one source and one pack.

Rows are ordered by subject (instance, then frame, then event), then by id, then by
field. Presence comes before the other fields of that subject. The annotator id is
not a difference: each document keeps its own, and the sensitivity band retains both.
"""

from ss_track.annotate.labels.model import Instance, LabelSet
from ss_track.annotate.review.model import PRESENCE, Disagreement, canonical_value
from ss_track.annotate.review.values import (
    EVENT_FIELDS,
    FRAME_FIELDS,
    INSTANCE_FIELDS,
    event_values,
    frame_values,
    instance_values,
)
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import invalid

_SUBJECT_ORDER = {"instance": 0, "frame": 1, "event": 2}


def compare_label_sets(left: LabelSet, right: LabelSet) -> tuple[Disagreement, ...]:
    """Return every differing field. Equal numbers compare equal, including ``1`` and ``1.0``."""
    _require_pair(left, right)
    rows = [*_instances(left, right), *_events(left, right)]
    return tuple(sorted(rows, key=_order))


def _require_pair(left: LabelSet, right: LabelSet) -> None:
    if (left.pack_id, left.pack_hash) != (right.pack_id, right.pack_hash):
        raise invalid("the two label documents name different packs")
    if left.space != right.space:
        raise invalid("the two label documents name different sources")


def _instances(left: LabelSet, right: LabelSet) -> list[Disagreement]:
    left_map = {item.instance_id: item for item in left.instances}
    right_map = {item.instance_id: item for item in right.instances}
    rows: list[Disagreement] = []
    for instance_id in sorted(set(left_map) | set(right_map)):
        one = left_map.get(instance_id)
        other = right_map.get(instance_id)
        _presence(rows, "instance", instance_id, None, None, one is not None, other is not None)
        if one is None or other is None:
            continue
        _fields(
            rows,
            "instance",
            instance_id,
            None,
            None,
            INSTANCE_FIELDS,
            instance_values(one),
            instance_values(other),
        )
        _frames(rows, instance_id, one, other)
    return rows


def _frames(rows: list[Disagreement], instance_id: str, left: Instance, right: Instance) -> None:
    left_map = {frame.frame_index: frame for frame in left.frames}
    right_map = {frame.frame_index: frame for frame in right.frames}
    for index in sorted(set(left_map) | set(right_map)):
        one = left_map.get(index)
        other = right_map.get(index)
        _presence(rows, "frame", instance_id, index, None, one is not None, other is not None)
        if one is None or other is None:
            continue
        _fields(
            rows,
            "frame",
            instance_id,
            index,
            None,
            FRAME_FIELDS,
            frame_values(one),
            frame_values(other),
        )


def _events(left: LabelSet, right: LabelSet) -> list[Disagreement]:
    left_map = {item.event_id: item for item in left.motion_events}
    right_map = {item.event_id: item for item in right.motion_events}
    rows: list[Disagreement] = []
    for event_id in sorted(set(left_map) | set(right_map)):
        one = left_map.get(event_id)
        other = right_map.get(event_id)
        _presence(rows, "event", None, None, event_id, one is not None, other is not None)
        if one is None or other is None:
            continue
        _fields(
            rows,
            "event",
            None,
            None,
            event_id,
            EVENT_FIELDS,
            event_values(one),
            event_values(other),
        )
    return rows


def _fields(
    rows: list[Disagreement],
    subject: str,
    instance_id: str | None,
    frame_index: int | None,
    event_id: str | None,
    fields: tuple[str, ...],
    left: dict[str, JsonValue],
    right: dict[str, JsonValue],
) -> None:
    for field in fields:
        if left[field] != right[field]:
            rows.append(
                _row(subject, instance_id, frame_index, event_id, field, left[field], right[field])
            )


def _presence(
    rows: list[Disagreement],
    subject: str,
    instance_id: str | None,
    frame_index: int | None,
    event_id: str | None,
    left_has: bool,
    right_has: bool,
) -> None:
    if left_has == right_has:
        return
    rows.append(_row(subject, instance_id, frame_index, event_id, PRESENCE, left_has, right_has))


def _row(
    subject: str,
    instance_id: str | None,
    frame_index: int | None,
    event_id: str | None,
    field: str,
    left: JsonValue,
    right: JsonValue,
) -> Disagreement:
    return Disagreement(
        subject,
        instance_id,
        frame_index,
        event_id,
        field,
        canonical_value(left),
        canonical_value(right),
    )


def _order(row: Disagreement) -> tuple[int, str, int, str, int, str]:
    index = -1 if row.frame_index is None else row.frame_index
    presence = 0 if row.field == PRESENCE else 1
    return (
        _SUBJECT_ORDER[row.subject],
        row.instance_id or "",
        index,
        row.event_id or "",
        presence,
        row.field,
    )
