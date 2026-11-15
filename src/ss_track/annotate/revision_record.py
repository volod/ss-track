"""Write the frozen label document and the sealed revision that pins it.

The label hash is the declaration hash. The revision seal covers both annotator
hashes, the sample, the disagreements and that label hash. The two annotator hashes
are the sensitivity band. This record computes no score.
"""

import json
from collections.abc import Mapping
from pathlib import Path

from ss_track.annotate.digest import declaration_hash
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.label_read import read_label_set
from ss_track.annotate.label_rules import check_label_set
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.review_model import Disagreement, Reviewer, ReviewPlan, Settlement
from ss_track.annotate.revision_build import build_frozen_document
from ss_track.annotate.space import FrameSpace
from ss_track.annotate.validate import LABEL_CONTRACT
from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.core.refusal import JsonValue, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.corpus.declarations.fields import Fields
from ss_track.corpus.records.kinds import ANNOTATION_REVISION
from ss_track.schema.registry.store import damaged
from ss_track.schema.validation.enforce import installed_contracts, require_conforming

_MAJOR = 1


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
    _write_label(labels_out, document)
    sealed = seal(_body(left, rows, plan, settlement, reviewers, label_sha256))
    write_sealed(revision_out, sealed)
    return label_sha256, str(sealed[SEAL_FIELD])


def read_annotation_revision(path: Path) -> dict[str, JsonValue]:
    """Read a frozen revision as evidence."""
    return read_sealed(path, ANNOTATION_REVISION)


def _checked_label(
    document: dict[str, JsonValue], pack: ScenarioPack, space: FrameSpace, revision_id: str
) -> str:
    _require_schema(document)
    digest = declaration_hash(document)
    labels = read_label_set(Fields(document, revision_id), digest)
    check_label_set(labels, pack, space)
    return labels.document_sha256


def _require_schema(document: Mapping[str, JsonValue]) -> None:
    installed = installed_contracts()
    contract = installed.contracts.named(LABEL_CONTRACT)
    frozen = contract.newest(_MAJOR)
    if frozen is None:
        raise damaged(f"{LABEL_CONTRACT} has no frozen major {_MAJOR}")
    require_conforming(
        document,
        installed.contracts,
        contract,
        frozen,
        code=RefusalCode.MANIFEST_INVALID,
        label="frozen labels",
    )


def _write_label(path: Path, document: Mapping[str, JsonValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
    write_atomically(path, f"{payload}\n".encode("ascii"))


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
