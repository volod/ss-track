"""Read a review plan and a settlement. The schemas hold structure; these hold the rules."""

from pathlib import Path

from ss_track.annotate.digest import as_document, declaration_hash
from ss_track.annotate.review_model import Decision, ReviewPlan, Settlement
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.schema.validation.enforce import read_declaration

REVIEW_CONTRACT = "declaration/annotation-review"
SETTLEMENT_CONTRACT = "declaration/annotation-settlement"
_MAJOR = 1


def read_review(path: Path) -> ReviewPlan:
    """Return the review plan. An entire review lists no sample frames."""
    document = read_declaration(path, REVIEW_CONTRACT, _MAJOR)
    fields = Fields(document, path.name)
    items = _items(fields)
    coverage = fields.string("coverage")
    if coverage == "entire" and items:
        raise invalid("an entire review lists no sample")
    return ReviewPlan(
        fields.string("review_id"),
        fields.string("authority"),
        coverage,
        items,
        declaration_hash(as_document(document)),
    )


def read_settlement(path: Path) -> Settlement:
    """Return the settlement. A rationale is not blank."""
    document = read_declaration(path, SETTLEMENT_CONTRACT, _MAJOR)
    fields = Fields(document, path.name)
    return Settlement(
        fields.string("settlement_id"),
        fields.string("revision_id"),
        fields.string("authority"),
        tuple(_decision(Fields(item, path.name)) for item in fields.items("decisions")),
        declaration_hash(as_document(document)),
    )


def _items(fields: Fields) -> tuple[tuple[str, int], ...]:
    items: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for raw in fields.items("items"):
        item = Fields(raw, fields.where)
        pair = (item.string("instance_id"), item.index("frame_index"))
        if pair in seen:
            raise invalid(f"duplicate sample frame {pair[0]} {pair[1]}")
        seen.add(pair)
        items.append(pair)
    return tuple(items)


def _decision(fields: Fields) -> Decision:
    subject = fields.string("subject")
    instance_id = fields.string("instance_id") if fields.has("instance_id") else None
    frame_index = fields.index("frame_index") if fields.has("frame_index") else None
    event_id = fields.string("event_id") if fields.has("event_id") else None
    return Decision(
        subject,
        instance_id,
        frame_index,
        event_id,
        fields.string("field"),
        fields.string("outcome"),
        fields.text("rationale"),
    )
