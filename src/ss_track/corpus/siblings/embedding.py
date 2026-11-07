"""Embed staged frames with one pinned extractor and key every row by bundle, frame and frame hash.

ss-track reads each frame through its sealed index, sends it with its `FrameRef` key, and accepts a
batch only when the worker echoes exactly the keys it was sent with one finite unit row each. Before
any frame is sent, the worker's own account of what it loaded must equal the plan: the package
commit, every weight's revision, hash and size, the architecture, device type, batch size and row
length. Batches never cross a stream and always hold `batch_size` frames but a stream's last, so the
same plan sends the same batches and gets the same rows.
"""

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.frames import FrameBundle, FrameRef
from ss_track.corpus.discovery.plan import EmbeddingPlan, ExtractorPlan
from ss_track.corpus.siblings.worker_process import (
    DEFAULT_TIMEOUT_SEC,
    WorkerProcess,
    started_worker,
)

PROTOCOL = 1
PYTHON_VARIABLE = "SST_PERCEPTION_PYTHON"
PIXEL_FORMAT = "rgb24"
STAGED_FRAME = "staged_frame"
_NORM_TOLERANCE = 1e-3
# Forwarded so the worker finds its caches and devices; nothing else of this process reaches it.
_FORWARDED = ("PATH", "HOME", "HF_HOME", "HF_HUB_CACHE", "TORCH_HOME", "XDG_CACHE_HOME")
_FORWARDED_DEVICES = ("CUDA_VISIBLE_DEVICES",)
_CHECKPOINT_VARIABLE = "DINO_CHECKPOINT"


@dataclass(frozen=True, slots=True)
class StreamRows:
    """One extractor's rows for one stream, in the order of their keys."""

    stream_id: str
    bundle_sha256: str
    keys: tuple[tuple[int, str], ...]  # frame index and frame hash
    vectors: bytes  # little-endian float32, one row of `dimensions` values per key


@dataclass(frozen=True, slots=True)
class ExtractorRows:
    """An extractor's provenance as a run states it, and its rows for every stream."""

    provenance: dict[str, JsonValue]
    streams: tuple[StreamRows, ...]


def worker_python(environ: Mapping[str, str] | None = None) -> Path:
    """Return the pinned environment's interpreter, which the operator names, never a default."""
    found = (os.environ if environ is None else environ).get(PYTHON_VARIABLE)
    if not found:
        raise CorpusRefusal(
            RefusalCode.WORKER_FAILED,
            f"set {PYTHON_VARIABLE} to the Python of the pinned ss-perception environment",
            {"variable": PYTHON_VARIABLE},
        )
    return Path(found)


def require_no_checkpoint(environ: Mapping[str, str] | None = None) -> None:
    """Refuse a configured adapted checkpoint, which the worker would otherwise never see."""
    found = (os.environ if environ is None else environ).get(_CHECKPOINT_VARIABLE)
    if found:
        raise CorpusRefusal(
            RefusalCode.EXTRACTOR_UNPINNED,
            f"{_CHECKPOINT_VARIABLE} is set; adapted checkpoints carry no training-source manifest",
            {"variable": _CHECKPOINT_VARIABLE},
        )


def worker_environment(
    extractor: ExtractorPlan, neutral: Path, environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Build the worker's whole environment: caches offline, settings explicit, data dir empty."""
    source = os.environ if environ is None else environ
    forwarded = {key: source[key] for key in (*_FORWARDED, *_FORWARDED_DEVICES) if key in source}
    settings = {
        "APP_ENV": "dev",
        "DATA_DIR": str(neutral),
        "SUP_CHECKPOINT_DIR": str(neutral / "checkpoints"),
        _CHECKPOINT_VARIABLE: "",
        "DEVICE": extractor.device,
        "USE_FP16": "false",
        "OPENCLIP_MODEL": extractor.model,
        "OPENCLIP_PRETRAINED": extractor.pretrained or "",
    }
    quiet = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "TQDM_DISABLE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
    }
    return forwarded | settings | quiet


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


def _batch(
    worker: WorkerProcess, bundle: FrameBundle, refs: Sequence[FrameRef], dimensions: int
) -> bytes:
    frames = [
        {
            "frame_index": ref.frame_index,
            "sha256": ref.sha256,
            "width": ref.width,
            "height": ref.height,
        }
        for ref in refs
    ]
    worker.send(
        {"op": "embed", "frames": frames},
        b"".join(map(bundle.read_frame, (r.frame_index for r in refs))),
    )
    header, payload = worker.receive()
    sent = [[ref.frame_index, ref.sha256] for ref in refs]
    if header.get("status") != "rows" or header.get("keys") != sent:
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
) -> StreamRows:
    refs = embedded_frames(bundle, frame_stride)
    size = extractor.batch_size
    vectors = b"".join(
        _batch(worker, bundle, refs[first : first + size], extractor.dimensions)
        for first in range(0, len(refs), size)
    )
    keys = tuple((ref.frame_index, ref.sha256) for ref in refs)
    return StreamRows(bundle.stream_id, bundle.bundle_sha256, keys, vectors)


def embed_streams(
    embedding: EmbeddingPlan,
    extractor: ExtractorPlan,
    bundles: Sequence[FrameBundle],
    *,
    python: Path,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    environ: Mapping[str, str] | None = None,
) -> ExtractorRows:
    """Run one extractor's worker over every bundle and return its pinned rows."""
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
        streams = tuple(
            _stream_rows(worker, bundle, extractor, embedding.frame_stride) for bundle in bundles
        )
    return ExtractorRows(provenance, streams)
