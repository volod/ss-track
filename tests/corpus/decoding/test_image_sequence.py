"""Lossless sequence decoding keeps explicit order and rejects damaged membership."""

from fractions import Fraction
from pathlib import Path

import av
import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.decoding.image_sequence import inspect_image_sequence
from tests.corpus._images import image


def test_sequence_order_and_timing(tmp_path: Path) -> None:
    paths = [image(tmp_path / f"{i}.png", i) for i in (2, 1)]
    observed: list[tuple[int, int | None, int]] = []

    def collect(index: int, frame: av.VideoFrame) -> None:
        observed.append((index, frame.pts, int(frame.to_ndarray(format="rgb24")[0, 0, 0])))

    result = inspect_image_sequence(paths, current_decode_policy(), collect)
    assert observed == [(0, None, 2), (1, None, 1)]
    assert result.pts == (None, None) and result.time_base is None
    observed.clear()
    result = inspect_image_sequence(
        paths, current_decode_policy(), collect, frame_rate=Fraction(25)
    )
    assert result.pts == (0, 1) and result.time_base == "1/25"
    assert [item[1] for item in observed] == [0, 1]


def test_missing_and_mixed_image_name_the_offender(tmp_path: Path) -> None:
    first = image(tmp_path / "first.png", 1)
    missing = tmp_path / "missing.png"
    with pytest.raises(CorpusRefusal) as error:
        inspect_image_sequence([first, missing], current_decode_policy(), lambda *_: None)
    assert error.value.code == RefusalCode.SOURCE_NOT_FOUND
    assert error.value.details["name"] == missing.name
    other = image(tmp_path / "other.png", 2, width=6)
    with pytest.raises(CorpusRefusal) as error:
        inspect_image_sequence([first, other], current_decode_policy(), lambda *_: None)
    assert error.value.code == RefusalCode.SOURCE_FORMAT_CHANGED
    assert error.value.details["name"] == other.name


def test_sequence_deadline_covers_all_images(tmp_path: Path) -> None:
    path = image(tmp_path / "one.png", 1)
    clock = iter([0.0, 0.0, 2.0])
    with pytest.raises(CorpusRefusal) as error:
        inspect_image_sequence(
            [path],
            current_decode_policy(),
            lambda *_: None,
            clock=lambda: next(clock),
            decode_limit_seconds=1.0,
        )
    assert error.value.code == RefusalCode.DECODE_TIME_EXCEEDED
