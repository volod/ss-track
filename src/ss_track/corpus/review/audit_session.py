"""A durable, resumable blinded audit review built only from the packet a reviewer holds.

Nothing here reads the private mapping, a discovery run or a queue template, so the session cannot
show a selection, score, stream or offer reason. Every save writes a complete
`declaration/audit-review` that `discover unblind` reads, with undecided items `unreviewed`.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.core.strict_yaml import parse_unique_document
from ss_track.corpus.declarations.fields import Fields
from ss_track.corpus.review.blind_review import AuditObservation, read_audit_review
from ss_track.corpus.review.decisions import UNREVIEWED
from ss_track.corpus.review.review_terminal import SECONDS_PER_MINUTE, whole_minutes

TEMPLATE_NAME = "review.yaml"
REVIEW_NAME = "review-completed.yaml"
NOT_DECLARED = "not_declared"
_HEADER = (
    "# Blinded audit review written by `ss-track discover review-audit`.",
    "# Map it with `ss-track discover unblind --review <this file>`.",
    "# An observation is not a label. Declarations are not verifications.",
)


@dataclass(frozen=True, slots=True)
class AuditPacket:
    """The packet a reviewer holds: its audit id and item ids, in presentation order."""

    root: Path
    audit_id: str
    item_ids: tuple[str, ...]

    def pictures(self, item_id: str) -> list[Path]:
        """Return the item's pictures in display order."""
        return sorted((self.root / "items" / item_id).glob("*.png"))


@dataclass(slots=True)
class AuditDraft:
    """A review in progress. Items absent from `observations` are unreviewed."""

    reviewer: str
    independence: str
    blinding: str
    active_seconds: float
    observations: dict[str, AuditObservation] = field(default_factory=dict)

    @property
    def minutes(self) -> int:
        """Whole minutes recorded so far, rounded up so that recorded work is never zero."""
        return whole_minutes(self.active_seconds)


def _invalid(message: str, **details: str) -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.MANIFEST_INVALID, message, dict(details))


def read_packet(root: Path) -> AuditPacket:
    """Read the packet's template for its audit id and items and require each item's pictures."""
    template = root / TEMPLATE_NAME
    if not template.is_file():
        raise _invalid("the packet holds no review template", path=str(template))
    fields = Fields(parse_unique_document(template.read_bytes().decode("ascii")), template.name)
    item_ids = tuple(
        Fields(raw, template.name).text("item_id") for raw in fields.items("observations")
    )
    if len(set(item_ids)) != len(item_ids):
        raise _invalid("the packet template lists an item twice", path=str(template))
    packet = AuditPacket(root, fields.text("audit_id"), item_ids)
    for item_id in item_ids:
        if not packet.pictures(item_id):
            raise _invalid("a packet item has no pictures", item_id=item_id)
    return packet


def load_draft(
    packet: AuditPacket,
    review: Path,
    reviewer: str,
    independence: str | None,
    blinding: str | None,
) -> AuditDraft:
    """Resume a saved review of this packet by the same reviewer, or start an empty one."""
    if not reviewer.strip() or not reviewer.isascii():
        raise _invalid("reviewer must be nonempty ASCII")
    if review.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "the review file is a symbolic link")
    if not review.exists():
        return AuditDraft(reviewer, independence or NOT_DECLARED, blinding or NOT_DECLARED, 0.0)
    saved = read_audit_review(review)
    if saved.audit_id != packet.audit_id or set(saved.observations) != set(packet.item_ids):
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT, "the review file belongs to another audit packet"
        )
    if saved.reviewer != reviewer:
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "the review file names another reviewer")
    decided = {
        item_id: observation
        for item_id, observation in saved.observations.items()
        if observation.decision != UNREVIEWED
    }
    return AuditDraft(
        reviewer,
        independence or saved.independence,
        blinding or saved.blinding,
        float(saved.reviewer_minutes * SECONDS_PER_MINUTE),
        decided,
    )


def _entry(item_id: str, observation: AuditObservation | None) -> dict[str, str]:
    if observation is None:
        return {"item_id": item_id, "decision": UNREVIEWED}
    entry = {
        "item_id": item_id,
        "decision": observation.decision,
        "observation": str(observation.observation),
    }
    if observation.reason is not None:
        entry["reason"] = observation.reason
    if observation.note is not None:
        entry["note"] = observation.note
    return entry


def review_text(packet: AuditPacket, draft: AuditDraft) -> str:
    """Return the complete review document, every packet item in presentation order."""
    document = {
        "schema_version": 1,
        "audit_id": packet.audit_id,
        "reviewer": draft.reviewer,
        "independence": draft.independence,
        "blinding": draft.blinding,
        "reviewer_minutes": draft.minutes,
        "observations": [
            _entry(item_id, draft.observations.get(item_id)) for item_id in packet.item_ids
        ],
    }
    body = yaml.safe_dump(document, sort_keys=False, allow_unicode=False)
    return "\n".join(_HEADER) + "\n" + body


def save_draft(packet: AuditPacket, review: Path, draft: AuditDraft) -> None:
    """Atomically replace the review, which stays a valid declaration at every save."""
    if review.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "the review file is a symbolic link")
    review.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(review, review_text(packet, draft).encode("ascii"))
