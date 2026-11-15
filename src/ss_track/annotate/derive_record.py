"""Seal one derived label revision.

The seal pins the parent revision, the parent label hash and the hash of the
stored label transform. It has no score, and it is not a two-reviewer freeze.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from ss_track.annotate.derive_document import checked_document, write_label
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.core.canonical import SEAL_FIELD, canonical_json, sha256_bytes
from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.core.refusal import JsonValue
from ss_track.corpus.records.kinds import DERIVED_LABEL
from ss_track.corpus.storage.layout import label_document_path, label_revision_path


def transform_sha256(transform: Mapping[str, object]) -> str:
    """Return the declaration hash of one stored label transform."""
    body = cast(Mapping[str, JsonValue], transform)
    return sha256_bytes(canonical_json(body))


def publish_case(
    labels: LabelSet,
    pack: ScenarioPack,
    *,
    data_root: Path,
    corpus_id: str,
    case_id: str,
    parent_stream_id: str,
    parent_revision_sha256: str,
    parent_label_sha256: str,
    transform_kind: str,
    label_transform_sha256: str,
    timestamp_quality: str | None,
) -> tuple[str, str, Path, Path]:
    """Validate, write and seal one case. Return the two hashes and the two paths."""
    document, label_sha256 = checked_document(labels, pack)
    labels_path = label_document_path(data_root, corpus_id, case_id)
    revision_path = label_revision_path(data_root, corpus_id, case_id)
    sealed = seal(
        _body(
            labels,
            case_id=case_id,
            parent_stream_id=parent_stream_id,
            parent_revision_sha256=parent_revision_sha256,
            parent_label_sha256=parent_label_sha256,
            label_sha256=label_sha256,
            transform_kind=transform_kind,
            label_transform_sha256=label_transform_sha256,
            timestamp_quality=timestamp_quality,
        )
    )
    write_label(labels_path, document)
    write_sealed(revision_path, sealed)
    return label_sha256, str(sealed[SEAL_FIELD]), labels_path, revision_path


def _body(
    labels: LabelSet,
    *,
    case_id: str,
    parent_stream_id: str,
    parent_revision_sha256: str,
    parent_label_sha256: str,
    label_sha256: str,
    transform_kind: str,
    label_transform_sha256: str,
    timestamp_quality: str | None,
) -> dict[str, JsonValue]:
    return {
        **DERIVED_LABEL.stamp(),
        "case_id": case_id,
        "parent_stream_id": parent_stream_id,
        "parent_revision_sha256": parent_revision_sha256,
        "parent_label_sha256": parent_label_sha256,
        "label_sha256": label_sha256,
        "pack_id": labels.pack_id,
        "pack_hash": labels.pack_hash,
        "source_sha256": labels.space.source_sha256,
        "transform_kind": transform_kind,
        "label_transform_sha256": label_transform_sha256,
        "timestamp_quality": timestamp_quality,
    }
