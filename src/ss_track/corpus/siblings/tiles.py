"""Square tiles that together cover a frame, and how much of a frame a model input shows.

The ss-perception embedders scale a frame's short side to 224 pixels and keep its centre, so a 16:9
frame loses about a fifth of its width on each side and a small target shrinks with the whole frame.
A tile grid cuts each frame into `columns` by `rows` square tiles of side
`S = max(ceil(W / columns), ceil(H / rows))`, spaced evenly from the left and top edges to the right
and bottom ones, so the tiles cover the frame. A square tile passes through the embedder's centre
crop unchanged, and a target in it is `224 / S` times its frame size instead of `224 / min(W, H)`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from ss_track.core.refusal import CorpusRefusal, RefusalCode

RGB_CHANNELS = 3
TILED = "tiled"


@dataclass(frozen=True, slots=True)
class TileBox:
    """One square tile of a frame: its left and top edge and its side, in frame pixels."""

    left: int
    top: int
    side: int


@dataclass(frozen=True, slots=True)
class Tile:
    """One position of a grid, which a run states as one extractor."""

    columns: int
    rows: int
    column: int
    row: int

    def suffix(self) -> str:
        """Return the name a tile adds to its extractor's id."""
        return f"r{self.row}c{self.column}"

    def to_record(self) -> dict[str, int]:
        """Return the tile as a run's extractor preprocessing states it."""
        return {"columns": self.columns, "rows": self.rows, "column": self.column, "row": self.row}

    def box(self, width: int, height: int) -> TileBox:
        """Place this tile on a frame, refusing a grid whose square tiles do not fit it."""
        side = max(-(-width // self.columns), -(-height // self.rows))
        if side > min(width, height):
            raise CorpusRefusal(
                RefusalCode.EXTRACTOR_INCOMPATIBLE,
                "the tile grid needs square tiles larger than the frame's shorter side",
                {"width": width, "height": height, "columns": self.columns, "rows": self.rows},
            )
        return TileBox(
            _edge(self.column, self.columns, width - side),
            _edge(self.row, self.rows, height - side),
            side,
        )


def _edge(index: int, count: int, room: int) -> int:
    return 0 if count == 1 else index * room // (count - 1)


def grid(columns: int, rows: int) -> tuple[Tile, ...]:
    """Return every tile of a grid, row by row."""
    return tuple(
        Tile(columns, rows, column, row) for row in range(rows) for column in range(columns)
    )


def crop(pixels: bytes, width: int, height: int, box: TileBox) -> bytes:
    """Cut one tile out of a packed RGB frame, as packed RGB."""
    frame = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, RGB_CHANNELS)
    window = frame[box.top : box.top + box.side, box.left : box.left + box.side]
    return np.ascontiguousarray(window).tobytes()


def coverage(preprocessing: Mapping[str, Any], width: int, height: int) -> tuple[float, float]:
    """Return the share of a frame's area a model input shows, and its pixels per frame pixel."""
    input_width, input_height = preprocessing["input_width"], preprocessing["input_height"]
    tile = preprocessing.get("tile")
    if tile is not None:
        box = Tile(**tile).box(width, height)
        return box.side * box.side / (width * height), input_width / box.side
    resize = preprocessing["resize"]
    if resize == "exact":
        return 1.0, min(input_width / width, input_height / height)
    scale = input_width / min(width, height) if resize == "short_side" else 1.0
    if preprocessing["crop"] != "center":
        return 1.0, scale
    shown = min(width, input_width / scale) * min(height, input_height / scale)
    return min(1.0, shown / (width * height)), scale
