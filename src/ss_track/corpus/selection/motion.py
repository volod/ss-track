"""The motion score: the largest local change in brightness between consecutive frames of a window.

A small bird moving across a still sky changes a few pixels, so the mean change over a whole frame
hides it. Each frame is cut into 16 by 16 pixel blocks, partial ones at the right and bottom edges
included, and a pair of consecutive frames scores the mean absolute luma change of its most changed
block. A window scores its most changed pair. Luma is BT.601 in integer thousandths and every block
sum is an integer, so the score is the same on any machine.
"""

from collections.abc import Iterable, Mapping, Sequence

import numpy as np

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


def stream_changes(bundles: Iterable[FrameBundle]) -> dict[str, dict[int, float]]:
    """Return every stream's frame changes, reading each staged frame once."""
    return {bundle.stream_id: pair_changes(bundle) for bundle in bundles}
