"""The slot rule reproduces how ss-video's ffmpeg sampling labels source frames.

The 30 frame per second case is the one the sibling study measured on ffmpeg 8.0.1 at five samples
per second: sample k showed frame 6k + 2, because a slot shows the last frame that falls in it.
"""

from fractions import Fraction

import pytest

from ss_track.corpus.siblings.slots import (
    EMPTY_SLOT,
    SLOT_OUT_OF_RANGE,
    parse_rational,
    slot_at,
    slot_windows,
)

FIVE = Fraction(5)
MILLISECOND = Fraction(1, 1000)


def _shown(windows: dict[int, tuple[int, int]]) -> dict[int, int]:
    """The frame each sample shows: the last of its slot."""
    return {slot: end - 1 for slot, (_, end) in windows.items()}


def test_a_constant_rate_source_matches_the_measured_samples() -> None:
    pts = list(range(120))  # 30 frames per second, time base 1/30

    slots = slot_windows(pts, Fraction(1, 30), FIVE)

    assert slots.windows[0] == (0, 3) and slots.windows[1] == (3, 9)
    assert all(_shown(slots.windows)[k] == 6 * k + 2 for k in range(19))
    assert slots.last_slot == 20  # frames 117 to 119 round up into slot 20


def test_a_start_offset_counts_from_the_first_frame() -> None:
    offset = [1500 + round(index * 1000 / 30) for index in range(30)]
    plain = [round(index * 1000 / 30) for index in range(30)]

    assert slot_windows(offset, MILLISECOND, FIVE) == slot_windows(plain, MILLISECOND, FIVE)


def test_a_source_slower_than_the_rate_leaves_empty_slots() -> None:
    pts = list(range(16))  # 4 frames per second, time base 1/4

    slots = slot_windows(pts, Fraction(1, 4), FIVE)

    assert slots.window(0) == (0, 1) and slots.window(3) == (2, 3)
    assert slots.window(2) == EMPTY_SLOT  # ffmpeg repeats frame 1 there
    assert slots.window(19) == (15, 16)
    assert slots.window(20) == SLOT_OUT_OF_RANGE
    assert len(slots.windows) == 16  # every frame shows once; four slots repeat a frame


def test_a_variable_rate_source_groups_frames_by_presentation_time() -> None:
    pts = [0, 40, 80, 300, 310, 320, 900, 1000]  # milliseconds

    slots = slot_windows(pts, MILLISECOND, FIVE)

    # Slot k holds times from (k - 1/2) / 5 s: 0 to 100 ms, 300 to 500 ms, 900 to 1100 ms.
    assert slots.windows == {0: (0, 3), 2: (3, 6), 5: (6, 8)}
    assert slots.window(1) == EMPTY_SLOT and slots.window(4) == EMPTY_SLOT


def test_a_frame_on_a_slot_boundary_rounds_up_exactly() -> None:
    # 100 ms is exactly half a slot at five per second; float arithmetic could drop it a slot.
    slots = slot_windows([0, 100, 300], MILLISECOND, FIVE)

    assert slots.windows == {0: (0, 1), 1: (1, 2), 2: (2, 3)}


@pytest.mark.parametrize(
    ("t_sec", "slot"),
    [(0.0, 0), (0.6, 3), (7 / 5, 7), (0.61, None), (-0.2, None)],
)
def test_a_sibling_time_names_a_whole_sample_or_nothing(t_sec: float, slot: int | None) -> None:
    assert slot_at(t_sec, FIVE) == slot


def test_rates_are_read_as_exact_rationals() -> None:
    assert parse_rational("30000/1001") == Fraction(30000, 1001)
