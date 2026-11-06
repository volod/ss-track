"""A small perceptual fingerprint of one stream window.

Sixteen samples, spread through the window, are each reduced to a 16 by 16 box average of
luma. Two windows are compared by the normalized correlation of those samples. The
threshold is the one measured on re-encoded fixtures and the development corpus: copies of
that footage stayed at or above 0.969 and independent windows stayed at or below 0.733.
A window with no spatial contrast correlates as zero, because a blank frame is not evidence
of one recording.
"""

from collections.abc import Sequence

import numpy as np

from ss_track.core.refusal import CorpusRefusal, RefusalCode

SAMPLE_COUNT = 16
GRID = 16
METHOD = "luma-grid-16"
SIMILARITY_THRESHOLD = 0.90
_RGB_BYTES = 3
_LUMA_RED = 54
_LUMA_GREEN = 183
_LUMA_BLUE = 19
_LUMA_SHIFT = 8
_FLAT_NORM = 1e-6

type Grid = tuple[int, ...]


def sample_indexes(start: int, end: int, count: int = SAMPLE_COUNT) -> tuple[int, ...]:
    """Return `count` frame indexes spread through the half-open window, or every frame."""
    span = end - start
    if span <= 0:
        return ()
    if span <= count:
        return tuple(range(start, end))
    return tuple(start + (2 * index + 1) * span // (2 * count) for index in range(count))


def luma_grid(rgb: bytes, width: int, height: int, grid: int = GRID) -> Grid:
    """Return one frame's box-averaged luma, row by row, each value in 0..255."""
    pixels = np.frombuffer(rgb, dtype=np.uint8)
    if width < 1 or height < 1 or pixels.size != width * height * _RGB_BYTES:
        raise CorpusRefusal(
            RefusalCode.SOURCE_UNREADABLE,
            "decoded frame has an unexpected size",
            {"width": width, "height": height, "bytes": int(pixels.size)},
        )
    image = pixels.reshape(height, width, _RGB_BYTES)
    luma = (
        image[:, :, 0].astype(np.uint16) * _LUMA_RED
        + image[:, :, 1].astype(np.uint16) * _LUMA_GREEN
        + image[:, :, 2].astype(np.uint16) * _LUMA_BLUE
    ) >> _LUMA_SHIFT
    means = np.empty((grid, grid), dtype=np.uint16)
    for row in range(grid):
        y0, y1 = _span(row, height, grid)
        for column in range(grid):
            x0, x1 = _span(column, width, grid)
            block = luma[y0:y1, x0:x1]
            means[row, column] = int(block.sum() // block.size)
    return tuple(int(value) for value in means.ravel())


def similarity(left: Sequence[Grid], right: Sequence[Grid]) -> float:
    """Return the normalized correlation of two fingerprints, or zero when either is flat.

    Windows with different sample counts are not the same frames and correlate as zero.
    """
    if len(left) != len(right) or not left:
        return 0.0
    left_values = np.asarray(left, dtype=np.float64)
    right_values = np.asarray(right, dtype=np.float64)
    if left_values.shape != right_values.shape or left_values.size == 0:
        return 0.0
    left_centered = left_values - float(left_values.mean())
    right_centered = right_values - float(right_values.mean())
    denominator = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    if denominator <= _FLAT_NORM:
        return 0.0
    correlated = float(np.dot(left_centered.ravel(), right_centered.ravel()) / denominator)
    return correlated


def _span(index: int, length: int, parts: int) -> tuple[int, int]:
    """Return one block of `length` split into `parts`, at least one pixel when it fits."""
    start = index * length // parts
    end = max((index + 1) * length // parts, start + 1)
    return start, min(end, length)
