"""Hand-checkable frames and recipes for testing transforms with no codec or data root."""

import numpy as np

from ss_track.corpus.case_model import Pixels, Rendering
from ss_track.corpus.transforms import prepare_case

WIDTH = 16
HEIGHT = 12
FRAMES = 10
LEVELS = 256


def frame(index: int) -> Pixels:
    """Return one frame whose every pixel differs from its neighbors and from other frames."""
    rows, columns = np.mgrid[0:HEIGHT, 0:WIDTH]
    red = (columns * 13 + index * 3) % LEVELS
    green = (rows * 17 + index * 5) % LEVELS
    blue = (rows * columns + index * 7) % LEVELS
    return np.stack((red, green, blue), axis=-1).astype(np.uint8)


def case_record(
    transform: str, parameters: dict[str, object], **fields: object
) -> dict[str, object]:
    return {
        "case_id": "case",
        "transform": transform,
        "seed": 11,
        "window": {"start_frame": 0, "end_frame": FRAMES},
        "parameters": parameters,
    } | fields


def prepare(record: dict[str, object], selection: range = range(FRAMES)) -> Rendering:
    return prepare_case(record, selection, WIDTH, HEIGHT, frame)


def painted(rendering: Rendering, index: int) -> Pixels:
    assert rendering.paint is not None
    return rendering.paint(frame(index), index)


def window(start: int, end: int) -> dict[str, int]:
    return {"start_frame": start, "end_frame": end}


REGION = {"x": 4, "y": 2, "width": 6, "height": 5}


def inside(pixels: Pixels) -> Pixels:
    return pixels[2:7, 4:10]


def outside_mask() -> Pixels:
    mask = np.ones((HEIGHT, WIDTH), dtype=bool)
    mask[2:7, 4:10] = False
    return mask
