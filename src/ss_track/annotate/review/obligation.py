"""Which disagreements a review must settle.

A disagreement is difficult when one side lacks the subject, or either label marks
the instance identity as ambiguous, its mark or visibility as unknown, its geometry
as unlocalizable, or a motion-event selection as uncertain. Difficult disagreements
stay in the review when a sample leaves their frame out. Anything outside the review
stays unknown and does not block the freeze.
"""

from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.review.model import (
    PRESENCE,
    Decision,
    Disagreement,
    ReviewKey,
    ReviewPlan,
    Settlement,
)
from ss_track.corpus.declarations.fields import invalid


def apply_obligation(
    rows: tuple[Disagreement, ...], left: LabelSet, right: LabelSet, plan: ReviewPlan
) -> tuple[Disagreement, ...]:
    """Mark each row required or outside, and whether it is difficult."""
    frames = _difficult_frames(left, right)
    sample = frozenset(plan.items)
    return tuple(_mark(row, plan.coverage, sample, frames, left, right) for row in rows)


def apply_decisions(
    rows: tuple[Disagreement, ...], settlement: Settlement
) -> tuple[Disagreement, ...]:
    """Apply a settlement. A required row with no decision blocks the freeze."""
    chosen = _decisions(settlement, rows)
    missing: list[Disagreement] = []
    settled: list[Disagreement] = []
    for row in rows:
        decision = chosen.get(row.key)
        if decision is None and row.obligation == "required":
            missing.append(row)
            continue
        if decision is None:
            settled.append(_outcome(row, "unknown", None))
            continue
        settled.append(_outcome(row, decision.outcome, decision.rationale))
    if missing:
        listed = "; ".join(row.place for row in missing)
        raise invalid(f"unresolved disagreement {listed}")
    return tuple(settled)


def require_sample(plan: ReviewPlan, left: LabelSet, right: LabelSet) -> None:
    """Refuse a sample frame this source or these labels do not have."""
    known = {item.instance_id for item in left.instances}
    known.update(item.instance_id for item in right.instances)
    for instance_id, frame_index in plan.items:
        if instance_id not in known:
            raise invalid(f"sample instance {instance_id} is not in either label document")
        if frame_index >= left.space.frame_count:
            raise invalid(f"sample frame {instance_id} {frame_index} is outside the source")


def _decisions(settlement: Settlement, rows: tuple[Disagreement, ...]) -> dict[ReviewKey, Decision]:
    present = {row.key for row in rows}
    chosen: dict[ReviewKey, Decision] = {}
    for decision in settlement.decisions:
        if decision.key in chosen:
            raise invalid(f"duplicate decision {decision.place}")
        if decision.key not in present:
            raise invalid(f"decision {decision.place} is not a disagreement")
        chosen[decision.key] = decision
    return chosen


def _outcome(row: Disagreement, outcome: str, rationale: str | None) -> Disagreement:
    return row.with_review(
        difficult=row.difficult, obligation=row.obligation, outcome=outcome, rationale=rationale
    )


def _mark(
    row: Disagreement,
    coverage: str,
    sample: frozenset[tuple[str, int]],
    frames: set[tuple[str, int]],
    left: LabelSet,
    right: LabelSet,
) -> Disagreement:
    difficult = _difficult(row, frames, left, right)
    required = coverage == "entire" or difficult or _sampled(row, sample, left, right)
    obligation = "required" if required else "outside"
    return row.with_review(
        difficult=difficult, obligation=obligation, outcome=row.outcome, rationale=row.rationale
    )


def _difficult(
    row: Disagreement, frames: set[tuple[str, int]], left: LabelSet, right: LabelSet
) -> bool:
    if row.field == PRESENCE:
        return True
    if row.subject == "instance":
        return any(instance == row.instance_id for instance, _index in frames)
    if row.subject == "frame":
        return (row.instance_id, row.frame_index) in frames
    return _event_difficult(row, left, right, frames)


def _event_difficult(
    row: Disagreement, left: LabelSet, right: LabelSet, frames: set[tuple[str, int]]
) -> bool:
    for labels in (left, right):
        for event in labels.motion_events:
            if event.event_id != row.event_id:
                continue
            if event.selection_quality == "uncertain":
                return True
            if (event.instance_id, event.onset_frame) in frames:
                return True
    return False


def _sampled(
    row: Disagreement, items: frozenset[tuple[str, int]], left: LabelSet, right: LabelSet
) -> bool:
    if row.subject == "frame" and row.frame_index is not None and row.instance_id is not None:
        return (row.instance_id, row.frame_index) in items
    if row.subject == "instance" and row.instance_id is not None:
        return any(instance == row.instance_id for instance, _index in items)
    onsets = {
        (event.instance_id, event.onset_frame)
        for labels in (left, right)
        for event in labels.motion_events
        if event.event_id == row.event_id
    }
    return bool(onsets & items)


def _difficult_frames(left: LabelSet, right: LabelSet) -> set[tuple[str, int]]:
    found: set[tuple[str, int]] = set()
    for labels in (left, right):
        _add_uncertain_frames(found, labels)
        _add_uncertain_events(found, labels)
    return found


def _add_uncertain_frames(found: set[tuple[str, int]], labels: LabelSet) -> None:
    for instance in labels.instances:
        ambiguous = (
            instance.identity == "identity_ambiguous" or instance.non_scoring_mark == "unknown"
        )
        for frame in instance.frames:
            uncertain = frame.visibility == "unknown" or frame.geometry.kind == "unlocalizable"
            if ambiguous or uncertain:
                found.add((instance.instance_id, frame.frame_index))


def _add_uncertain_events(found: set[tuple[str, int]], labels: LabelSet) -> None:
    for event in labels.motion_events:
        if event.selection_quality == "uncertain":
            found.add((event.instance_id, event.onset_frame))
