"""Embed staged frames with one pinned extractor and key every row by bundle, frame and frame hash.

ss-track reads each frame through its sealed index, sends it with its `FrameRef` key, and accepts a
batch only when the worker echoes exactly the keys it was sent with one finite unit row each. Before
any frame is sent, the worker's own account of what it loaded must equal the plan: the package
commit, every weight's revision, hash and size, the architecture, device type, batch size and row
length. Batches never cross a stream and always hold `batch_size` frames but a stream's last, so the
same plan sends the same batches and gets the same rows.

A tiled extractor sends square tiles cut from each frame instead (see `tiles.py`). Each tile
position is its own extractor of the run, with its own rows keyed by the frame they were cut from,
and each batch holds one tile position of `batch_size` consecutive frames.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.frames import FrameBundle, FrameRef
from ss_track.corpus.discovery.plan import EmbeddingPlan, ExtractorPlan
from ss_track.corpus.siblings.tiles import TILED, Tile, TileBox, crop
from ss_track.corpus.siblings.worker_env import require_no_checkpoint, worker_environment
from ss_track.corpus.siblings.worker_process import (
    DEFAULT_TIMEOUT_SEC,
    WorkerProcess,
    started_worker,
)

PROTOCOL = 1
PIXEL_FORMAT = "rgb24"
STAGED_FRAME = "staged_frame"
_NORM_TOLERANCE = 1e-3


@dataclass(frozen=True, slots=True)
class StreamRows:
    """One extractor's rows for one stream, in the order of their keys."""

    stream_id: str
    bundle_sha256: str
    keys: tuple[tuple[int, str], ...]  # frame index and frame hash
    vectors: bytes  # little-endian float32, one row of `dimensions` values per key


@dataclass(frozen=True, slots=True)
class ExtractorRows:
    """One run extractor's provenance as a run states it, and its rows for every stream."""

    provenance: dict[str, JsonValue]
    streams: tuple[StreamRows, ...]


def _differs(name: str, pinned: object, found: object) -> CorpusRefusal | None:
    if pinned == found:
        return None
    unpinned = name in {"package commit", "weights"}
    return CorpusRefusal(
        RefusalCode.EXTRACTOR_UNPINNED if unpinned else RefusalCode.EXTRACTOR_INCOMPATIBLE,
        f"the worker's {name} does not match the plan",
        {"pinned": _json(pinned), "found": _json(found)},
    )


def _json(value: object) -> JsonValue:
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def require_pinned(
    reported: Mapping[str, Any], embedding: EmbeddingPlan, extractor: ExtractorPlan
) -> dict[str, JsonValue]:
    """Refuse a worker that loaded anything the plan does not pin, else state its provenance."""
    package = reported["package"]
    checks = (
        ("package name", embedding.package_name, package["name"]),
        ("package commit", embedding.package_commit, package["commit"]),
        ("weights", list(extractor.weights), list(reported["weights"])),
        ("architecture", extractor.model, reported["architecture"]),
        ("device type", extractor.device, str(reported["device"]).split(":")[0]),
        ("row length", extractor.dimensions, reported["output"]["dimensions"]),
    )
    for name, pinned, found in checks:
        refusal = _differs(name, pinned, found)
        if refusal is not None:
            raise refusal
    return {
        "extractor_id": extractor.extractor_id,
        "architecture": reported["architecture"],
        "package": _json(package),
        "libraries": _json(reported["libraries"]),
        "weights": _json(reported["weights"]),
        "device": reported["device"],
        "dtype": reported["dtype"],
        "autocast": reported["autocast"],
        "batch_size": extractor.batch_size,
        "pixel_source": STAGED_FRAME,
        "preprocessing": _json(reported["preprocessing"]),
        "output": _json(reported["output"]),
    }


def embedded_frames(bundle: FrameBundle, frame_stride: int) -> list[FrameRef]:
    """Return every `frame_stride`-th frame of a bundle, from its first."""
    if bundle.pixel_format != PIXEL_FORMAT:
        raise CorpusRefusal(
            RefusalCode.EXTRACTOR_INCOMPATIBLE,
            f"the worker reads {PIXEL_FORMAT} frames",
            {"stream_id": bundle.stream_id, "pixel_format": bundle.pixel_format},
        )
    start = bundle.selection.start
    return [ref for ref in bundle.frame_refs() if (ref.frame_index - start) % frame_stride == 0]


