"""Read a reviewer's decisions on a blinded audit sample.

Decisions name item ids, never a stream, a candidate, a score or a source. Independence and
blinding are the reviewer's declaration. Reading them does not verify that the procedure was
followed, and an observation is not a label.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.corpus.review.decisions import (
    EXCLUDE,
    OTHER_REASON,
    REVIEW_CONTRACT,
    REVIEW_SCHEMA_VERSION,
    UNREVIEWED,
)
from ss_track.schema.validation.enforce import (
    installed_contracts,
    read_declaration,
    require_conforming,
)

AUDIT_REVIEW_CONTRACT = "declaration/audit-review"
AUDIT_REVIEW_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class AuditObservation:
    """One decision on one blinded item."""

    item_id: str
    decision: str
    observation: str | None = None
    reason: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class AuditReview:
    """A completed blinded review: who decided, what they declared, and the effort they recorded."""

    audit_id: str
    reviewer: str
    independence: str
    blinding: str
    reviewer_minutes: int
    observations: dict[str, AuditObservation]
    review_sha256: str


def _observation(raw: object, where: str) -> AuditObservation:
    entry = Fields(raw, where)
    decision = entry.text("decision")
    if decision == UNREVIEWED:
        return AuditObservation(entry.text("item_id"), decision)
    reason = entry.text("reason") if decision == EXCLUDE else None
    note = entry.optional_text("note")
    if reason == OTHER_REASON and note is None:
        raise invalid(f"{where} excludes for the reason other and states no note")
    return AuditObservation(
        entry.text("item_id"), decision, entry.text("observation"), reason, note
    )


def read_audit_review(path: Path) -> AuditReview:
    """Read one blinded review under its contract, refusing an item decided twice."""
    document = read_declaration(path, AUDIT_REVIEW_CONTRACT, AUDIT_REVIEW_SCHEMA_VERSION)
    fields = Fields(document, path.name)
    observations: dict[str, AuditObservation] = {}
    for position, raw in enumerate(fields.items("observations")):
        observation = _observation(raw, f"{path.name}.observations[{position}]")
        if observation.item_id in observations:
            raise invalid(f"{path.name} decides item {observation.item_id} twice")
        observations[observation.item_id] = observation
    return AuditReview(
        fields.text("audit_id"),
        fields.text("reviewer"),
        fields.text("independence"),
        fields.text("blinding"),
        fields.index("reviewer_minutes"),
        observations,
        sha256_bytes(canonical_json(document)),
    )


def require_corpus_reviews(
    review: AuditReview, items: Sequence[Mapping[str, JsonValue]], run_ids: Sequence[str]
) -> list[dict[str, JsonValue]]:
    """Map one blinded review onto one corpus review per run, once the item set matches."""
    expected = {str(item["item_id"]) for item in items}
    found = set(review.observations)
    if found != expected:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "the blinded review does not decide the audit sample",
            {
                "missing": list[JsonValue](sorted(expected - found)),
                "unexpected": list[JsonValue](sorted(found - expected)),
            },
        )
    documents = [_mapped_review(run_id, review, items) for run_id in run_ids]
    for document in documents:
        _require_review(document)
    return documents


def _require_review(document: Mapping[str, JsonValue]) -> None:
    installed = installed_contracts()
    contract = installed.contracts.named(REVIEW_CONTRACT)
    frozen = contract.newest(REVIEW_SCHEMA_VERSION)
    assert frozen is not None, "the corpus review contract has a frozen version of its major"
    require_conforming(
        document,
        installed.contracts,
        contract,
        frozen,
        code=RefusalCode.MANIFEST_INVALID,
        label="unblinded review",
        registry=installed.registry,
    )


def _decision(item: Mapping[str, JsonValue], observation: AuditObservation) -> dict[str, JsonValue]:
    record: dict[str, JsonValue] = {
        "stream_id": str(item["stream_id"]),
        "candidate_id": str(item["candidate_id"]),
        "decision": observation.decision,
    }
    if observation.observation is not None:
        record["observation"] = observation.observation
    if observation.reason is not None:
        record["reason"] = observation.reason
    if observation.note is not None:
        record["note"] = observation.note
    return record


def _mapped_review(
    run_id: str, review: AuditReview, items: Sequence[Mapping[str, JsonValue]]
) -> dict[str, JsonValue]:
    decisions = [_decision(item, review.observations[str(item["item_id"])]) for item in items]
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "run_id": run_id,
        "reviewer": review.reviewer,
        "independence": review.independence,
        "blinding": review.blinding,
        "reviewer_minutes": review.reviewer_minutes,
        "audit_id": review.audit_id,
        "decisions": list[JsonValue](decisions),
    }
