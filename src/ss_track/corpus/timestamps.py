"""Timestamp-quality assessment. Quality can only be established, never assumed."""

from collections.abc import Sequence
from enum import StrEnum
from itertools import pairwise

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode


class TimestampQuality(StrEnum):
    """Specification section 4.1 timestamp quality."""

    MEASURED = "measured"
    DERIVED = "derived"
    MISSING = "missing"


def assess_timestamps(
    pts: Sequence[int | None], capture_clock_evidence: str | None
) -> TimestampQuality:
    """Grade stored PTS values, or refuse values that cannot be correct as times.

    A container cannot show that its PTS came from a capture clock, so PTS alone is only `derived`.
    `measured` needs operator evidence, and one frame with no stored PTS makes the stream `missing`.
    """
    _require_strictly_increasing(pts)
    if any(value is None for value in pts):
        if capture_clock_evidence is not None:
            raise CorpusRefusal(
                RefusalCode.TIMESTAMP_CLAIM_UNSUPPORTED,
                "capture-clock evidence was declared, but the source stores no complete PTS",
                {"frames": len(pts), "frames_with_pts": sum(v is not None for v in pts)},
            )
        return TimestampQuality.MISSING
    if capture_clock_evidence is not None:
        return TimestampQuality.MEASURED
    return TimestampQuality.DERIVED


def _require_strictly_increasing(pts: Sequence[int | None]) -> None:
    stored = [(index, value) for index, value in enumerate(pts) if value is not None]
    for (_, earlier), (index, value) in pairwise(stored):
        if value <= earlier:
            raise CorpusRefusal(
                RefusalCode.PTS_NON_INCREASING,
                "presentation timestamps must strictly increase",
                {"frame_index": index, "previous_pts": earlier, "pts": value},
            )