def tiled_provenance(
    provenance: Mapping[str, Any], extractor_id: str, tile: Tile
) -> dict[str, Any]:
    """State one tile position as its own extractor, refusing an input a tile would be cropped by."""
    preprocessing = provenance["preprocessing"]
    if preprocessing["input_width"] != preprocessing["input_height"]:
        raise CorpusRefusal(
            RefusalCode.EXTRACTOR_INCOMPATIBLE,
            "a tiled extractor needs a square model input, or the embedder would crop each tile",
            {"extractor_id": extractor_id, "preprocessing": _json(preprocessing)},
        )
    tiled = {**preprocessing, "crop": TILED, "tile": tile.to_record()}
    return {**provenance, "extractor_id": extractor_id, "preprocessing": tiled}


def _batch(
    worker: WorkerProcess,
    refs: Sequence[FrameRef],
    pixels: Sequence[bytes],
    box: TileBox | None,
    dimensions: int,
) -> bytes:
    frames: list[dict[str, Any]] = []
    sent: list[bytes] = []
    for ref, frame in zip(refs, pixels, strict=True):
        pixels_sent = frame if box is None else crop(frame, ref.width, ref.height, box)
        width, height = (ref.width, ref.height) if box is None else (box.side, box.side)
        frames.append(
            {
                "frame_index": ref.frame_index,
                "sha256": ref.sha256 if box is None else sha256_bytes(pixels_sent),
                "width": width,
                "height": height,
            }
        )
        sent.append(pixels_sent)
    worker.send({"op": "embed", "frames": frames}, b"".join(sent))
    header, payload = worker.receive()
    keys = [[frame["frame_index"], frame["sha256"]] for frame in frames]
    if header.get("status") != "rows" or header.get("keys") != keys:
        raise worker.failed("the worker answered with rows for other frames than it was sent")
    if len(payload) != len(refs) * dimensions * 4:
        raise worker.failed("the worker answered with a partial batch of rows")
    rows = np.frombuffer(payload, dtype="<f4").reshape(len(refs), dimensions)
    norms = np.linalg.norm(rows.astype(np.float64), axis=1)
    if not np.isfinite(rows).all() or not all(
        math.isclose(float(norm), 1.0, abs_tol=_NORM_TOLERANCE) for norm in norms
    ):
        raise worker.failed("the worker answered with rows that are not finite unit vectors")
    return payload


def _stream_rows(
    worker: WorkerProcess, bundle: FrameBundle, extractor: ExtractorPlan, frame_stride: int
) -> list[StreamRows]:
    """Return one stream's rows of every view: the whole frame, or each tile position."""
    refs = embedded_frames(bundle, frame_stride)
    boxes = [
        None if tile is None else tile.box(bundle.width, bundle.height)
        for _, tile in extractor.views()
    ]
    vectors = [bytearray() for _ in boxes]
    size = extractor.batch_size
    for first in range(0, len(refs), size):
        chunk = refs[first : first + size]
        pixels = [bundle.read_frame(ref.frame_index) for ref in chunk]
        for rows, box in zip(vectors, boxes, strict=True):
            rows += _batch(worker, chunk, pixels, box, extractor.dimensions)
    keys = tuple((ref.frame_index, ref.sha256) for ref in refs)
    return [
        StreamRows(bundle.stream_id, bundle.bundle_sha256, keys, bytes(rows)) for rows in vectors
    ]


def embed_streams(
    embedding: EmbeddingPlan,
    extractor: ExtractorPlan,
    bundles: Sequence[FrameBundle],
    *,
    python: Path,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    environ: Mapping[str, str] | None = None,
) -> tuple[ExtractorRows, ...]:
    """Run one extractor's worker over every bundle and return the pinned rows of each view."""
    require_no_checkpoint(environ)
    with started_worker(
        python, lambda neutral: worker_environment(extractor, neutral, environ), timeout
    ) as worker:
        package = {"name": embedding.package_name, "commit": embedding.package_commit}
        worker.send({"protocol": PROTOCOL, "package": package, "extractor": extractor.to_worker()})
        header, _ = worker.receive()
        if header.get("status") != "ready" or not isinstance(header.get("provenance"), dict):
            raise worker.failed("the worker did not report what it loaded")
        try:
            provenance = require_pinned(header["provenance"], embedding, extractor)
        except (KeyError, TypeError, AttributeError) as error:
            message = f"the worker's account of what it loaded is incomplete: {error}"
            raise worker.failed(message) from error
        views = [
            provenance if tile is None else tiled_provenance(provenance, view_id, tile)
            for view_id, tile in extractor.views()
        ]
        per_stream = [
            _stream_rows(worker, bundle, extractor, embedding.frame_stride) for bundle in bundles
        ]
    return tuple(
        ExtractorRows(view, tuple(rows[position] for rows in per_stream))
        for position, view in enumerate(views)
    )
