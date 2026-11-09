"""The motion score: the largest local change in brightness between consecutive frames of a window.

A small bird moving across a still sky changes a few pixels, so the mean change over a whole frame
hides it. Each frame is cut into 16 by 16 pixel blocks, partial ones at the right and bottom edges
included, and a pair of consecutive frames scores the mean absolute luma change of its most changed
block. A window scores its most changed pair. Luma is BT.601 in integer thousandths and every block
sum is an integer, so the score is the same on any machine.
"""

import multiprocessing
import os
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait

import numpy as np

from ss_track.core.motion_resources import (
    RESERVE_BYTES,
    HostResources,
    choose_workers,
    host_resources,
    requested_workers,
    restrict_worker_cpus,
    worker_memory,
)
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.frames import FrameBundle

BLOCK_PIXELS = 16
_LUMA_WEIGHTS = np.array([299, 587, 114], dtype=np.int64)
_LUMA_SCALE = 1000  # weights sum to 1000, so luma is in thousandths of an 8-bit level
_RGB = 3


def _luma(pixels: bytes, width: int, height: int) -> np.ndarray:
    frame = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, _RGB)
    luma: np.ndarray = frame.astype(np.int64) @ _LUMA_WEIGHTS
    return luma


def _block_change(previous: np.ndarray, current: np.ndarray) -> float:
    change = np.abs(current - previous)
    height, width = change.shape
    rows = np.arange(0, height, BLOCK_PIXELS)
    columns = np.arange(0, width, BLOCK_PIXELS)
    sums = np.add.reduceat(np.add.reduceat(change, rows, axis=0), columns, axis=1)
    counts = np.outer(np.diff(np.append(rows, height)), np.diff(np.append(columns, width)))
    return float((sums / (counts * _LUMA_SCALE)).max())


def pair_changes(bundle: FrameBundle) -> dict[int, float]:
    """Return each frame's change from the frame before it, keyed by the later frame's index."""
    changes: dict[int, float] = {}
    previous: np.ndarray | None = None
    for ref in bundle.frame_refs():
        current = _luma(bundle.read_frame(ref.frame_index), ref.width, ref.height)
        if previous is not None:
            changes[ref.frame_index] = _block_change(previous, current)
        previous = current
    return changes


def window_motion(changes: Mapping[int, float], start: int, end: int) -> float | None:
    """Return a window's motion, or None for a window of one frame, which has no pair."""
    pairs: Sequence[float] = [changes[index] for index in range(start + 1, end)]
    return max(pairs) if pairs else None


def _worker(bundle: FrameBundle) -> tuple[dict[int, float] | None, dict[str, JsonValue] | None]:
    try:
        return pair_changes(bundle), None
    except CorpusRefusal as error:
        return None, error.to_record()


def _require_memory(host: HostResources, per_worker: int) -> None:
    if host.available_bytes is not None and host.available_bytes < per_worker:
        raise CorpusRefusal(
            RefusalCode.WORKER_FAILED,
            "insufficient available memory for motion scoring",
            {"available_bytes": host.available_bytes, "estimated_worker_bytes": per_worker},
        )


def _capacity(limit: int, requested: int | None, active: int, per_worker: int) -> int:
    host = host_resources()
    if host.cpu_count is None or host.available_bytes is None:
        return 1
    if active == 0:
        _require_memory(host, per_worker)
    spare = max(0, (host.available_bytes - RESERVE_BYTES) // per_worker)
    return max(1, min(limit, requested or limit, max(1, host.cpu_count // 2), active + spare))


def _result(
    future: Future[tuple[dict[int, float] | None, dict[str, JsonValue] | None]],
) -> dict[int, float]:
    try:
        changes, refusal = future.result()
    except OSError:
        raise
    except Exception as error:
        raise CorpusRefusal(RefusalCode.WORKER_FAILED, "motion worker failed") from error
    if refusal is not None:
        raise CorpusRefusal(
            RefusalCode(str(refusal["code"])),
            str(refusal["message"]),
            refusal["details"] if isinstance(refusal["details"], dict) else {},
        )
    assert changes is not None
    return changes


def _parallel_changes(
    bundles: Sequence[FrameBundle], limit: int, requested: int | None, per_worker: int
) -> dict[str, dict[int, float]]:
    cpus = tuple(sorted(os.sched_getaffinity(0))[:limit])
    results: dict[str, dict[int, float]] = {}
    pending: dict[Future[tuple[dict[int, float] | None, dict[str, JsonValue] | None]], str] = {}
    index = 0
    with ProcessPoolExecutor(
        max_workers=limit,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=restrict_worker_cpus,
        initargs=(cpus,),
    ) as pool:
        while index < len(bundles) or pending:
            capacity = _capacity(limit, requested, len(pending), per_worker)
            while index < len(bundles) and len(pending) < capacity:
                bundle = bundles[index]
                pending[pool.submit(_worker, bundle)] = bundle.stream_id
                index += 1
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                results[pending.pop(future)] = _result(future)
    return {bundle.stream_id: results[bundle.stream_id] for bundle in bundles}


def stream_changes(bundles: Iterable[FrameBundle]) -> dict[str, dict[int, float]]:
    """Return frame changes, using bounded host-aware processes across streams."""
    streams = list(bundles)
    requested = requested_workers(os.environ.get("SST_MOTION_WORKERS"))
    per_worker = max((worker_memory(b.width, b.height) for b in streams), default=1)
    host = host_resources()
    if streams:
        _require_memory(host, per_worker)
    limit = choose_workers(host, len(streams), requested, per_worker)
    if limit <= 1:
        return {bundle.stream_id: pair_changes(bundle) for bundle in streams}
    return _parallel_changes(streams, limit, requested, per_worker)
