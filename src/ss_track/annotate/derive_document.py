"""Write one derived label document and check it against the label contract.

The document is the same declaration a reviewer freezes. Its hash is the
declaration hash. A derivation that the contract refuses is not sealed.
"""

import json
from collections.abc import Mapping
from pathlib import Path

from ss_track.annotate.derive_geom import json_number
from ss_track.annotate.digest import declaration_hash
from ss_track.annotate.geometry import Box
from ss_track.annotate.label_model import (
    Instance,
    LabeledFrame,
    LabelGeometry,
    LabelSet,
    MotionEvent,
)
from ss_track.annotate.label_read import read_label_set
from ss_track.annotate.label_rules import check_label_set
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.space import FrameSpace
from ss_track.annotate.validate import LABEL_CONTRACT
from ss_track.core.refusal import JsonValue, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.corpus.declarations.fields import Fields
from ss_track.schema.registry.store import damaged
from ss_track.schema.validation.enforce import installed_contracts, require_conforming

_MAJOR = 1


def checked_document(labels: LabelSet, pack: ScenarioPack) -> tuple[dict[str, JsonValue], str]:
    """Return the label document and its hash, once the contract and the pack accept it."""
    document = label_document(labels)
    _require_schema(document)
    digest = declaration_hash(document)
    read = read_label_set(Fields(document, labels.label_id), digest)
    check_label_set(read, pack, frame_space(read))
    return document, digest


def write_label(path: Path, document: Mapping[str, JsonValue]) -> None:
    """Write one label document. A repeated write of the same document is the same file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
    write_atomically(path, f"{payload}\n".encode("ascii"))


def label_document(labels: LabelSet) -> dict[str, JsonValue]:
    """Return the declaration object for one derived label set."""
    space = labels.space
    return {
        "schema_version": _MAJOR,
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


def frame_space(labels: LabelSet) -> FrameSpace:
    """Return a frame space taken from the label document itself."""
    space = labels.space
    return FrameSpace(
        source_sha256=space.source_sha256,
        width=space.width,
        height=space.height,
        display_rotation_degrees=space.display_rotation_degrees,
        time_base=None,
        pts=tuple(None for _ in range(space.frame_count)),
    )


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
        label="derived labels",
    )
