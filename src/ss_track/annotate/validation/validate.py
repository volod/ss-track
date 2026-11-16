"""Validate one label, seed or mask document against the source modules receive."""

from pathlib import Path

from ss_track.annotate.declarations.contracts import (
    LABEL_CONTRACT,
    MASK_CONTRACT,
    SEED_CONTRACT,
    read_hashed,
    read_version,
)
from ss_track.annotate.labels.document import read_label_file
from ss_track.annotate.packs.load import load_scenario_pack
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.annotate.validation.mask import check_mask, mask_entries, read_mask
from ss_track.annotate.validation.result import AnnotationResult, label_entries
from ss_track.annotate.validation.seed import check_seed, read_seed, replay_hash, seed_entries
from ss_track.corpus.declarations.fields import Fields


def validate_labels(
    path: Path, pack_path: Path, source: Path, video_stream_index: int | None = None
) -> AnnotationResult:
    """Validate labels against one pack and one video stream or retained image sequence."""
    space = read_frame_space(source, video_stream_index)
    pack = load_scenario_pack(pack_path)
    labels = read_label_file(path, pack, space)
    return AnnotationResult(
        path,
        LABEL_CONTRACT,
        read_version(LABEL_CONTRACT),
        "label",
        labels.document_sha256,
        pack.pack_hash,
        None,
        label_entries(labels),
    )


def validate_seed(
    path: Path,
    labels_path: Path,
    pack_path: Path,
    source: Path,
    video_stream_index: int | None = None,
) -> AnnotationResult:
    """Validate a seed against the labels, pack and source its selection was drawn on."""
    space = read_frame_space(source, video_stream_index)
    labels = read_label_file(labels_path, load_scenario_pack(pack_path), space)
    document, document_sha256 = read_hashed(path, SEED_CONTRACT)
    seed = read_seed(Fields(document, path.name), document_sha256)
    check_seed(seed, labels, space)
    return AnnotationResult(
        path,
        SEED_CONTRACT,
        read_version(SEED_CONTRACT),
        "seed",
        seed.document_sha256,
        None,
        replay_hash(seed),
        seed_entries(seed),
    )


def validate_mask(
    path: Path,
    labels_path: Path,
    pack_path: Path,
    source: Path,
    video_stream_index: int | None = None,
) -> AnnotationResult:
    """Validate a mask against the labels it freezes. An unscorable frame stays unscorable."""
    space = read_frame_space(source, video_stream_index)
    labels = read_label_file(labels_path, load_scenario_pack(pack_path), space)
    document, document_sha256 = read_hashed(path, MASK_CONTRACT)
    mask = read_mask(Fields(document, path.name), document_sha256)
    check_mask(mask, labels)
    return AnnotationResult(
        path,
        MASK_CONTRACT,
        read_version(MASK_CONTRACT),
        "mask",
        mask.document_sha256,
        None,
        None,
        mask_entries(mask),
    )
