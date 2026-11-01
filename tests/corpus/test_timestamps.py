import pytest

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.timestamps import TimestampQuality, assess_timestamps


@pytest.mark.parametrize(
    ("pts", "evidence", "quality"),
    [
        pytest.param([0, 40, 80], None, TimestampQuality.DERIVED, id="pts-alone-is-derived"),
        pytest.param([0, 40, 80], "hardware clock", TimestampQuality.MEASURED, id="with-evidence"),
        pytest.param([0, 33, 100], None, TimestampQuality.DERIVED, id="variable-rate"),
        pytest.param([-5, 0, 7], None, TimestampQuality.DERIVED, id="negative-start"),
        pytest.param([None, None], None, TimestampQuality.MISSING, id="none-stored"),
        pytest.param([10, None, 30], None, TimestampQuality.MISSING, id="partly-stored"),
    ],
)
def test_quality_grades(
    pts: list[int | None], evidence: str | None, quality: TimestampQuality
) -> None:
    assert assess_timestamps(pts, evidence) is quality


@pytest.mark.parametrize(
    ("pts", "frame_index"),
    [
        pytest.param([0, 40, 40, 80], 2, id="duplicate"),
        pytest.param([0, 40, 20, 80], 2, id="backward"),
        pytest.param([0, None, 0], 2, id="across-a-gap"),
    ],
)
def test_non_increasing_pts_is_refused_at_the_offending_frame(
    pts: list[int | None], frame_index: int
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        assess_timestamps(pts, None)

    assert caught.value.code is RefusalCode.PTS_NON_INCREASING
    assert caught.value.details["frame_index"] == frame_index


@pytest.mark.parametrize("pts", [[None, None], [0, None]])
def test_capture_clock_claim_needs_stored_timestamps(pts: list[int | None]) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        assess_timestamps(pts, "hardware clock")

    assert caught.value.code is RefusalCode.TIMESTAMP_CLAIM_UNSUPPORTED
