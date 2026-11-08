"""Read a reviewer's decisions on the candidates one discovery run offered, under their contract.

A decision names a stream and candidate of the run. Including a window puts its frames in the
frozen version; excluding one keeps them out with a reason from a closed list; `unreviewed` says
plainly that no one decided it. Every include and exclude states what the reviewer saw, and that
observation is never a label: a frozen version holds membership only.
"""

from dataclasses import dataclass
from pathlib import Path

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.corpus.review.queue import CandidateKey
from ss_track.schema.validation.enforce import read_declaration

REVIEW_CONTRACT = "declaration/corpus-review"
REVIEW_SCHEMA_VERSION = 1
INCLUDE = "include"
EXCLUDE = "exclude"
UNREVIEWED = "unreviewed"
OTHER_REASON = "other"
DECLARED = "declared"
NOT_DECLARED = "not_declared"


@dataclass(frozen=True, slots=True)
class Decision:
    """One reviewer decision on one offered candidate."""

    key: CandidateKey
    decision: str
    observation: str | None = None
    reason: str | None = None
    note: str | None = None

    def fields(self) -> dict[str, JsonValue]:
        """Return what the freeze record copies beside the candidate: observation, reason, note."""
        record: dict[str, JsonValue] = {}
        if self.observation is not None:
            record["observation"] = self.observation
        if self.reason is not None:
            record["reason"] = self.reason
        if self.note is not None:
            record["note"] = self.note
        return record


@dataclass(frozen=True, slots=True)
class Review:
    """Every decision of one review, keyed by candidate, who made them and the document's hash.

    Independence, blinding and minutes are present only when the review states them. A stated
    value is the reviewer's declaration, not a check that the procedure was followed.
    """

    run_id: str
    reviewer: str
    decisions: dict[CandidateKey, Decision]
    review_sha256: str
    independence: str | None = None
    blinding: str | None = None
    reviewer_minutes: int | None = None
    audit_id: str | None = None

    def decided(self, decision: str) -> list[Decision]:
        """Return the decisions of one kind, ascending by stream and candidate."""
        return [item for _, item in sorted(self.decisions.items()) if item.decision == decision]


def _decision(raw: object, where: str) -> Decision:
    entry = Fields(raw, where)
    key = (entry.text("stream_id"), entry.text("candidate_id"))
    decision = entry.text("decision")
    if decision == UNREVIEWED:
        return Decision(key, decision)
    reason = entry.text("reason") if decision == EXCLUDE else None
    note = entry.optional_text("note")
    if reason == OTHER_REASON and note is None:
        raise invalid(f"{where} excludes for the reason other and states no note")
    return Decision(key, decision, entry.text("observation"), reason, note)


def read_review(path: Path) -> Review:
    """Read one review under its contract, refusing a candidate decided twice."""
    document = read_declaration(path, REVIEW_CONTRACT, REVIEW_SCHEMA_VERSION)
    fields = Fields(document, path.name)
    decisions: dict[CandidateKey, Decision] = {}
    for position, raw in enumerate(fields.items("decisions")):
        decision = _decision(raw, f"{path.name}.decisions[{position}]")
        if decision.key in decisions:
            stream_id, candidate_id = decision.key
            raise invalid(f"{path.name} decides candidate {candidate_id} of {stream_id} twice")
        decisions[decision.key] = decision
    return Review(
        fields.text("run_id"),
        fields.text("reviewer"),
        decisions,
        sha256_bytes(canonical_json(document)),
        fields.text("independence") if fields.has("independence") else None,
        fields.text("blinding") if fields.has("blinding") else None,
        fields.index("reviewer_minutes") if fields.has("reviewer_minutes") else None,
        fields.text("audit_id") if fields.has("audit_id") else None,
    )
