"""Derive one hashed label revision for every generated case of a corpus.

Parent revisions live at ``$DATA_DIR/corpus/<id>/labels/<stream-id>/``. A parent
with no revision leaves its cases unscorable. Frozen labels that were not drawn on
their stream, a plate that still shows a target, or a track that does not match the
frozen instance refuses the command before any case is written.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.annotate.declarations.contracts import LABEL_CONTRACT, read_hashed
from ss_track.annotate.derivation.apply import Applied, apply_label_transform
from ss_track.annotate.derivation.check import require_case_labels
from ss_track.annotate.derivation.fields import mapping, text
from ss_track.annotate.derivation.record import Derivation, publish_case, transform_sha256
from ss_track.annotate.derivation.result import DerivedCase, DeriveResult
from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.labels.read import read_label_set
from ss_track.annotate.labels.rules import check_label_rules
from ss_track.annotate.packs.load import load_scenario_pack
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.revision import read_annotation_revision
from ss_track.annotate.sources.declared_space import require_stream
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

_LOCK = ".derive.lock"


@dataclass(frozen=True, slots=True)
class _Parent:
    """One stream's frozen revision and the label document it pins."""

    revision_sha256: str
    label_sha256: str
    labels: LabelSet


@dataclass(frozen=True, slots=True)
class _Pending:
    """One case that passed its checks and is ready to write."""

    derivation: Derivation
    labels: LabelSet


def prepare_case_labels(
    labels: LabelSet, case: Mapping[str, object], pack: ScenarioPack, revision_sha256: str
) -> Applied:
    """Check one case against frozen labels and return the derived label set."""
    require_case_labels(labels, case, revision_sha256)
    transform = mapping(case.get("label_transform"), "label_transform")
    return apply_label_transform(labels, transform, pack, text(case, "case_id"))


def derive_corpus(corpus_id: str, pack_path: Path, data_root: Path) -> DeriveResult:
    """Derive every generated case, or leave a case unscorable when its parent has no revision."""
    manifest = load_corpus_manifest(corpus_id, data_root)
    pack = load_scenario_pack(pack_path)
    streams = {text(stream, "stream_id"): stream for stream in _objects(manifest, "streams")}
    parents: dict[str, _Parent | None] = {}
    pending: list[_Pending] = []
    rows: dict[str, DerivedCase | None] = {}
    for case in _objects(manifest, "generated_cases"):
        case_id, stream_id = text(case, "case_id"), text(case, "parent_stream_id")
        if stream_id not in parents:
            stream = mapping(streams.get(stream_id), f"stream {stream_id}")
            parents[stream_id] = _load_parent(data_root, corpus_id, stream, pack)
        parent = parents[stream_id]
        rows[case_id] = None if parent is not None else DerivedCase.without_parent_labels(case_id)
        if parent is not None:
            pending.append(_checked(case, parent, pack))
    written = _publish(pending, pack, data_root, corpus_id)
    return DeriveResult(corpus_id, tuple(row or written[case_id] for case_id, row in rows.items()))


def _load_parent(
    data_root: Path, corpus_id: str, stream: Mapping[str, object], pack: ScenarioPack
) -> _Parent | None:
    """Read one stream's frozen labels, or ``None`` when the stream has no frozen revision."""
    stream_id = text(stream, "stream_id")
    revision = label_revision_path(data_root, corpus_id, stream_id)
    document_path = label_document_path(data_root, corpus_id, stream_id)
    if not revision.is_file() or not document_path.is_file():
        return None
    sealed = read_annotation_revision(revision)
    document, digest = read_hashed(document_path, LABEL_CONTRACT)
    if digest != sealed.get("label_sha256"):
        raise invalid("label document does not match the frozen revision")
    labels = read_label_set(Fields(document, document_path.name), digest)
    check_label_rules(labels, pack)
    require_stream(labels.space, stream, f"frozen labels {labels.label_id}")
    return _Parent(str(sealed[SEAL_FIELD]), digest, labels)


def _checked(case: Mapping[str, object], parent: _Parent, pack: ScenarioPack) -> _Pending:
    applied = prepare_case_labels(parent.labels, case, pack, parent.revision_sha256)
    transform = mapping(case.get("label_transform"), "label_transform")
    derivation = Derivation(
        case_id=text(case, "case_id"),
        parent_stream_id=text(case, "parent_stream_id"),
        parent_revision_sha256=parent.revision_sha256,
        parent_label_sha256=parent.label_sha256,
        transform_kind=text(transform, "kind"),
        label_transform_sha256=transform_sha256(transform),
        timestamp_quality=applied.timestamp_quality,
    )
    return _Pending(derivation, applied.labels)


def _publish(
    pending: list[_Pending], pack: ScenarioPack, data_root: Path, corpus_id: str
) -> dict[str, DerivedCase]:
    if not pending:
        return {}
    with exclusive_lock(labels_directory(data_root, corpus_id), _LOCK):
        return {
            item.derivation.case_id: publish_case(
                item.labels, pack, item.derivation, data_root, corpus_id
            )
            for item in pending
        }


def _objects(holder: Mapping[str, JsonValue], name: str) -> list[Mapping[str, object]]:
    raw = holder.get(name)
    if not isinstance(raw, list):
        raise TypeError(f"{name} is not a list")
    return [mapping(item, f"{name} entry") for item in raw]
