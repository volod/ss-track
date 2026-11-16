"""Label documents and generated-case records for derivation tests.

Expected boxes in the tests are literals. These helpers only build the parent.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.annotate.derivation.derive import prepare_case_labels
from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.packs.model import ScenarioPack
from tests.annotate.documents import SPACE, frame, label_body, load_labels, write_yaml

BOX = {"x": 1, "y": 2, "width": 4, "height": 3}
REVISION = "ab" * 32


def box_frame(
    index: int = 0,
    *,
    x: int = 1,
    y: int = 2,
    width: int = 4,
    height: int = 3,
    uncertainty: int | float = 1,
    amodal: dict[str, int] | None = None,
    visibility: str = "visible",
) -> dict[str, Any]:
    """Return one box frame. The default box is the shared annotation fixture."""
    return {
        "frame_index": index,
        "visibility": visibility,
        "camera_motion": "static",
        "annotator_id": "ann-a",
        "geometry": {
            "kind": "box",
            "box": {"x": x, "y": y, "width": width, "height": height},
            "amodal_box": amodal,
            "uncertainty_px": uncertainty,
            "plausible_extent_px": None,
        },
    }


def point_frame(
    index: int = 0, *, x: int = 5, y: int = 7, extent: int | None = 5, uncertainty: int = 4
) -> dict[str, Any]:
    """Return one point frame."""
    return {
        "frame_index": index,
        "visibility": "visible",
        "camera_motion": "static",
        "annotator_id": "ann-a",
        "geometry": {
            "kind": "point_only",
            "point": {"x": x, "y": y},
            "uncertainty_px": uncertainty,
            "plausible_extent_px": extent,
        },
    }


def labels_of(
    folder: Path,
    pack: ScenarioPack,
    frames: list[dict[str, Any]],
    *,
    events: list[dict[str, Any]] | None = None,
    extra: list[dict[str, Any]] | None = None,
) -> LabelSet:
    """Load one parent whose first instance carries `frames`."""
    folder.mkdir(parents=True, exist_ok=True)
    body = label_body(pack, SPACE)
    body["instances"][0]["frames"] = frames
    if events is not None:
        body["motion_events"] = events
    if extra:
        body["instances"].extend(extra)
    return load_labels(write_yaml(folder / "parent.yaml", body), pack)


def case_of(
    transform: Mapping[str, object],
    *,
    case_id: str = "case-1",
    window: tuple[int, int] = (0, 4),
    parameters: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return one generated case. A track case supplies its own parameters."""
    return {
        "case_id": case_id,
        "parent_stream_id": "stream-1",
        "window": {"start_frame": window[0], "end_frame": window[1]},
        "parameters": {} if parameters is None else dict(parameters),
        "label_transform": dict(transform),
    }


def other_instance(index: int = 0, *, x: int = 20, y: int = 10) -> dict[str, Any]:
    """Return a second scoring instance on one frame."""
    labeled = frame(index)
    labeled["geometry"]["box"] = {"x": x, "y": y, "width": 6, "height": 6}
    return {
        "instance_id": "other-1",
        "class_id": "bird",
        "identity": "reviewed",
        "non_scoring_mark": None,
        "frames": [labeled],
    }


def rect(x: int, y: int, width: int, height: int) -> dict[str, int]:
    """Return one stored rectangle."""
    return {"x": x, "y": y, "width": width, "height": height}


def apply_track_case(
    labels: LabelSet,
    pack: ScenarioPack,
    frames: list[dict[str, object]],
    track: list[dict[str, object]],
    *,
    window: tuple[int, int] = (0, 1),
    revision: str = REVISION,
    **parameters: object,
) -> LabelSet:
    transform = {
        "kind": "track_status",
        "label_revision": revision,
        "instance_id": "target-1",
        "frames": frames,
    }
    body = case_of(
        transform,
        window=window,
        parameters={"track": track, **parameters},
    )
    return prepare_case_labels(labels, body, pack, REVISION).labels


def first_box(labels: LabelSet) -> tuple[int, int, int, int]:
    box = labels.instances[0].frames[0].geometry.box
    if box is None:
        raise TypeError("frame has no box")
    return (box.x, box.y, box.width, box.height)


def track_box(index: int, *, x: int = 1, y: int = 2) -> dict[str, object]:
    return {"frame_index": index, "box": rect(x, y, 4, 3)}


def boxed(index: int, role: str, *, x: int = 1, y: int = 2) -> dict[str, object]:
    return {"frame_index": index, "role": role, "region": rect(x, y, 4, 3)}


def shift(index: int, dx: int, dy: int) -> dict[str, object]:
    return {
        "frame_index": index,
        "role": "shift",
        "dx": dx,
        "dy": dy,
        "region": dict(BOX),
        "visibility": "out_of_view",
    }


def removal(index: int, region: dict[str, int]) -> dict[str, object]:
    return {
        "frame_index": index,
        "role": "region",
        "region": region,
        "inside": "absent",
        "overlap": "unknown",
        "overlap_geometry": "unlocalizable",
    }


def distractor(index: int, region: dict[str, int]) -> dict[str, object]:
    return removal(index, region) | {
        "inside": "unknown",
        "overlap": "unknown",
        "added_objects": "distractor",
    }


def status_region(region: dict[str, int]) -> dict[str, object]:
    return {
        "kind": "region_status",
        "frames": {"start_frame": 0, "end_frame": 1},
        "region": region,
        "inside": "absent",
        "overlap": "unknown",
        "overlap_geometry": "unlocalizable",
    }
