"""`ss-track corpus preview`: one parent frame beside each generated case, as a PNG.

The command reads staged bundles and writes only the named PNG, outside the corpus directory. A
region is outlined on the case that declares it. A frame that case removed stays in the sheet as a
marked panel, so the gap is visible.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.frames import FrameBundle, frames_root
from ss_track.corpus.cases.case_model import Region
from ss_track.corpus.cases.preview_png import (
    PNG_ENCODER,
    encode_rgb_png,
    join_horizontal,
    paint_outline,
    removed_panel,
)
from ss_track.corpus.decoding.pixels import OUTPUT_PIXEL_FORMAT
from ss_track.corpus.records.sealing import SCRATCH_PREFIX
from ss_track.corpus.versions.builder import CORPUS_DIRECTORY, load_corpus_manifest

ROLE_PARENT = "parent"
ROLE_CASE = "case"
ROLE_REMOVED = "removed"
_REGION_STATUS = "region_status"


@dataclass(frozen=True, slots=True)
class PreviewPanel:
    """One panel of the sheet, from left to right."""

    stream_id: str
    role: str
    region: Region | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form. `region` is absent when no outline was drawn."""
        record: dict[str, JsonValue] = {"role": self.role, "stream_id": self.stream_id}
        if self.region is not None:
            record["region"] = self.region.record()
        return record


