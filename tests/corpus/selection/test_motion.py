"""Motion scores the most changed block, so a tiny target at the frame edge is not averaged away."""

from dataclasses import dataclass

import numpy as np

from ss_track.corpus.selection.motion import pair_changes, window_motion

WIDTH, HEIGHT = 40, 24


@dataclass(frozen=True)
class _Ref:
    frame_index: int
    width: int = WIDTH
    height: int = HEIGHT


class _Bundle:
    """Just the frame reads `pair_changes` makes."""

    stream_id = "one"

    def __init__(self, frames: list[np.ndarray]) -> None:
        self.frames = frames

    def frame_refs(self) -> list[_Ref]:
        return [_Ref(index) for index in range(len(self.frames))]

    def read_frame(self, frame_index: int) -> bytes:
        return self.frames[frame_index].tobytes()


def _sky() -> np.ndarray:
    return np.full((HEIGHT, WIDTH, 3), 200, dtype=np.uint8)


def test_a_two_pixel_target_in_a_partial_edge_block_is_its_whole_block_change() -> None:
    moved = _sky()
    moved[20:22, 38:40] = 0  # inside the 8 by 8 block at the bottom-right corner
    changes = pair_changes(_Bundle([_sky(), moved, moved]))  # type: ignore[arg-type]

    assert changes == {1: 4 * 200 / 64, 2: 0.0}
    whole_frame = 4 * 200 / (WIDTH * HEIGHT)
    assert changes[1] > 10 * whole_frame


def test_a_window_scores_its_most_changed_pair_and_one_frame_scores_nothing() -> None:
    changes = {1: 3.0, 2: 9.5, 3: 0.5}

    assert window_motion(changes, 0, 4) == 9.5
    assert window_motion(changes, 2, 4) == 0.5
    assert window_motion(changes, 3, 4) is None
