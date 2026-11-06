"""Compression and variable frame timing: the section 4.3 cases that need no labels.

Pixel work is integer arithmetic, so a CPU or a NumPy build cannot move it. Revision 1 of
`compression` is the encoder `block-quant-rgb24-v1`: each block becomes its average, quantized to
a step the seed draws. Another encoder, or another block size, is another revision. Variable
timing keeps every pixel and stretches presentation intervals. A parent with a missing
presentation time cannot take that case, and the case's own time is `derived`.
"""

import numpy as np

from ss_track.core.refusal import JsonValue
from ss_track.corpus.cases.case_model import CaseContext, Pixels, Rendering
from ss_track.corpus.sources.timestamps import TimestampQuality

COMPRESSION_ENCODER = "block-quant-rgb24-v1"
COMPRESSION_BLOCK = 8
_MAX_COMPONENT = 255
_MIN_STEP = 1
_MAX_STEP = 255
_MIN_SCALE = 2
_MAX_SCALE = 16
_STORED_TIME = frozenset({TimestampQuality.MEASURED.value, TimestampQuality.DERIVED.value})


def compression(case: CaseContext) -> Rendering:
    """Flatten each block to its quantized average, the blocking of heavy compression."""
    max_step = _bounded(case, "max_step", _MIN_STEP, _MAX_STEP)
    steps = {
        index: case.draws.integers(f"step:{index}", 1, _MIN_STEP, max_step)[0]
        for index in case.window
    }

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        return _quantize_blocks(pixels, steps[frame_index])

    labels: dict[str, JsonValue] = {
        "kind": "compression",
        "encoder": COMPRESSION_ENCODER,
        "block": COMPRESSION_BLOCK,
        "steps": [{"frame_index": index, "step": step} for index, step in steps.items()],
    }
    return Rendering(case.unchanged_slots(), paint, labels)


def variable_timing(case: CaseContext) -> Rendering:
    """Stretch presentation intervals inside the window. Pixels stay the parent's."""
    max_scale = _bounded(case, "max_scale", _MIN_SCALE, _MAX_SCALE)
    case.require(
        case.timestamp_quality in _STORED_TIME,
        "variable timing needs a presentation time on every frame",
    )
    later = [index for index in case.window if index > case.selection.start]
    case.require(bool(later), "window changes no presentation interval")
    gaps = tuple(
        (index, case.draws.integers(f"scale:{index}", 1, _MIN_SCALE, max_scale)[0])
        for index in later
    )
    labels: dict[str, JsonValue] = {
        "kind": "timing",
        "timestamp_quality": TimestampQuality.DERIVED.value,
        "gaps": [{"frame_index": index, "scale": scale} for index, scale in gaps],
    }
    return Rendering(case.unchanged_slots(), None, labels, gaps)


def _bounded(case: CaseContext, name: str, lowest: int, highest: int) -> int:
    value: int = case.parameters[name]
    case.require(lowest <= value <= highest, f"{name} is outside {lowest} to {highest}")
    return value


def _quantize_blocks(pixels: Pixels, step: int) -> Pixels:
    """Replace every block with one quantized color. A leftover edge is its own block."""
    result = pixels.astype(np.int32)
    height, width = result.shape[:2]
    core_h = height // COMPRESSION_BLOCK * COMPRESSION_BLOCK
    core_w = width // COMPRESSION_BLOCK * COMPRESSION_BLOCK
    if core_h and core_w:
        _fill_grid(result[:core_h, :core_w], step)
    if core_w < width:
        _fill_strip(result[:, core_w:], step)
    if core_h < height and core_w:
        _fill_strip(result[core_h:, :core_w], step)
    quantized: Pixels = result.astype(np.uint8)
    return quantized


def _fill_grid(core: np.ndarray, step: int) -> None:
    block = COMPRESSION_BLOCK
    packed = np.ascontiguousarray(core)
    tiles_y, tiles_x = packed.shape[0] // block, packed.shape[1] // block
    tiles = packed.reshape(tiles_y, block, tiles_x, block, packed.shape[2])
    mean = tiles.sum(axis=(1, 3)) // (block * block)
    tiles[:] = _quantized(mean, step)[:, None, :, None, :]
    core[:] = packed


def _fill_strip(rect: np.ndarray, step: int) -> None:
    """Average a leftover edge. The short side is one tile, so the loop stays on the edge."""
    height, width = rect.shape[:2]
    tile_h, tile_w = min(COMPRESSION_BLOCK, height), min(COMPRESSION_BLOCK, width)
    for y in range(0, height, tile_h):
        for x in range(0, width, tile_w):
            _fill_mean(rect[y : y + tile_h, x : x + tile_w], step)


def _fill_mean(rect: np.ndarray, step: int) -> None:
    count = rect.shape[0] * rect.shape[1]
    mean = rect.reshape(-1, rect.shape[2]).sum(axis=0) // count
    rect[:] = _quantized(mean, step)


def _quantized(mean: np.ndarray, step: int) -> np.ndarray:
    rounded = (mean + step // 2) // step * step
    bounded = np.minimum(np.maximum(rounded, 0), _MAX_COMPONENT)
    return np.asarray(bounded)
