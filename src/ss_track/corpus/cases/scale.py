"""Integer area averages for whole-frame scale reduction."""

import numpy as np

from ss_track.core.refusal import JsonValue
from ss_track.corpus.cases.case_model import CaseContext, Pixels, Rendering


def scale_reduction(case: CaseContext) -> Rendering:
    """Reduce by an integer factor, including partial blocks at the right and bottom."""
    factor: int = case.parameters["factor"]
    case.require(factor >= 2, "factor must be at least 2")
    case.require(case.window == case.selection, "scale reduction requires the whole selection")
    case.require(case.width > 1 or case.height > 1, "factor changes no pixel")
    width = (case.width + factor - 1) // factor
    height = (case.height + factor - 1) // factor

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        del frame_index
        block_size = min(factor, max(case.width, case.height))
        rows = np.arange(0, case.height, block_size)
        columns = np.arange(0, case.width, block_size)
        totals = np.add.reduceat(pixels.astype(np.uint64), rows, axis=0)
        totals = np.add.reduceat(totals, columns, axis=1)
        row_sizes = np.minimum(block_size, case.height - rows)
        column_sizes = np.minimum(block_size, case.width - columns)
        counts = (row_sizes[:, None] * column_sizes[None, :])[:, :, None].astype(np.uint64)
        result: Pixels = ((totals + counts // 2) // counts).astype(np.uint8)
        return result

    labels: dict[str, JsonValue] = {"kind": "scale", "factor": factor}
    return Rendering(case.unchanged_slots(), paint, labels, output_size=(width, height))
