"""Integer area averages for whole-frame scale reduction.

Integer arithmetic keeps one recipe's bytes identical on every architecture. A 64-bit block sum
cannot overflow for any frame a decoder gives; a narrower one would need a bound on the factor.
"""

import numpy as np

from ss_track.core.refusal import JsonValue
from ss_track.corpus.cases.case_model import CaseContext, Pixels, Rendering

SCALE_REDUCTION = "scale_reduction"


def reduced_size(width: int, height: int, factor: int) -> tuple[int, int]:
    """Return the frame size a reduction gives: each dimension divided by `factor`, rounded up."""
    return -(-width // factor), -(-height // factor)


def scale_reduction(case: CaseContext) -> Rendering:
    """Reduce by an integer factor, including partial blocks at the right and bottom."""
    factor: int = case.parameters["factor"]
    case.require(factor >= 2, "factor must be at least 2")
    case.require(case.window == case.selection, "scale reduction requires the whole selection")
    case.require(case.width > 1 or case.height > 1, "factor changes no pixel")
    rows = np.arange(0, case.height, factor)
    columns = np.arange(0, case.width, factor)
    row_sizes = np.minimum(factor, case.height - rows)
    column_sizes = np.minimum(factor, case.width - columns)
    counts = (row_sizes[:, None] * column_sizes[None, :])[:, :, None].astype(np.uint64)

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        del frame_index
        totals = np.add.reduceat(pixels.astype(np.uint64), rows, axis=0)
        totals = np.add.reduceat(totals, columns, axis=1)
        result: Pixels = ((totals + counts // 2) // counts).astype(np.uint8)
        return result

    labels: dict[str, JsonValue] = {"kind": "scale", "factor": factor}
    output_size = reduced_size(case.width, case.height, factor)
    return Rendering(case.unchanged_slots(), paint, labels, output_size=output_size)
