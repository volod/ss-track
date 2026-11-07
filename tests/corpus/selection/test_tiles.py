"""Square tiles cover a frame, and coverage states what a model input shows of it."""

import math

import numpy as np
import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.siblings.embedding import tiled_provenance
from ss_track.corpus.siblings.tiles import Tile, coverage, crop, grid

CENTRE = {
    "resize": "short_side",
    "crop": "center",
    "input_width": 224,
    "input_height": 224,
}


def test_a_grid_of_square_tiles_covers_a_wide_frame_edge_to_edge() -> None:
    boxes = [tile.box(1920, 1080) for tile in grid(4, 2)]

    assert {box.side for box in boxes} == {540}
    assert [box.left for box in boxes[:4]] == [0, 460, 920, 1380]
    assert [box.top for box in boxes[::4]] == [0, 540]
    covered = np.zeros((1080, 1920), dtype=bool)
    for box in boxes:
        covered[box.top : box.top + box.side, box.left : box.left + box.side] = True
    assert covered.all()


def test_one_column_or_row_places_its_tile_at_the_edge() -> None:
    box = Tile(1, 2, 0, 1).box(48, 64)
    assert (box.left, box.top, box.side) == (0, 16, 48)


def test_a_grid_whose_tiles_exceed_the_short_side_is_refused() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        Tile(1, 1, 0, 0).box(64, 48)

    assert caught.value.code is RefusalCode.EXTRACTOR_INCOMPATIBLE


def test_a_tile_is_cut_from_the_packed_frame() -> None:
    frame = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
    box = Tile(2, 1, 1, 0).box(6, 4)

    tile = crop(frame.tobytes(), 6, 4, box)

    assert (box.left, box.side) == (2, 4)
    assert tile == frame[0:4, 2:6].tobytes()


def test_coverage_states_the_centre_crop_loss_and_the_tile_scale() -> None:
    fraction, scale = coverage(CENTRE, 1920, 1080)
    assert math.isclose(fraction, 1080 / 1920) and math.isclose(scale, 224 / 1080)

    tiled = CENTRE | {"crop": "tiled", "tile": {"columns": 4, "rows": 2, "column": 3, "row": 1}}
    fraction, scale = coverage(tiled, 1920, 1080)
    assert math.isclose(fraction, 540 * 540 / (1920 * 1080)) and math.isclose(scale, 224 / 540)

    assert coverage(CENTRE | {"crop": "none"}, 1920, 1080) == (1.0, 224 / 1080)
    assert coverage(CENTRE | {"resize": "exact"}, 448, 224) == (1.0, 0.5)
    assert coverage(CENTRE | {"resize": "none"}, 448, 224) == (0.5, 1.0)


def test_a_tile_names_its_row_then_column() -> None:
    assert [tile.suffix() for tile in grid(2, 2)] == ["r0c0", "r0c1", "r1c0", "r1c1"]


def test_a_tile_of_a_rectangular_model_input_would_be_cropped_and_is_refused() -> None:
    provenance = {"extractor_id": "clip", "preprocessing": CENTRE | {"input_width": 336}}

    with pytest.raises(CorpusRefusal) as caught:
        tiled_provenance(provenance, "clip.r0c0", Tile(2, 1, 0, 0))

    assert caught.value.code is RefusalCode.EXTRACTOR_INCOMPATIBLE
    square = tiled_provenance(
        {"extractor_id": "clip", "preprocessing": CENTRE}, "clip.r0c1", Tile(2, 1, 1, 0)
    )
    assert square["extractor_id"] == "clip.r0c1" and square["preprocessing"]["crop"] == "tiled"
