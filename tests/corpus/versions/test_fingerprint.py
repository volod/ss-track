"""The perceptual fingerprint, without a container."""

import pytest

from ss_track.core.refusal import RefusalCode
from ss_track.corpus import CorpusRefusal
from ss_track.corpus.versions.fingerprint import (
    SIMILARITY_THRESHOLD,
    luma_grid,
    sample_indexes,
    similarity,
)


def test_samples_cover_a_short_window_and_spread_through_a_long_one() -> None:
    assert sample_indexes(4, 8, count=16) == (4, 5, 6, 7)
    assert sample_indexes(0, 0) == ()
    spread = sample_indexes(0, 160)
    assert spread[0] > 0
    assert spread[-1] < 160
    assert len(spread) == len(set(spread)) == 16


def test_identical_grids_correlate_and_a_flat_grid_does_not() -> None:
    bright = tuple(range(256))
    dark = tuple(255 - value for value in bright)

    assert similarity((bright,), (bright,)) == 1.0
    assert similarity((bright,), (dark,)) == -1.0
    assert similarity((bright,), (bright, bright)) == 0.0
    assert similarity(((128,) * 256,), ((40,) * 256,)) == 0.0
    assert similarity((), ()) == 0.0
    assert -1.0 < SIMILARITY_THRESHOLD < 1.0


def test_a_short_buffer_and_uneven_grids_are_not_a_match() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        luma_grid(b"123", 2, 2)
    assert caught.value.code is RefusalCode.SOURCE_UNREADABLE
    assert similarity(((1, 2, 3),), ((1, 2),)) == 0.0


def test_a_decoded_frame_keeps_a_coarse_gradient() -> None:
    width, height = 32, 16
    rgb = b"".join(bytes((x * 8, 0, 0)) for _y in range(height) for x in range(width))

    grid = luma_grid(rgb, width, height, grid=4)

    assert len(grid) == 16
    assert grid[0] < grid[3]
    assert grid[0] == grid[4]
