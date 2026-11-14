"""The slot rule: which source frames an ss-video sample time names.

ss-video samples a source with ffmpeg's `fps` filter and labels sample `k` as `k / rate` seconds.
The sibling integration study (`docs/impl/current/corpus/sibling-integration.md`) reproduced every
sample with one rule: frame `f` falls in slot `floor((pts_f - pts_0) * rate + 1/2)`, a slot shows
the last frame that falls in it, and an empty slot repeats the previous one. A slot therefore names
a window of source frames, never one frame, and only under a recorded ffmpeg version and rate. The
arithmetic is exact, so a frame on a slot boundary lands where ffmpeg puts it.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

_HALF = Fraction(1, 2)
# ss-video writes `k / rate` as a float, so a whole slot comes back within this of an integer.
SLOT_TOLERANCE = 1e-6

EMPTY_SLOT = "empty_slot"
SLOT_OUT_OF_RANGE = "slot_out_of_range"
NOT_ON_SLOT = "not_on_slot"


def parse_rational(text: str) -> Fraction:
    """Read a `numerator/denominator` rate or time base, as the contracts state them."""
    numerator, denominator = text.split("/")
    return Fraction(int(numerator), int(denominator))


@dataclass(frozen=True, slots=True)
class SlotWindows:
    """The source frames of each non-empty slot, as half-open source frame windows."""

    windows: dict[int, tuple[int, int]]
    last_slot: int

    def window(self, slot: int) -> tuple[int, int] | str:
        """Return a slot's window, or why it names no frame."""
        found = self.windows.get(slot)
        if found is not None:
            return found
        return SLOT_OUT_OF_RANGE if slot > self.last_slot else EMPTY_SLOT


def slot_of(pts: int, first_pts: int, time_base: Fraction, rate: Fraction) -> int:
    """Return the slot a frame falls in."""
    return math.floor((pts - first_pts) * time_base * rate + _HALF)


def slot_windows(pts: Sequence[int], time_base: Fraction, rate: Fraction) -> SlotWindows:
    """Group a whole source's frames, in presentation order, into the slots they fall in.

    PTS strictly increase, which the import enforces, so each slot's frames are contiguous.
    """
    windows: dict[int, tuple[int, int]] = {}
    slot = -1
    for index, value in enumerate(pts):
        slot = slot_of(value, pts[0], time_base, rate)
        first = windows.get(slot, (index, index))[0]
        windows[slot] = (first, index + 1)
    return SlotWindows(windows, slot)


def slot_at(t_sec: float, rate: Fraction) -> int | None:
    """Return the slot a sibling time labels, or None when it lies between two samples."""
    exact = t_sec * rate.numerator / rate.denominator
    nearest = round(exact)
    if nearest < 0 or abs(exact - nearest) > SLOT_TOLERANCE:
        return None
    return nearest
