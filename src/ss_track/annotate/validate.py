"""Validate one label, seed or mask document against the source modules receive."""

from pathlib import Path

from ss_track.annotate.digest import as_document, declaration_hash
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.label_read import read_label_set
from ss_track.annotate.label_rules import check_label_set, label_entries
from ss_track.annotate.mask import check_mask, mask_entries, read_mask
from ss_track.annotate.pack import load_scenario_pack
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.result import (
    LABEL_VERSION,
    MASK_VERSION,
    SEED_VERSION,
    AnnotationEntry,
    AnnotationKind,
    AnnotationResult,
)
from ss_track.annotate.seed import check_seed, read_seed, replay_hash, seed_entries
from ss_track.annotate.space import FrameSpace, read_frame_space
from ss_track.corpus.declarations.fields import Fields
from ss_track.schema.validation.enforce import read_declaration

LABEL_CONTRACT = "declaration/annotation-label"
SEED_CONTRACT = "declaration/annotation-seed"
MASK_CONTRACT = "declaration/annotation-mask"
_MAJOR = 1


def validate_labels(path: Path, pack_path: Path, source: Path) -> AnnotationResult:
    """Validate labels against one pack and one video file."""
    space = read_frame_space(source)
    pack = load_scenario_pack(pack_path)
    labels = _labels(path, pack, space)
    return _result(
        path,
        LABEL_CONTRACT,
        LABEL_VERSION,
        "label",
        labels.document_sha256,
        pack.pack_hash,
        None,
        label_entries(labels),
    )


def validate_seed(path: Path, labels_path: Path, pack_path: Path, source: Path) -> AnnotationResult:
    """Validate a seed against the labels, pack and video its selection was drawn on."""
    space = read_frame_space(source)
    pack = load_scenario_pack(pack_path)
    labels = _labels(labels_path, pack, space)
    document = read_declaration(path, SEED_CONTRACT, _MAJOR)
    seed = read_seed(Fields(document, path.name), declaration_hash(as_document(document)))
    check_seed(seed, labels, space)
    return _result(
        path,
        SEED_CONTRACT,
        SEED_VERSION,
        "seed",
        seed.document_sha256,
        None,
        replay_hash(seed),
        seed_entries(seed),
    )


def validate_mask(path: Path, labels_path: Path, pack_path: Path, source: Path) -> AnnotationResult:
    """Validate a mask against the labels it freezes. An unscorable frame stays unscorable."""
    space = read_frame_space(source)
    pack = load_scenario_pack(pack_path)
    labels = _labels(labels_path, pack, space)
    document = read_declaration(path, MASK_CONTRACT, _MAJOR)
    mask = read_mask(Fields(document, path.name), declaration_hash(as_document(document)))
    check_mask(mask, labels)
    return _result(
        path,
        MASK_CONTRACT,
        MASK_VERSION,
        "mask",
        mask.document_sha256,
        None,
        None,
        mask_entries(mask),
    )


def read_validated_labels(path: Path, pack: ScenarioPack, space: FrameSpace) -> LabelSet:
    """Return labels that match this pack and the stored frame."""
    return _labels(path, pack, space)


def _labels(path: Path, pack: ScenarioPack, space: FrameSpace) -> LabelSet:
    document = read_declaration(path, LABEL_CONTRACT, _MAJOR)
    labels = read_label_set(Fields(document, path.name), declaration_hash(as_document(document)))
    check_label_set(labels, pack, space)
    return labels


def _result(
    path: Path,
    contract: str,
    version: str,
    kind: AnnotationKind,
    document_sha256: str,
    pack_hash: str | None,
    replay_sha256: str | None,
    entries: tuple[AnnotationEntry, ...],
) -> AnnotationResult:
    return AnnotationResult(
        path, contract, version, kind, document_sha256, pack_hash, replay_sha256, entries
    )