@dataclass(frozen=True, slots=True)
class PreviewResult:
    """The PNG that was written and the panels it holds."""

    corpus_id: str
    stream_id: str
    frame_index: int
    path: str
    png_sha256: str
    width: int
    height: int
    frame_width: int
    frame_height: int
    panels: tuple[PreviewPanel, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the command result."""
        return {
            "status": "written",
            "corpus_id": self.corpus_id,
            "files": [self.path],
            "preview": {
                "encoder": PNG_ENCODER,
                "stream_id": self.stream_id,
                "frame_index": self.frame_index,
                "width": self.width,
                "height": self.height,
                "frame_width": self.frame_width,
                "frame_height": self.frame_height,
                "png_sha256": self.png_sha256,
                "panels": [panel.to_record() for panel in self.panels],
            },
        }


def preview_stream(
    corpus_id: str, stream_id: str, frame_index: int, out: Path, data_root: Path
) -> PreviewResult:
    """Write a contact sheet of one parent frame and the cases derived from that stream."""
    corpus = load_corpus_manifest(corpus_id, data_root)
    _require_parent_stream(corpus, stream_id)
    _require_output_outside_corpus(out, data_root)
    root = frames_root(data_root, corpus_id)
    parent = open_corpus_bundle(stream_id, corpus, root)
    _require_rgb24(parent)
    panels = [(PreviewPanel(parent.stream_id, ROLE_PARENT), parent.read_frame(frame_index))]
    for case in _child_cases(corpus, stream_id):
        panels.append(_case_panel(case, parent, frame_index, corpus, root))
    packed = join_horizontal([item for _, item in panels], parent.width, parent.height)
    payload = encode_rgb_png(parent.width * len(panels), parent.height, packed)
    _write_bytes(out, payload)
    described = tuple(panel for panel, _ in panels)
    return PreviewResult(
        corpus_id=corpus_id,
        stream_id=stream_id,
        frame_index=frame_index,
        path=str(out),
        png_sha256=sha256_bytes(payload),
        width=parent.width * len(panels),
        height=parent.height,
        frame_width=parent.width,
        frame_height=parent.height,
        panels=described,
    )


def _case_panel(
    case: Mapping[str, Any],
    parent: FrameBundle,
    frame_index: int,
    corpus: Mapping[str, Any],
    root: Path,
) -> tuple[PreviewPanel, bytes]:
    bundle = open_corpus_bundle(str(case["case_id"]), corpus, root)
    _require_same_shape(parent, bundle)
    pixels = _frame_pixels(bundle, frame_index)
    if pixels is None:
        return (
            PreviewPanel(bundle.stream_id, ROLE_REMOVED),
            removed_panel(parent.width, parent.height),
        )
    region = _region_on_frame(case, frame_index)
    if region is not None:
        pixels = paint_outline(pixels, parent.width, parent.height, region)
    return PreviewPanel(bundle.stream_id, ROLE_CASE, region), pixels


def _require_parent_stream(corpus: Mapping[str, Any], stream_id: str) -> None:
    streams: list[dict[str, Any]] = corpus["streams"]
    if any(stream["stream_id"] == stream_id for stream in streams):
        return
    cases: list[dict[str, Any]] = corpus["generated_cases"]
    for case in cases:
        if case["case_id"] == stream_id:
            raise CorpusRefusal(
                RefusalCode.CASE_INVALID,
                "preview shows a parent stream beside its generated cases",
                {"stream_id": stream_id, "parent_stream_id": case["parent_stream_id"]},
            )
    raise CorpusRefusal(
        RefusalCode.BUNDLE_NOT_STAGED,
        "this stream has no staged frame bundle",
        {"stream_id": stream_id},
    )


def _require_output_outside_corpus(out: Path, data_root: Path) -> None:
    """A preview must not add a file among staged bundles or sealed corpus records."""
    corpus_root = (data_root / CORPUS_DIRECTORY).resolve()
    target = out.resolve()
    if target == corpus_root or target.is_relative_to(corpus_root):
        raise CorpusRefusal(
            RefusalCode.STORAGE_FAILED,
            "preview writes its PNG outside the corpus directory",
            {"path": str(out)},
        )


def _require_rgb24(bundle: FrameBundle) -> None:
    if bundle.pixel_format != OUTPUT_PIXEL_FORMAT:
        raise CorpusRefusal(
            RefusalCode.SOURCE_FORMAT_CHANGED,
            "preview reads rgb24 frames",
            {"stream_id": bundle.stream_id, "pixel_format": bundle.pixel_format},
        )


def _require_same_shape(parent: FrameBundle, case: FrameBundle) -> None:
    same = case.width == parent.width and case.height == parent.height
    same = same and case.pixel_format == parent.pixel_format
    if not same:
        raise CorpusRefusal(
            RefusalCode.CASE_INVALID,
            f"generated case {case.stream_id} does not match its parent's frame shape",
            {
                "case_id": case.stream_id,
                "parent_stream_id": parent.stream_id,
                "width": case.width,
                "height": case.height,
                "pixel_format": case.pixel_format,
            },
        )


def _child_cases(corpus: Mapping[str, Any], stream_id: str) -> tuple[Mapping[str, Any], ...]:
    cases: list[dict[str, Any]] = corpus["generated_cases"]
    children = [case for case in cases if case["parent_stream_id"] == stream_id]
    return tuple(sorted(children, key=lambda case: str(case["case_id"])))


def _region_on_frame(case: Mapping[str, Any], frame_index: int) -> Region | None:
    label: Mapping[str, Any] = case["label_transform"]
    if label.get("kind") != _REGION_STATUS:
        return None
    frames: Mapping[str, int] = label["frames"]
    if not frames["start_frame"] <= frame_index < frames["end_frame"]:
        return None
    box: Mapping[str, int] = label["region"]
    return Region(int(box["x"]), int(box["y"]), int(box["width"]), int(box["height"]))


def _frame_pixels(bundle: FrameBundle, frame_index: int) -> bytes | None:
    """Return one frame, or none when this case removed it. Other refusals still propagate."""
    try:
        return bundle.read_frame(frame_index)
    except CorpusRefusal as refusal:
        if refusal.code is not RefusalCode.FRAME_NOT_IN_BUNDLE:
            raise
        return None


def _write_bytes(path: Path, payload: bytes) -> None:
    """Replace one file so a crash cannot leave a partial PNG in its place."""
    if not path.parent.is_dir():
        raise CorpusRefusal(
            RefusalCode.STORAGE_FAILED,
            "preview cannot create its PNG because the directory does not exist",
            {"path": str(path)},
        )
    temporary = _temporary(path, payload)
    try:
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise CorpusRefusal(
            RefusalCode.STORAGE_FAILED, "preview cannot write its PNG", {"path": str(path)}
        ) from error
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _temporary(path: Path, payload: bytes) -> Path:
    """Write the PNG aside. An interrupt removes that file before the error propagates."""
    with NamedTemporaryFile(dir=path.parent, prefix=SCRATCH_PREFIX, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return temporary
