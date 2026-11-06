"""The declared wall-clock bound on one strict decode.

The bound is not part of the decode policy, so it cannot change a pixel or a hash. It is checked
when the decode loop is in Python. A native call that never returns is outside it.
"""

import math
import time
from collections.abc import Callable

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

DECODE_LIMIT_SECONDS = 24 * 60 * 60
type Clock = Callable[[], float]


def decode_clock() -> float:
    """Return seconds from a clock that does not go backwards."""
    return time.monotonic()


class DecodeDeadline:
    """One decode's start, limit and clock."""

    def __init__(self, limit_seconds: float, clock: Clock) -> None:
        if not _positive(limit_seconds):
            raise ValueError("decode limit must be a positive finite number of seconds")
        self.limit_seconds = limit_seconds
        self._clock = clock
        self._started = clock()

    def check(self, frames_decoded: int) -> None:
        """Refuse once this decode has run longer than its limit."""
        elapsed = self._clock() - self._started
        if elapsed <= self.limit_seconds:
            return
        raise CorpusRefusal(
            RefusalCode.DECODE_TIME_EXCEEDED,
            f"decode exceeded its time limit after {_seconds(elapsed)} seconds",
            {
                "limit_seconds": _amount(self.limit_seconds),
                "elapsed_seconds": _amount(elapsed),
                "frames_decoded": frames_decoded,
            },
        )


def _positive(limit_seconds: float) -> bool:
    if isinstance(limit_seconds, bool) or not isinstance(limit_seconds, (int, float)):
        return False
    return math.isfinite(limit_seconds) and limit_seconds > 0


def _amount(value: float) -> JsonValue:
    """Store a whole number of seconds as an integer."""
    if isinstance(value, int) or float(value).is_integer():
        return int(value)
    return float(value)


def _seconds(value: float) -> str:
    """Render a duration without trailing zeros, for the refusal message."""
    amount = _amount(value)
    if isinstance(amount, int):
        return str(amount)
    return format(amount, "f").rstrip("0").rstrip(".")
