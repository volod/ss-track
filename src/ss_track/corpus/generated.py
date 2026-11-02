"""Stage one generated case: a frame bundle derived from its parent's verified frames.

A case is an ordinary bundle, so a module reads it exactly as it reads a stream. Its identity covers
the parent bundle and the recipe, and neither a corpus nor a case name, so one recipe over one parent
gives one hash. Every parent frame is re-hashed on the way in by `read_frame`.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ss_track.corpus.bundle_writer import publish_bundle, require_space, store_frame
from ss_track.corpus.case_model import Pixels, ReadFrame, Rendering, Slot, as_pixels
from ss_track.corpus.frames import (
    FRAME_BUNDLE_KIND,
    FrameBundle,
    bundle_hash,
    open_frame_bundle,
)
from ss_track.corpus.importer import MANIFEST_NAME
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import SEAL_FIELD, read_sealed, seal, write_sealed
from ss_track.corpus.timestamps import TimestampQuality
from ss_track.corpus.transforms import prepare_case


def _frame_reader(parent: FrameBundle) -> ReadFrame:
    def read(frame_index: int) -> Pixels:
        return as_pixels(parent.read_frame(frame_index), parent.width, parent.height)

    return read


def _time_claim(parent_record: Mapping[str, Any], rendering: Rendering) -> tuple[str, str | None]:
    """A repeated frame shows an older capture, so its PTS is no longer a measured capture time."""
    quality, evidence = parent_record["timestamp_quality"], parent_record["capture_clock_evidence"]
    stale = any(slot.content_frame_index != slot.frame_index for slot in rendering.slots)
    if stale and quality == TimestampQuality.MEASURED:
        return TimestampQuality.DERIVED.value, None
    return quality, evidence


def _case_body(
    case: Mapping[str, Any],
    parent: FrameBundle,
    parent_record: Mapping[str, Any],
    rendering: Rendering,
    frames: Sequence[Mapping[str, Any]],
) -> dict[str, JsonValue]:
    """Inherit every fact of the parent's record, then state what this case changed."""
    body = {key: value for key, value in parent_record.items() if key != SEAL_FIELD}
    recipe: dict[str, JsonValue] = {
        "transform": case["transform"],
        "transform_revision": case["transform_revision"],
        "seed": case["seed"],
        "window": case["window"],
        "parameters": case["parameters"],
    }
    identity: dict[str, JsonValue] = {
        **parent_record["identity"],
        "parent_bundle_sha256": parent.bundle_sha256,
        "recipe": recipe,
        "label_transform": rendering.label_transform,
        "frames": [dict(frame) for frame in frames],
    }
    quality, evidence = _time_claim(parent_record, rendering)
    return body | {
        "stream_id": case["case_id"],
        "bundle_sha256": bundle_hash(identity),
        "identity": identity,
        "timestamp_quality": quality,
        "capture_clock_evidence": evidence,
        "generated": {
            "parent_stream_id": case["parent_stream_id"],
            "encounter_id": case["encounter_id"],
            "group_id": case["group_id"],
            "split": case["split"],
        },
    }


def _store_slot(
    directory: Path, slot: Slot, window: range, parent: FrameBundle, rendering: Rendering
) -> dict[str, JsonValue]:
    """Store one case frame. A frame outside the window keeps its parent's exact bytes."""
    packed = parent.read_frame(slot.content_frame_index)
    if rendering.paint is not None and slot.frame_index in window:
        pixels = as_pixels(packed, parent.width, parent.height)
        packed = rendering.paint(pixels, slot.frame_index).tobytes()
    pts = parent.frame_ref(slot.frame_index).pts
    entry = store_frame(directory, slot.frame_index, pts, packed)
    if slot.content_frame_index != slot.frame_index:
        entry["content_frame_index"] = slot.content_frame_index
    return entry


def _require_some_change(
    case: Mapping[str, Any], parent: FrameBundle, frames: Sequence[Mapping[str, Any]]
) -> None:
    """A case identical to its parent tests no failure mechanism and must not pass as one."""
    same_frames = len(frames) == len(parent)
    if same_frames and all(
        frame["sha256"] == parent.frame_ref(frame["frame_index"]).sha256 for frame in frames
    ):
        raise CorpusRefusal(
            RefusalCode.CASE_INVALID,
            f"generated case {case['case_id']} changes no frame of its parent",
            {"case_id": case["case_id"], "transform": case["transform"]},
        )


def write_case_bundle(case: Mapping[str, Any], parent: FrameBundle, root: Path) -> FrameBundle:
    """Write one case into scratch and publish it with one rename."""
    read = _frame_reader(parent)
    rendering = prepare_case(case, parent.selection, parent.width, parent.height, read)
    require_space(root, len(rendering.slots), parent.width, parent.height)
    parent_record = read_sealed(parent.directory / MANIFEST_NAME, FRAME_BUNDLE_KIND)
    window = range(case["window"]["start_frame"], case["window"]["end_frame"])
    target = root / case["case_id"]
    with publish_bundle(root, target) as staged:
        frames = [_store_slot(staged, slot, window, parent, rendering) for slot in rendering.slots]
        _require_some_change(case, parent, frames)
        body = _case_body(case, parent, parent_record, rendering, frames)
        write_sealed(staged / MANIFEST_NAME, seal(body))
    return open_frame_bundle(target)
