"""Write the frozen label document and the sealed revision that pins it.

The label hash is the declaration hash. The revision seal covers both annotator
hashes, the sample, the disagreements and that label hash. The two annotator hashes
are the sensitivity band. This record computes no score. Both files are written once.
"""

from collections.abc import Mapping
from pathlib import Path

from ss_track.annotate.declarations.contracts import LABEL_CONTRACT, require_built
from ss_track.annotate.declarations.digest import declaration_hash
from ss_track.annotate.labels.document import label_bytes, write_label
from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.labels.read import read_label_set
from ss_track.annotate.labels.rules import check_label_set
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.frozen_document import build_frozen_document
from ss_track.annotate.review.model import Disagreement, Reviewer, ReviewPlan, Settlement
from ss_track.annotate.sources.frame_space import FrameSpace
from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import seal, sealed_bytes, write_sealed
from ss_track.core.refusal import JsonValue
from ss_track.core.scratch import holds_payload
from ss_track.corpus.declarations.fields import Fields
from ss_track.corpus.records.kinds import ANNOTATION_REVISION


def write_revision(
    left: LabelSet,
    right: LabelSet,
    rows: tuple[Disagreement, ...],
    pack: ScenarioPack,
    space: FrameSpace,
    plan: ReviewPlan,
    settlement: Settlement,
    reviewers: tuple[Reviewer, Reviewer],
    labels_out: Path,
    revision_out: Path,
) -> tuple[str, str]:
    """Validate and write the label document and the sealed revision. Return both hashes."""
    document = build_frozen_document(
        left,
        right,
        rows,
        pack,
        revision_id=settlement.revision_id,
        authority=plan.authority,
    )
    label_sha256 = _checked_label(document, pack, space, settlement.revision_id)
    sealed = seal(_body(left, rows, plan, settlement, reviewers, label_sha256))
    _publish_once(labels_out, document, revision_out, sealed)
    return label_sha256, str(sealed[SEAL_FIELD])


def _publish_once(
    labels_out: Path,
    document: Mapping[str, JsonValue],
    revision_out: Path,
    sealed: Mapping[str, JsonValue],
) -> None:
    """Write both files once. Either path holding other bytes refuses before anything is written.

    The label document goes first. A crash between the two leaves no revision, which reads as
    not frozen, and the same freeze again completes it.
    """
    labels_held = holds_payload(labels_out, label_bytes(document))
    revision_held = holds_payload(revision_out, sealed_bytes(sealed))
    if not labels_held:
        write_label(labels_out, document)
    if not revision_held:
        write_sealed(revision_out, sealed)


def read_annotation_revision(path: Path) -> dict[str, JsonValue]:
    """Read a frozen revision as evidence."""
    return read_sealed(path, ANNOTATION_REVISION)


def _checked_label(
    document: dict[str, JsonValue], pack: ScenarioPack, space: FrameSpace, revision_id: str
) -> str:
    require_built(document, LABEL_CONTRACT, "frozen labels")
    labels = read_label_set(Fields(document, revision_id), declaration_hash(document))
    check_label_set(labels, pack, space)
    return labels.document_sha256


def _body(
    left: LabelSet,
    rows: tuple[Disagreement, ...],
    plan: ReviewPlan,
    settlement: Settlement,
    reviewers: tuple[Reviewer, Reviewer],
    label_sha256: str,
) -> dict[str, JsonValue]:
    listed: list[JsonValue] = [row.to_record() for row in rows]
    sample: list[JsonValue] = [
        {"instance_id": instance_id, "frame_index": frame_index}
        for instance_id, frame_index in plan.items
    ]
    left_reviewer, right_reviewer = reviewers
    return {
        **ANNOTATION_REVISION.stamp(),
        "revision_id": settlement.revision_id,
        "authority": plan.authority,
        "coverage": plan.coverage,
        "label_sha256": label_sha256,
        "pack_id": left.pack_id,
        "pack_hash": left.pack_hash,
        "source_sha256": left.space.source_sha256,
        "review_sha256": plan.document_sha256,
        "settlement_sha256": settlement.document_sha256,
        "sensitivity_band": {
            "left_sha256": left_reviewer.label_sha256,
            "right_sha256": right_reviewer.label_sha256,
        },
        "reviewers": [left_reviewer.to_record(), right_reviewer.to_record()],
        "sample": sample,
        "disagreements": listed,
    }
