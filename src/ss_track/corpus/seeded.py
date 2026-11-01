"""Every random value of a generated case, derived by hash from its seed.

`random` and NumPy's generators may change their streams between releases, and a generated case must
stay byte-identical. SHAKE-256 is a published standard with no such freedom, so one seed gives the
same draws under any Python, NumPy or CPU, and each purpose gets an independent stream.
"""

from collections.abc import Iterable
from hashlib import shake_256

_INTEGER_BYTES = 8
_SEPARATOR = "/"


class SeededDraws:
    """Independent named streams of deterministic values for one transform and seed."""

    def __init__(self, transform: str, seed: int) -> None:
        self._prefix = f"{transform}{_SEPARATOR}{seed}{_SEPARATOR}"

    def raw(self, purpose: str, size: int) -> bytes:
        """Return `size` bytes of one purpose's stream."""
        return shake_256(f"{self._prefix}{purpose}".encode("ascii")).digest(size)

    def integers(self, purpose: str, count: int, low: int, high: int) -> list[int]:
        """Return `count` integers in `[low, high]`. Modulo bias at 64 bits is negligible here."""
        data = self.raw(purpose, count * _INTEGER_BYTES)
        span = high - low + 1
        return [
            low + int.from_bytes(data[start : start + _INTEGER_BYTES]) % span
            for start in range(0, len(data), _INTEGER_BYTES)
        ]

    def pick(self, purpose: str, candidates: Iterable[int], count: int) -> list[int]:
        """Return `count` distinct candidates, each ranked by its own hash."""
        ranked = sorted(
            candidates, key=lambda value: self.raw(f"{purpose}:{value}", _INTEGER_BYTES)
        )
        return sorted(ranked[:count])
