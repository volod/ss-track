"""The written form of a label set, and the one check a built document must pass.

A frozen revision and a derived case write the same declaration. Its hash is the
declaration hash. A document the contract or the pack refuses is not written.
"""

import json
from collections.abc import Mapping
from pathlib import Path

from ss_track.annotate.declarations.contracts import (
    LABEL_CONTRACT,
    SCHEMA_MAJOR,
    read_hashed,
    require_built,
)
from ss_track.annotate.declarations.digest import declaration_hash
from ss_track.annotate.labels.geometry import Box
from ss_track.annotate.labels.model import (
    Instance,
    LabeledFrame,
    LabelGeometry,
    LabelSet,
    MotionEvent,
)
from ss_track.annotate.labels.read import read_label_set
from ss_track.annotate.labels.rules import check_label_rules, check_label_set
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.sources.frame_space import FrameSpace
from ss_track.core.refusal import JsonValue
from ss_track.core.scratch import write_atomically
from ss_track.corpus.declarations.fields import Fields

_EXACT_INTEGER_LIMIT = 2**53  # above it a float no longer names one integer


def read_label_file(path: Path, pack: ScenarioPack, space: FrameSpace) -> LabelSet:
    """Return the labels of one file that match this pack and the stored frames of its source."""
    labels = read_unjoined_label_file(path)
    check_label_set(labels, pack, space)
    return labels


def read_unjoined_label_file(path: Path) -> LabelSet:
    """Return the labels of one file under its contract, before any rule joins them to a source."""
    document, document_sha256 = read_hashed(path, LABEL_CONTRACT)
    return read_label_set(Fields(document, path.name), document_sha256)


def checked_document(labels: LabelSet, pack: ScenarioPack) -> tuple[dict[str, JsonValue], str]:
    """Return a built label document and its hash, once the contract and the pack accept it.

    The caller has already joined the labels to what they were drawn on.
    """
    document = label_document(labels)
    require_built(document, LABEL_CONTRACT, "derived labels")
    read = read_label_set(Fields(document, labels.label_id), declaration_hash(document))
    check_label_rules(read, pack)
    return document, read.document_sha256


def write_label(path: Path, document: Mapping[str, JsonValue]) -> None:
    """Write one label document. A repeated write of the same document is the same file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, label_bytes(document))


def label_bytes(document: Mapping[str, JsonValue]) -> bytes:
    """Return the bytes one label document is stored as."""
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
    return f"{payload}\n".encode("ascii")


def label_document(labels: LabelSet) -> dict[str, JsonValue]:
    """Return the declaration object for one label set."""
    space = labels.space
    return {
        "schema_version": SCHEMA_MAJOR,
        "label_id": labels.label_id,
        "pack_id": labels.pack_id,
        "pack_hash": labels.pack_hash,
        "source_sha256": space.source_sha256,
        "frame_count": space.frame_count,
        "width": space.width,
        "height": space.height,
        "orientation_degrees": space.orientation_degrees,
        "display_rotation_degrees": space.display_rotation_degrees,
        "instances": [_instance(item) for item in labels.instances],
        "motion_events": [_event(item) for item in labels.motion_events],
    }


def json_number(value: float) -> int | float:
    """Return an integer when the measure lands on one, so the document does not carry ``2.0``."""
    if value.is_integer() and abs(value) < _EXACT_INTEGER_LIMIT:
        return int(value)
    return value


def _instance(instance: Instance) -> dict[str, JsonValue]:
    return {
        "instance_id": instance.instance_id,
        "class_id": instance.class_id,
        "identity": instance.identity,
        "non_scoring_mark": instance.non_scoring_mark,
        "frames": [_frame(frame) for frame in instance.frames],
    }


def _frame(frame: LabeledFrame) -> dict[str, JsonValue]:
    return {
        "frame_index": frame.frame_index,
        "visibility": frame.visibility,
        "camera_motion": frame.camera_motion,
        "annotator_id": frame.annotator_id,
        "geometry": _geometry(frame.geometry),
    }


def _geometry(geometry: LabelGeometry) -> dict[str, JsonValue]:
    if geometry.kind == "unlocalizable":
        return {"kind": "unlocalizable"}
    if geometry.kind == "box" and geometry.box is not None and geometry.uncertainty_px is not None:
        return {
            "kind": "box",
            "box": _box(geometry.box),
            "amodal_box": None if geometry.amodal_box is None else _box(geometry.amodal_box),
            "uncertainty_px": json_number(geometry.uncertainty_px),
            "plausible_extent_px": None,
        }
    if (
        geometry.kind == "point_only"
        and geometry.point is not None
        and geometry.uncertainty_px is not None
    ):
        return {
            "kind": "point_only",
            "point": {"x": geometry.point.x, "y": geometry.point.y},
            "uncertainty_px": json_number(geometry.uncertainty_px),
            "plausible_extent_px": geometry.plausible_extent_px,
        }
    raise TypeError(f"geometry {geometry.kind} cannot be written")


def _box(box: Box) -> dict[str, JsonValue]:
    return {"x": box.x, "y": box.y, "width": box.width, "height": box.height}


def _event(event: MotionEvent) -> dict[str, JsonValue]:
    return {
        "event_id": event.event_id,
        "instance_id": event.instance_id,
        "onset_frame": event.onset_frame,
        "onset_uncertainty_frames": event.onset_uncertainty_frames,
        "visibility": event.visibility,
        "selection_quality": event.selection_quality,
        "reentry": event.reentry,
    }
