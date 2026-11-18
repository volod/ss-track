"""Seal one derived label revision.

The seal pins the parent revision, the parent label hash and the hash of the
stored label transform. It has no score, and it is not a two-reviewer freeze.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ss_track.annotate.declarations.digest import declaration_hash
from ss_track.annotate.derivation.result import DerivedCase
from ss_track.annotate.labels.document import checked_document, write_label
from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.contract_stamp import require_current_data_root
from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.core.refusal import JsonValue
from ss_track.corpus.records.kinds import DERIVED_LABEL
from ss_track.corpus.storage.layout import label_document_path, label_revision_path


@dataclass(frozen=True, slots=True)
class Derivation:
    """What one derived revision pins beside its labels: the case, its parent and its transform."""

    case_id: str
    parent_stream_id: str
    parent_revision_sha256: str
    parent_label_sha256: str
    transform_kind: str
    label_transform_sha256: str
    timestamp_quality: str | None


def transform_sha256(transform: Mapping[str, object]) -> str:
    """Return the declaration hash of one stored label transform."""
    return declaration_hash(cast(Mapping[str, JsonValue], transform))


def publish_case(
    labels: LabelSet, pack: ScenarioPack, derivation: Derivation, data_root: Path, corpus_id: str
) -> DerivedCase:
    """Validate, write and seal one case, and return its row."""
    require_current_data_root(data_root)
    document, label_sha256 = checked_document(labels, pack)
    labels_path = label_document_path(data_root, corpus_id, derivation.case_id)
    revision_path = label_revision_path(data_root, corpus_id, derivation.case_id)
    sealed = seal(_body(labels, derivation, label_sha256))
    write_label(labels_path, document)
    write_sealed(revision_path, sealed)
    return DerivedCase(
        derivation.case_id,
        "derived",
        label_sha256=label_sha256,
        revision_sha256=str(sealed[SEAL_FIELD]),
        labels_path=labels_path,
        revision_path=revision_path,
        timestamp_quality=derivation.timestamp_quality,
    )


def _body(labels: LabelSet, derivation: Derivation, label_sha256: str) -> dict[str, JsonValue]:
    return {
        **DERIVED_LABEL.stamp(),
        "case_id": derivation.case_id,
        "parent_stream_id": derivation.parent_stream_id,
        "parent_revision_sha256": derivation.parent_revision_sha256,
        "parent_label_sha256": derivation.parent_label_sha256,
        "label_sha256": label_sha256,
        "pack_id": labels.pack_id,
        "pack_hash": labels.pack_hash,
        "source_sha256": labels.space.source_sha256,
        "transform_kind": derivation.transform_kind,
        "label_transform_sha256": derivation.label_transform_sha256,
        "timestamp_quality": derivation.timestamp_quality,
    }
