"""Derive one hashed label revision for every generated case of a corpus.

Parent revisions live at ``$DATA_DIR/corpus/<id>/labels/<stream-id>/``. A parent
with no revision leaves its cases unscorable. A plate that still shows a target,
or a track that does not match the frozen instance, refuses the command before
any case is written.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.annotate.derive_apply import Applied, apply_label_transform
from ss_track.annotate.derive_check import require_case_labels
from ss_track.annotate.derive_document import frame_space
from ss_track.annotate.derive_record import publish_case, transform_sha256
from ss_track.annotate.derive_result import DerivedCase, DeriveResult
from ss_track.annotate.digest import as_document, declaration_hash
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.label_read import read_label_set
from ss_track.annotate.label_rules import check_label_set
from ss_track.annotate.pack import load_scenario_pack
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.revision_record import read_annotation_revision
from ss_track.annotate.validate import LABEL_CONTRACT
from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.core.scratch import exclusive_lock
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.corpus.storage.layout import (
    label_document_path,
    label_revision_path,
    labels_directory,
)
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.validation.enforce import read_declaration

_MAJOR = 1
_LOCK = ".derive.lock"
_NO_LABELS = "no_frozen_labels"


@dataclass(frozen=True, slots=True)
class _Parent:
    """One stream's frozen revision and the label document it pins."""

    revision_sha256: str
    label_sha256: str
    labels: LabelSet


@dataclass(frozen=True, slots=True)
class _Pending:
    """One case that passed its checks and is ready to write."""

    case_id: str
    parent_stream_id: str
    parent: _Parent
    applied: Applied
    transform_kind: str
    label_transform_sha256: str


def prepare_case_labels(
    labels: LabelSet, case: Mapping[str, object], pack: ScenarioPack, revision_sha256: str
) -> Applied:
    """Check one case against frozen labels and return the derived label set."""
    require_case_labels(labels, case, revision_sha256)
    transform = case.get("label_transform")
    case_id = case.get("case_id")
    if not isinstance(transform, Mapping) or not isinstance(case_id, str):
        raise invalid("generated case has no label transform")
    return apply_label_transform(labels, transform, pack, case_id)


def derive_corpus(corpus_id: str, pack_path: Path, data_root: Path) -> DeriveResult:
    """Derive every generated case, or leave a case unscorable when its parent has no revision."""
    manifest = load_corpus_manifest(corpus_id, data_root)
    pack = load_scenario_pack(pack_path)
    raw = manifest.get("generated_cases")
    if not isinstance(raw, list):
        raise TypeError("generated_cases is not a list")
    parents: dict[str, _Parent | None] = {}
    pending: list[_Pending] = []
    skipped: set[str] = set()
    order: list[str] = []
    for item in raw:
        case = _case(item)
        case_id = _text(case, "case_id")
        order.append(case_id)
        parent = _parent(parents, _text(case, "parent_stream_id"), pack, data_root, corpus_id)
        if parent is None:
            skipped.add(case_id)
            continue
        applied = prepare_case_labels(parent.labels, case, pack, parent.revision_sha256)
        pending.append(_hold(case, parent, applied))
    written = _publish(pending, pack, data_root, corpus_id)
    cases = tuple(_row(case_id, skipped, written) for case_id in order)
    return DeriveResult(corpus_id, cases)


def _parent(
    parents: dict[str, _Parent | None],
    stream_id: str,
    pack: ScenarioPack,
    data_root: Path,
    corpus_id: str,
) -> _Parent | None:
    if stream_id not in parents:
        parents[stream_id] = _load_parent(data_root, corpus_id, stream_id, pack)
    return parents[stream_id]


def _load_parent(
    data_root: Path, corpus_id: str, stream_id: str, pack: ScenarioPack
) -> _Parent | None:
    revision = label_revision_path(data_root, corpus_id, stream_id)
    document_path = label_document_path(data_root, corpus_id, stream_id)
    if not revision.is_file() or not document_path.is_file():
        return None
    sealed = read_annotation_revision(revision)
    document = read_declaration(document_path, LABEL_CONTRACT, _MAJOR)
    digest = declaration_hash(as_document(document))
    if digest != sealed.get("label_sha256"):
        raise invalid("label document does not match the frozen revision")
    labels = read_label_set(Fields(document, document_path.name), digest)
    check_label_set(labels, pack, frame_space(labels))
    return _Parent(str(sealed[SEAL_FIELD]), digest, labels)


def _hold(case: Mapping[str, JsonValue], parent: _Parent, applied: Applied) -> _Pending:
    transform = case["label_transform"]
    if not isinstance(transform, Mapping):
        raise invalid("generated case has no label transform")
    return _Pending(
        _text(case, "case_id"),
        _text(case, "parent_stream_id"),
        parent,
        applied,
        _text(transform, "kind"),
        transform_sha256(transform),
    )


def _publish(
    pending: list[_Pending], pack: ScenarioPack, data_root: Path, corpus_id: str
) -> dict[str, DerivedCase]:
    if not pending:
        return {}
    written: dict[str, DerivedCase] = {}
    with exclusive_lock(labels_directory(data_root, corpus_id), _LOCK):
        for item in pending:
            written[item.case_id] = _write(item, pack, data_root, corpus_id)
    return written


def _write(item: _Pending, pack: ScenarioPack, data_root: Path, corpus_id: str) -> DerivedCase:
    label_sha, revision_sha, labels_path, revision_path = publish_case(
        item.applied.labels,
        pack,
        data_root=data_root,
        corpus_id=corpus_id,
        case_id=item.case_id,
        parent_stream_id=item.parent_stream_id,
        parent_revision_sha256=item.parent.revision_sha256,
        parent_label_sha256=item.parent.label_sha256,
        transform_kind=item.transform_kind,
        label_transform_sha256=item.label_transform_sha256,
        timestamp_quality=item.applied.timestamp_quality,
    )
    return DerivedCase(
        item.case_id,
        "derived",
        label_sha256=label_sha,
        revision_sha256=revision_sha,
        labels_path=labels_path,
        revision_path=revision_path,
        timestamp_quality=item.applied.timestamp_quality,
    )


def _row(case_id: str, skipped: set[str], written: dict[str, DerivedCase]) -> DerivedCase:
    if case_id in skipped:
        return DerivedCase(case_id, "unscorable", reason=_NO_LABELS)
    return written[case_id]


def _case(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise TypeError("generated case is not an object")
    return value


def _text(value: Mapping[str, object], name: str) -> str:
    found = value.get(name)
    if not isinstance(found, str) or not found:
        raise invalid(f"{name} is not text")
    return found
