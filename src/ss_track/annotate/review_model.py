"""A disagreement between two label documents, and the review that settles it.

A value is canonical JSON, so a hand-built disagreement is one string on each side.
The annotator id and the label id are not values here.
"""

import json
from dataclasses import dataclass

from ss_track.core.refusal import JsonValue

ReviewKey = tuple[str, str, int | None, str, str]
PRESENCE = "presence"


def review_key(
    subject: str,
    instance_id: str | None,
    frame_index: int | None,
    event_id: str | None,
    field: str,
) -> ReviewKey:
    """Return the identity of one disagreement. Missing locators stay empty."""
    return (subject, instance_id or "", frame_index, event_id or "", field)


def canonical_value(value: JsonValue) -> str:
    """Return one JSON encoding. Object keys are sorted. A null value is ``null``."""
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True
    )


@dataclass(frozen=True, slots=True)
class Disagreement:
    """One field that differs. ``left`` and ``right`` are canonical JSON."""

    subject: str
    instance_id: str | None
    frame_index: int | None
    event_id: str | None
    field: str
    left: str
    right: str
    difficult: bool = False
    obligation: str = "required"
    outcome: str = "unresolved"
    rationale: str | None = None

    @property
    def key(self) -> ReviewKey:
        """Return the identity a settlement decision must match."""
        return review_key(
            self.subject, self.instance_id, self.frame_index, self.event_id, self.field
        )

    def with_review(
        self, *, difficult: bool, obligation: str, outcome: str, rationale: str | None
    ) -> "Disagreement":
        """Return this row with the review's obligation and outcome."""
        return Disagreement(
            self.subject,
            self.instance_id,
            self.frame_index,
            self.event_id,
            self.field,
            self.left,
            self.right,
            difficult,
            obligation,
            outcome,
            rationale,
        )

    def to_record(self) -> dict[str, JsonValue]:
        """Return this row. A compare leaves the outcome unresolved and the rationale null."""
        return {
            "subject": self.subject,
            "instance_id": self.instance_id,
            "frame_index": self.frame_index,
            "event_id": self.event_id,
            "field": self.field,
            "left": self.left,
            "right": self.right,
            "difficult": self.difficult,
            "obligation": self.obligation,
            "outcome": self.outcome,
            "rationale": self.rationale,
        }


def where(row: Disagreement) -> str:
    """Return a short place for a refusal: subject, locator and field."""
    if row.subject == "frame":
        return f"frame {row.instance_id} {row.frame_index} {row.field}"
    if row.subject == "instance":
        return f"instance {row.instance_id} {row.field}"
    return f"event {row.event_id} {row.field}"


@dataclass(frozen=True, slots=True)
class Reviewer:
    """One side of the comparison and the annotator ids on that document."""

    side: str
    label_sha256: str
    annotator_ids: tuple[str, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return this side. The annotator ids are sorted."""
        return {
            "side": self.side,
            "label_sha256": self.label_sha256,
            "annotator_ids": list(self.annotator_ids),
        }


@dataclass(frozen=True, slots=True)
class ReviewPlan:
    """The declared review: the whole document, or a sample plus difficult cases."""

    review_id: str
    authority: str
    coverage: str
    items: tuple[tuple[str, int], ...]
    document_sha256: str


@dataclass(frozen=True, slots=True)
class Decision:
    """One settlement. The rationale is the recorded reason, including for unknown."""

    subject: str
    instance_id: str | None
    frame_index: int | None
    event_id: str | None
    field: str
    outcome: str
    rationale: str

    @property
    def key(self) -> ReviewKey:
        """Return the disagreement this decision names."""
        return review_key(
            self.subject, self.instance_id, self.frame_index, self.event_id, self.field
        )


def decision_where(decision: Decision) -> str:
    """Return the same place ``where`` uses, for a decision that may match no row."""
    if decision.subject == "frame":
        return f"frame {decision.instance_id} {decision.frame_index} {decision.field}"
    if decision.subject == "instance":
        return f"instance {decision.instance_id} {decision.field}"
    return f"event {decision.event_id} {decision.field}"


@dataclass(frozen=True, slots=True)
class Settlement:
    """The decisions that freeze one revision."""

    settlement_id: str
    revision_id: str
    authority: str
    decisions: tuple[Decision, ...]
    document_sha256: str
