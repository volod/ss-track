"""The versioned transforms of spec section 4.3, each a pure function of frames and seed.

Pixel work is integer arithmetic only, so its result has no floating-point or SIMD freedom. Changing
what a transform produces means raising its revision, and `test_transform_golden.py` fails until
that happens. A stored case then refuses to stage instead of silently becoming different evidence.
"""

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np

from ss_track.corpus.case_model import CaseContext, Pixels, ReadFrame, Rendering, Slot
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.region_transforms import moving_background, short_occlusion, target_absence
from ss_track.corpus.seeded import SeededDraws

_SHAKE_AXES = 2


def _camera_shake(case: CaseContext) -> Rendering:
    """Shift each frame by a whole-pixel offset. Exposed edges repeat the nearest pixel."""
    amplitude: int = case.parameters["amplitude"]
    case.require(amplitude < min(case.width, case.height), "amplitude exceeds the frame")
    offsets = {
        index: case.draws.integers(f"offset:{index}", _SHAKE_AXES, -amplitude, amplitude)
        for index in case.window
    }

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        dx, dy = offsets[frame_index]
        rows = np.clip(np.arange(case.height) - dy, 0, case.height - 1)
        columns = np.clip(np.arange(case.width) - dx, 0, case.width - 1)
        return pixels[rows][:, columns]

    labels: dict[str, JsonValue] = {
        "kind": "translate",
        "camera_motion": "shake",
        "frames": case.frame_range(),
        "offsets": [
            {"frame_index": index, "dx": dx, "dy": dy} for index, (dx, dy) in offsets.items()
        ],
    }
    return Rendering(case.unchanged_slots(), paint, labels)


def _blur_axis(pixels: Pixels, radius: int, axis: int) -> Pixels:
    """Average `2 * radius + 1` pixels along one axis, repeating edges and rounding to nearest."""
    size = 2 * radius + 1
    padding = [(0, 0)] * pixels.ndim
    padding[axis] = (radius + 1, radius)
    totals = np.cumsum(np.pad(pixels, padding, mode="edge"), axis=axis, dtype=np.uint32)
    upper = totals.take(np.arange(size, totals.shape[axis]), axis=axis)
    lower = totals.take(np.arange(totals.shape[axis] - size), axis=axis)
    blurred: Pixels = ((upper - lower + radius) // size).astype(np.uint8)
    return blurred


def _blur(case: CaseContext) -> Rendering:
    """Box-blur each frame by its own drawn radius, as focus and exposure drift in the field."""
    max_radius: int = case.parameters["max_radius"]
    case.require(max_radius < min(case.width, case.height), "max_radius exceeds the frame")
    radii = {
        index: case.draws.integers(f"radius:{index}", 1, 1, max_radius)[0] for index in case.window
    }

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        radius = radii[frame_index]
        return _blur_axis(_blur_axis(pixels, radius, 0), radius, 1)

    return Rendering(case.unchanged_slots(), paint, {"kind": "identity"})


def _dropped_frames(case: CaseContext) -> Rendering:
    """Remove frames. Survivors keep their index and PTS, so the gap stays visible."""
    count: int = case.parameters["count"]
    case.require(count <= len(case.window), "count exceeds the window")
    case.require(count < len(case.selection), "a case must keep at least one frame")
    removed = case.draws.pick("dropped", case.window, count)
    kept = sorted(set(case.selection) - set(removed))
    labels: dict[str, JsonValue] = {"kind": "frame_map", "removed": [*removed], "repeated": []}
    return Rendering(tuple(Slot(index, index) for index in kept), None, labels)


def _duplicated_frames(case: CaseContext) -> Rendering:
    """Repeat the previous frame's pixels at a frame's own index and PTS, as a stalled feed does."""
    count: int = case.parameters["count"]
    candidates = [index for index in case.window if index > case.selection.start]
    case.require(count <= len(candidates), "count exceeds the frames that have a predecessor")
    stale = set(case.draws.pick("duplicated", candidates, count))
    content: dict[int, int] = {}
    for index in case.selection:
        content[index] = content[index - 1] if index in stale else index
    repeated: list[JsonValue] = [
        {"frame_index": index, "content_frame_index": content[index]} for index in sorted(stale)
    ]
    labels: dict[str, JsonValue] = {"kind": "frame_map", "removed": [], "repeated": repeated}
    return Rendering(tuple(Slot(index, content[index]) for index in case.selection), None, labels)


_TRANSFORMS: dict[str, tuple[int, Callable[[CaseContext], Rendering]]] = {
    "target_absence": (1, target_absence),
    "moving_background": (1, moving_background),
    "camera_shake": (1, _camera_shake),
    "blur": (1, _blur),
    "dropped_frames": (1, _dropped_frames),
    "duplicated_frames": (1, _duplicated_frames),
    "short_occlusion": (1, short_occlusion),
}
TRANSFORM_REVISIONS = {name: revision for name, (revision, _) in _TRANSFORMS.items()}


def require_transform_revision(case: Mapping[str, Any]) -> None:
    """Refuse a stored case whose transform this code can no longer reproduce."""
    installed = TRANSFORM_REVISIONS.get(case["transform"])
    if installed != case["transform_revision"]:
        raise CorpusRefusal(
            RefusalCode.TRANSFORM_REVISION_MISMATCH,
            f"generated case {case['case_id']} needs a revision this code does not provide",
            {
                "case_id": case["case_id"],
                "transform": case["transform"],
                "case_transform_revision": case["transform_revision"],
                "installed_transform_revision": installed,
            },
        )


def prepare_case(
    case: Mapping[str, Any],
    selection: range,
    width: int,
    height: int,
    read: ReadFrame,
) -> Rendering:
    """Validate one recipe against its parent and return what it does to that parent."""
    window = range(case["window"]["start_frame"], case["window"]["end_frame"])
    context = CaseContext(
        case_id=case["case_id"],
        transform=case["transform"],
        parameters=case["parameters"],
        window=window,
        selection=selection,
        width=width,
        height=height,
        draws=SeededDraws(case["transform"], case["seed"]),
        read=read,
    )
    context.require(
        window.start >= selection.start and window.stop <= selection.stop,
        "window runs past the parent selection",
    )
    _, transform = _TRANSFORMS[case["transform"]]
    return transform(context)
