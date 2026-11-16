"""Motion events on a frozen revision.

An unknown value other than selection quality leaves the event out. Unknown selection
quality keeps the event and marks it uncertain. Visibility then follows the frozen
frame, and a re-entry on a frame that is not visible is cleared. Either of those
changes marks the selection uncertain, because the event is no longer the reviewed onset.
"""

from ss_track.annotate.labels.events import UNCERTAIN, EventState, follow_frame
from ss_track.annotate.labels.model import LabelSet, MotionEvent
from ss_track.annotate.review.model import PRESENCE, Disagreement, ReviewKey, review_key
from ss_track.annotate.review.values import event_values
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import invalid


def frozen_events(
    left: LabelSet,
    right: LabelSet,
    rows: tuple[Disagreement, ...],
    frames: dict[tuple[str, int], dict[str, JsonValue]],
) -> list[JsonValue]:
    """Return the events the freeze keeps, in event-id order."""
    by_key = {row.key: row for row in rows}
    dropped = _dropped_events(rows)
    left_map = {item.event_id: item for item in left.motion_events}
    right_map = {item.event_id: item for item in right.motion_events}
    built: list[JsonValue] = []
    for event_id in sorted(set(left_map) | set(right_map)):
        if event_id in dropped:
            continue
        built.append(
            _event(event_id, left_map.get(event_id), right_map.get(event_id), by_key, frames)
        )
    return built


def _event(
    event_id: str,
    left: MotionEvent | None,
    right: MotionEvent | None,
    by_key: dict[ReviewKey, Disagreement],
    frames: dict[tuple[str, int], dict[str, JsonValue]],
) -> dict[str, JsonValue]:
    if left is None or right is None:
        source = left if left is not None else right
        if source is None:
            raise TypeError(f"event {event_id} has no side")
        body = event_values(source)
    else:
        body = _merged(event_id, left, right, by_key)
    aligned = _align(event_id, body, frames)
    if aligned is None:
        raise invalid(f"event {event_id} has no frozen frame")
    return aligned


def _dropped_events(rows: tuple[Disagreement, ...]) -> frozenset[str]:
    """Return each event a decision leaves out: an unknown field, or a presence that omits it."""
    return frozenset(
        row.event_id
        for row in rows
        if row.subject == "event"
        and row.event_id is not None
        and (
            (row.field != "selection_quality" and row.outcome == "unknown")
            or (row.field == PRESENCE and _omits(row))
        )
    )


def _omits(row: Disagreement) -> bool:
    if row.outcome == "left":
        return row.left == "false"
    if row.outcome == "right":
        return row.right == "false"
    return False


def _merged(
    event_id: str, left: MotionEvent, right: MotionEvent, by_key: dict[ReviewKey, Disagreement]
) -> dict[str, JsonValue]:
    left_values = event_values(left)
    right_values = event_values(right)
    merged: dict[str, JsonValue] = {}
    uncertain = False
    for field, left_value in left_values.items():
        row = by_key.get(review_key("event", None, None, event_id, field))
        if row is not None and row.outcome == "unknown":
            uncertain = True
            merged[field] = left_value
            continue
        merged[field] = (
            right_values[field] if row is not None and row.outcome == "right" else left_value
        )
    if uncertain:
        merged["selection_quality"] = UNCERTAIN
    return {"event_id": event_id, **merged}


def _align(
    event_id: str,
    body: dict[str, JsonValue],
    frames: dict[tuple[str, int], dict[str, JsonValue]],
) -> dict[str, JsonValue] | None:
    instance_id = body["instance_id"]
    onset = body["onset_frame"]
    if not isinstance(instance_id, str) or isinstance(onset, bool) or not isinstance(onset, int):
        raise TypeError(f"event {event_id} locator is not the contract type")
    frame = frames.get((instance_id, onset))
    if frame is None:
        return None
    visibility = frame["visibility"]
    if not isinstance(visibility, str):
        raise TypeError(f"event {event_id} frame visibility is not a string")
    aligned = dict(body)
    aligned["event_id"] = event_id
    quality = body["selection_quality"]
    if not isinstance(quality, str):
        raise TypeError(f"event {event_id} selection quality is not a string")
    stated = EventState(str(body["visibility"]), body["reentry"] is True, quality)
    followed = follow_frame(stated, visibility)
    aligned["visibility"] = followed.visibility
    aligned["reentry"] = followed.reentry
    aligned["selection_quality"] = followed.selection_quality
    return aligned
