"""The `track_status` record a track-following case stores for later label derivation.

Each window frame is listed. A frame with no box is `unknown`. The other roles say what happened
to that frame's box. `generated-case-labels` applies this record; nothing here edits a label.
"""

from ss_track.core.refusal import JsonValue
from ss_track.corpus.cases.case_model import CaseContext, Region

_FULLY_OCCLUDED = "fully_occluded"
_PARTIALLY_OCCLUDED = "partially_occluded"
_ABSENT = "absent"
_UNKNOWN = "unknown"
_UNLOCALIZABLE = "unlocalizable"
_DISTRACTOR = "distractor"
_OUT_OF_VIEW = "out_of_view"


def track_status(case: CaseContext, frames: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    """Return the label transform for one frozen revision and one instance."""
    labels: dict[str, JsonValue] = {
        "kind": "track_status",
        "label_revision": str(case.parameters["label_revision"]),
        "instance_id": str(case.parameters["instance_id"]),
        "frames": [dict(frame) for frame in frames],
    }
    return labels


def unknown_frame(index: int) -> dict[str, JsonValue]:
    """Return the record for a window frame that has no scorable box."""
    return {"frame_index": index, "role": "unknown"}


def occluder_frame(index: int, box: Region | None, visible: Region | None) -> dict[str, JsonValue]:
    """Return the label for one frame of a crossing occluder."""
    if box is None:
        return unknown_frame(index)
    if visible is None:
        return _boxed(index, "unchanged", box)
    return _region(index, visible, _FULLY_OCCLUDED, _PARTIALLY_OCCLUDED)


def removal_frame(index: int, box: Region | None) -> dict[str, JsonValue]:
    """Return absence for a box, or unknown when the frame has no box."""
    if box is None:
        return unknown_frame(index)
    return _region(index, box, _ABSENT, _UNKNOWN)


def distractor_frame(index: int, box: Region | None, copy: Region | None) -> dict[str, JsonValue]:
    """Return the added copy as a distractor, or unknown when the frame has no box."""
    if box is None or copy is None:
        return unknown_frame(index)
    return _region(index, copy, _UNKNOWN, _UNKNOWN, added_objects=_DISTRACTOR)


def exit_frame(
    index: int,
    box: Region | None,
    outside: range,
    shift: tuple[int, int] | None,
) -> dict[str, JsonValue]:
    """Return out-of-view, re-entry, unchanged, or unknown for one frame."""
    if box is None:
        return unknown_frame(index)
    if shift is not None:
        horizontal, vertical = shift
        return {
            "frame_index": index,
            "role": "shift",
            "dx": horizontal,
            "dy": vertical,
            "region": box.record(),
            "visibility": _OUT_OF_VIEW,
        }
    if index >= outside.stop:
        return _boxed(index, "reentry", box)
    return _boxed(index, "unchanged", box)


def _region(
    index: int, region: Region, inside: str, overlap: str, **extra: JsonValue
) -> dict[str, JsonValue]:
    record: dict[str, JsonValue] = {
        "frame_index": index,
        "role": "region",
        "region": region.record(),
        "inside": inside,
        "overlap": overlap,
        "overlap_geometry": _UNLOCALIZABLE,
    }
    return record | extra


def _boxed(index: int, role: str, region: Region) -> dict[str, JsonValue]:
    return {"frame_index": index, "role": role, "region": region.record()}
