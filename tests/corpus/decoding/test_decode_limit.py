"""The declared decode limit: a clock the test controls, and a real clip that stays inside it."""

import math
from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.decoding.deadline import DECODE_LIMIT_SECONDS, DecodeDeadline
from ss_track.corpus.decoding.decode import inspect_media
from tests.corpus.decoding._decoding import POLICY, decoded_frame, fake_media

type Clock = Callable[[], float]


def _clock(*samples: float) -> Clock:
    """Return each sample once, then repeat the last one."""
    pending = list(samples)

    def clock() -> float:
        if len(pending) > 1:
            return pending.pop(0)
        return pending[0]

    return clock


def test_a_decode_inside_the_limit_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [decoded_frame(index) for index in range(4)]

    result = inspect_media(fake_media(monkeypatch, frames), POLICY, clock=_clock(0))

    assert len(result.pts) == 4


def test_a_decode_that_lands_on_the_limit_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [decoded_frame(index) for index in range(4)]
    clock = _clock(0, float(DECODE_LIMIT_SECONDS))

    result = inspect_media(fake_media(monkeypatch, frames), POLICY, clock=clock)

    assert len(result.pts) == 4


def test_a_decode_past_its_limit_names_the_elapsed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [decoded_frame(index) for index in range(4)]
    source = fake_media(monkeypatch, frames)
    seen: list[int] = []

    with pytest.raises(CorpusRefusal) as caught:
        inspect_media(
            source,
            POLICY,
            lambda index, _frame: seen.append(index),
            clock=_clock(0, float(DECODE_LIMIT_SECONDS) + 1),
        )

    refusal = caught.value
    assert refusal.code is RefusalCode.DECODE_TIME_EXCEEDED
    assert refusal.details == {
        "limit_seconds": DECODE_LIMIT_SECONDS,
        "elapsed_seconds": DECODE_LIMIT_SECONDS + 1,
        "frames_decoded": 0,
    }
    assert f"after {DECODE_LIMIT_SECONDS + 1} seconds" in refusal.message
    assert seen == []


def test_a_frame_already_delivered_is_named_when_the_next_check_is_past(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = [decoded_frame(index) for index in range(4)]
    seen: list[int] = []

    def clock() -> float:
        return float(DECODE_LIMIT_SECONDS + 7) if seen else 0

    with pytest.raises(CorpusRefusal) as caught:
        inspect_media(
            fake_media(monkeypatch, frames),
            POLICY,
            lambda index, _frame: seen.append(index),
            clock=clock,
        )

    assert seen == [0]
    assert caught.value.details["frames_decoded"] == 1
    assert caught.value.details["elapsed_seconds"] == DECODE_LIMIT_SECONDS + 7


def test_a_fractional_elapsed_time_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    source = fake_media(monkeypatch, [decoded_frame(0)])

    with pytest.raises(CorpusRefusal) as caught:
        inspect_media(source, POLICY, clock=_clock(0, 1.5), decode_limit_seconds=1)

    assert caught.value.details["elapsed_seconds"] == 1.5
    assert "after 1.5 seconds" in caught.value.message


def test_a_real_clip_inside_the_limit_still_decodes(clip: Path) -> None:
    result = inspect_media(clip, POLICY, clock=lambda: 0)

    assert result.pts


@pytest.mark.parametrize("limit", [0, -1, math.inf, math.nan, True])
def test_a_limit_that_is_not_a_positive_duration_is_rejected(limit: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        DecodeDeadline(limit, lambda: 0)
