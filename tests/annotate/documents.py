"""Builders for annotation fixtures. Coordinates are stored pixels."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.annotate.digest import as_document, declaration_hash
from ss_track.annotate.disposition import DISPOSITIONS
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.label_read import read_label_set
from ss_track.annotate.label_rules import check_label_set, label_entries
from ss_track.annotate.mask import MaskSet, check_mask, read_mask
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.result import LABEL_VERSION, AnnotationResult
from ss_track.annotate.seed import SeedSet, check_seed, read_seed
from ss_track.annotate.space import FrameSpace
from ss_track.annotate.validate import LABEL_CONTRACT, MASK_CONTRACT, SEED_CONTRACT
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.fields import Fields
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.enforce import read_declaration
from ss_track.schema.validation.strict import violations

SPACE = FrameSpace(
    source_sha256="ab" * 32,
    width=64,
    height=48,
    display_rotation_degrees=90,
    time_base="1/25",
    pts=(0, 1, 2, 3),
)


def write_yaml(path: Path, body: Mapping[str, Any]) -> Path:
    """Write one declaration. Key order in the file is not part of its hash."""
    path.write_text(yaml.safe_dump(dict(body), sort_keys=False), encoding="utf-8")
    return path


def label_body(pack: ScenarioPack, space: FrameSpace = SPACE) -> dict[str, Any]:
    """Return one scorable bird label in the stored orientation."""
    return {
        "schema_version": 1,
        "label_id": "clip-a",
        "pack_id": pack.pack_id,
        "pack_hash": pack.pack_hash,
        "source_sha256": space.source_sha256,
        "frame_count": space.frame_count,
        "width": space.width,
        "height": space.height,
        "orientation_degrees": 0,
        "display_rotation_degrees": space.display_rotation_degrees,
        "instances": [
            {
                "instance_id": "target-1",
                "class_id": "bird",
                "identity": "reviewed",
                "non_scoring_mark": None,
                "frames": [frame()],
            }
        ],
        "motion_events": [event()],
    }


def frame(index: int = 0, visibility: str = "visible") -> dict[str, Any]:
    """Return one visible box, or an unlocalizable frame when the visibility has no extent."""
    if visibility in ("visible", "partially_occluded"):
        geometry: dict[str, Any] = {
            "kind": "box",
            "box": {"x": 1, "y": 2, "width": 4, "height": 3},
            "amodal_box": None,
            "uncertainty_px": 1,
            "plausible_extent_px": None,
        }
    else:
        geometry = {"kind": "unlocalizable"}
    return {
        "frame_index": index,
        "visibility": visibility,
        "camera_motion": "static",
        "annotator_id": "ann-a",
        "geometry": geometry,
    }


def event(visibility: str = "visible", onset: int = 0, reentry: bool = False) -> dict[str, Any]:
    """Return a motion event whose visibility matches its frame."""
    return {
        "event_id": "onset-1",
        "instance_id": "target-1",
        "onset_frame": onset,
        "onset_uncertainty_frames": 1,
        "visibility": visibility,
        "selection_quality": "reviewed",
        "reentry": reentry,
    }


def replace_frame(body: dict[str, Any], labeled: dict[str, Any]) -> dict[str, Any]:
    """Replace the only frame and keep the motion event in agreement with it."""
    body["instances"][0]["frames"][0] = labeled
    if body["motion_events"]:
        body["motion_events"][0]["visibility"] = labeled["visibility"]
        body["motion_events"][0]["onset_frame"] = labeled["frame_index"]
        visible = labeled["visibility"] in ("visible", "partially_occluded")
        body["motion_events"][0]["reentry"] = body["motion_events"][0]["reentry"] and visible
    return body


def seed_body(space: FrameSpace, label_sha256: str) -> dict[str, Any]:
    """Return a seed whose box matches the default label and whose replay moves one column."""
    return {
        "schema_version": 1,
        "seed_id": "seed-1",
        "label_sha256": label_sha256,
        "annotator_id": "op-1",
        "source_sha256": space.source_sha256,
        "frame_count": space.frame_count,
        "width": space.width,
        "height": space.height,
        "orientation_degrees": 0,
        "display_rotation_degrees": space.display_rotation_degrees,
        "frame_index": 0,
        "pts": None,
        "time_base": None,
        "intended_instance_id": "target-1",
        "quality": "as_clicked",
        "original": {"kind": "box", "x": 1, "y": 2, "width": 4, "height": 3},
        "perturbations": [{"perturbation_id": "shift-1", "dx": 1, "dy": 0, "frame_offset": 0}],
    }


def mask_body(label_sha256: str, result: AnnotationResult, frame_count: int) -> dict[str, Any]:
    """Return a mask that repeats the validation rows and covers them with one episode each."""
    grouped: dict[str, list[Any]] = {}
    frames = []
    for entry in result.entries:
        frames.append(
            {
                "instance_id": entry.entry_id,
                "frame_index": entry.frame_index,
                "disposition": entry.disposition,
                "reason": entry.reason,
            }
        )
        grouped.setdefault(entry.entry_id, []).append(entry)
    episodes = []
    for index, (instance_id, rows) in enumerate(grouped.items(), start=1):
        scorable = any(row.disposition == "scorable" for row in rows)
        episodes.append(
            {
                "episode_id": f"ep-{index}",
                "instance_id": instance_id,
                "start_frame": 0,
                "end_frame": frame_count,
                "eligibility": "eligible" if scorable else "excluded",
                "exclusion_reason": None if scorable else "no scorable frame",
            }
        )
    return {
        "schema_version": 1,
        "mask_id": "clip-a-mask",
        "label_sha256": label_sha256,
        "frames": frames,
        "episodes": episodes,
    }


def refused(action: Any, reason: str) -> CorpusRefusal:
    """Return the refusal, which must name `reason`."""
    with pytest.raises(CorpusRefusal, match=reason) as caught:
        action()
    refusal: CorpusRefusal = caught.value
    assert refusal.code is RefusalCode.MANIFEST_INVALID
    return refusal


def assert_command(result: AnnotationResult) -> dict[str, Any]:
    """Require the command result to match the newest command contract and carry no score."""
    record = json.loads(json.dumps(result.to_record()))
    contracts = load_contract_set()
    contract = contracts.named("result/command")
    frozen = contract.versions[-1]
    found = violations(
        record, contracts.frozen_schema(contract, frozen), contracts.schema_registry()
    )
    assert not found, found
    _no_score(record)
    assert record["annotation"]["entries"]
    assert {row["disposition"] for row in record["annotation"]["entries"]} <= set(DISPOSITIONS)
    return record


def _no_score(value: object) -> None:
    if isinstance(value, dict):
        assert "score" not in value
        for child in value.values():
            _no_score(child)
    elif isinstance(value, list):
        for child in value:
            _no_score(child)


def load_labels(path: Path, pack: ScenarioPack, space: FrameSpace = SPACE) -> LabelSet:
    """Read one label file and apply the rules against `space`."""
    document = read_declaration(path, LABEL_CONTRACT, 1)
    labels = read_label_set(Fields(document, path.name), declaration_hash(as_document(document)))
    check_label_set(labels, pack, space)
    return labels


def load_seed(path: Path, labels: LabelSet, space: FrameSpace = SPACE) -> SeedSet:
    """Read one seed file and apply the rules against the labels and `space`."""
    document = read_declaration(path, SEED_CONTRACT, 1)
    seed = read_seed(Fields(document, path.name), declaration_hash(as_document(document)))
    check_seed(seed, labels, space)
    return seed


def load_mask(path: Path, labels: LabelSet) -> MaskSet:
    """Read one mask file and require it to repeat the label dispositions."""
    document = read_declaration(path, MASK_CONTRACT, 1)
    mask = read_mask(Fields(document, path.name), declaration_hash(as_document(document)))
    check_mask(mask, labels)
    return mask


def label_result(path: Path, labels: LabelSet, pack: ScenarioPack) -> AnnotationResult:
    """Return the command result a label validation would log."""
    return AnnotationResult(
        path,
        LABEL_CONTRACT,
        LABEL_VERSION,
        "label",
        labels.document_sha256,
        pack.pack_hash,
        None,
        label_entries(labels),
    )
