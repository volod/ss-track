import glob
import os
import subprocess
import sys
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import av
import pytest
from av.video.reformatter import ChromaLocation, Colorspace

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.decoding.declared_color import MATRIX_CODES, matrix_code, sws_colorspace
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.decoding.pixels import (
    CONVERSION_FLAGS,
    UNSPECIFIED_COLOR_MATRIX,
    PixelConverter,
    bits_per_component,
    color_tags,
    packed_rows,
    uses_color_matrix,
)
from tests.corpus._media import write_clip

_THREADS = 1
_BT601_MATRIX = 6
_BT709_MATRIX = 1
_LIMITED_RANGE = 1
_PURE_RED_BT709 = (63, 102, 240)
_PADDED_WIDTH = 33
_WIDTH = 32
_HEIGHT = 8


def _pixels(frame: av.VideoFrame) -> bytes:
    return PixelConverter(CONVERSION_FLAGS, _THREADS).pixels(frame)


def _flat_yuv(luma: int, u: int, v: int, matrix: int) -> av.VideoFrame:
    frame = av.VideoFrame(_WIDTH, _HEIGHT, "yuv444p")
    for plane, value in zip(frame.planes, (luma, u, v), strict=True):
        plane.update(bytes([value]) * (plane.line_size * plane.height))
    frame.colorspace, frame.color_range = matrix, _LIMITED_RANGE
    return frame


def _chroma_ramp(location: ChromaLocation) -> av.VideoFrame:
    frame = av.VideoFrame(_WIDTH, _HEIGHT, "yuv420p")
    luma, u, v = frame.planes
    luma.update(bytes([128]) * (luma.line_size * luma.height))
    u.update(bytes(64 + index * 8 for index in range(u.line_size)) * u.height)
    v.update(bytes([128]) * (v.line_size * v.height))
    frame.chroma_location = location
    return frame


def test_row_padding_never_reaches_the_pixels() -> None:
    def frame_with_padding(filler: int) -> av.VideoFrame:
        frame = av.VideoFrame(_PADDED_WIDTH, _HEIGHT, "rgb24")
        plane = frame.planes[0]
        padding = bytes([filler]) * (plane.line_size - _PADDED_WIDTH * 3)
        assert padding, "this width must leave padding, or the test proves nothing"
        plane.update((bytes([7, 8, 9]) * _PADDED_WIDTH + padding) * _HEIGHT)
        return frame

    assert _pixels(frame_with_padding(0x00)) == _pixels(frame_with_padding(0xFF))
    assert _pixels(frame_with_padding(0xAA)) == bytes([7, 8, 9]) * _PADDED_WIDTH * _HEIGHT


def test_converted_pixels_are_tightly_packed() -> None:
    frame = _flat_yuv(128, 128, 128, _BT601_MATRIX).reformat(width=_PADDED_WIDTH)

    assert len(_pixels(frame)) == _PADDED_WIDTH * _HEIGHT * 3


def test_a_row_layout_that_cannot_hold_the_image_is_refused() -> None:
    plane = SimpleNamespace(line_size=-12)
    frame = SimpleNamespace(planes=[plane], width=4, height=2)

    with pytest.raises(CorpusRefusal) as caught:
        packed_rows(frame)  # type: ignore[arg-type]

    assert caught.value.code is RefusalCode.SOURCE_UNREADABLE


def test_the_stored_color_matrix_steers_the_conversion() -> None:
    red = _pixels(_flat_yuv(*_PURE_RED_BT709, _BT709_MATRIX))[:3]
    misread = _pixels(_flat_yuv(*_PURE_RED_BT709, _BT601_MATRIX))[:3]

    assert red[0] >= 254 and red[1] <= 2 and red[2] <= 2
    assert misread[0] < 240


def _near_red(pixel: bytes) -> bool:
    return abs(pixel[0] - 255) <= 2 and pixel[1] <= 2 and pixel[2] <= 2


def test_a_declared_bt709_matrix_converts_untagged_red() -> None:
    frame = _flat_yuv(*_PURE_RED_BT709, UNSPECIFIED_COLOR_MATRIX)
    colorspace = sws_colorspace(matrix_code("bt709"))
    declared = PixelConverter(CONVERSION_FLAGS, _THREADS, matrix=colorspace).pixels(frame)[:3]
    untouched = _pixels(frame)[:3]

    assert _near_red(declared)
    assert tuple(untouched) == (233, 0, 2)
    assert not _near_red(untouched)


def test_a_declared_matrix_does_not_override_a_stored_tag() -> None:
    frame = _flat_yuv(*_PURE_RED_BT709, _BT601_MATRIX)
    forced = PixelConverter(CONVERSION_FLAGS, _THREADS, matrix=Colorspace.ITU709).pixels(frame)

    assert forced == _pixels(frame)


def test_frame_size_does_not_choose_a_color_matrix() -> None:
    narrow = _pixels(_flat_yuv(*_PURE_RED_BT709, UNSPECIFIED_COLOR_MATRIX))[:3]
    wide = av.VideoFrame(320, 16, "yuv444p")
    for plane, value in zip(wide.planes, _PURE_RED_BT709, strict=True):
        plane.update(bytes([value]) * (plane.line_size * plane.height))
    wide.colorspace, wide.color_range = UNSPECIFIED_COLOR_MATRIX, _LIMITED_RANGE

    assert tuple(_pixels(wide)[:3]) == tuple(narrow) == (233, 0, 2)


def test_bt601_uses_the_swscale_coefficients_for_that_name() -> None:
    """Code 6 is SMPTE 170M. swscale applies it as ITU601, whose own value is 5."""
    assert set(MATRIX_CODES) == {"bt709", "bt601", "bt2020", "fcc", "smpte240m"}
    assert int(sws_colorspace(matrix_code("bt601"))) == int(Colorspace.ITU601)
    assert int(Colorspace.ITU601) != matrix_code("bt601")


def test_the_stored_chroma_location_steers_the_conversion() -> None:
    left = _pixels(_chroma_ramp(ChromaLocation.LEFT))
    center = _pixels(_chroma_ramp(ChromaLocation.CENTER))

    assert left != center


def test_color_tags_record_every_input_of_the_conversion() -> None:
    frame = _chroma_ramp(ChromaLocation.LEFT)
    frame.colorspace, frame.color_range = _BT709_MATRIX, _LIMITED_RANGE

    tags = color_tags(frame)

    assert (tags.matrix, tags.range) == (_BT709_MATRIX, _LIMITED_RANGE)
    assert tags.chroma_location == ChromaLocation.LEFT


@pytest.mark.parametrize(
    ("pixel_format", "bits"),
    [("yuv420p", 8), ("yuv420p10le", 10), ("gray16le", 16), ("rgb24", 8), ("pal8", 8)],
)
def test_bits_per_component(pixel_format: str, bits: int) -> None:
    assert bits_per_component(pixel_format) == bits


@pytest.mark.parametrize(
    ("pixel_format", "needs_matrix"),
    [
        ("yuv420p", True),
        ("yuvj420p", True),
        ("nv12", True),
        ("yuv420p10le", True),
        ("yuv444p", True),
        ("yuv444p10le", True),
        ("yuva420p", True),
        ("ya8", False),
        ("rgb24", False),
        ("bgr24", False),
        ("rgba", False),
        ("gbrp", False),
        ("gray", False),
        ("gray16le", False),
        ("pal8", False),
    ],
)
def test_only_chroma_formats_use_a_color_matrix(pixel_format: str, needs_matrix: bool) -> None:
    assert uses_color_matrix(pixel_format) is needs_matrix


_DIGEST_PROGRAM = """
import ctypes, hashlib, pathlib, sys
from ss_track.corpus.decoding.decode import inspect_media
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.decoding.pixels import PixelConverter

if sys.argv[2]:
    library = ctypes.CDLL(sys.argv[2])
    library.av_force_cpu_flags(0)
    assert library.av_get_cpu_flags() == 0
policy = current_decode_policy()
converter = PixelConverter(policy.conversion_flags, policy.thread_count)
digest = hashlib.sha256()
inspect_media(
    pathlib.Path(sys.argv[1]), policy, lambda _, frame: digest.update(converter.pixels(frame))
)
print(digest.hexdigest())
"""


def _bundled_avutil() -> str | None:
    libraries = glob.glob(os.path.join(os.path.dirname(av.__file__), "..", "av.libs", "libavutil*"))
    return libraries[0] if libraries else None


def _digest(path: Path, library: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-c", _DIGEST_PROGRAM, str(path), library],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@pytest.mark.parametrize(
    ("codec", "pixel_format", "options"),
    [
        pytest.param("libx264", "yuv420p", {"preset": "ultrafast"}, id="h264-yuv420p"),
        pytest.param("mjpeg", "yuvj420p", None, id="mjpeg-yuvj420p"),
        pytest.param("mpeg2video", "yuv420p", None, id="mpeg2-yuv420p"),
        pytest.param("mpeg4", "yuv420p", None, id="mpeg4-yuv420p"),
        pytest.param("ffv1", "yuv420p10le", None, id="ffv1-10-bit"),
    ],
)
def test_pixels_do_not_depend_on_the_cpu_code_path(
    tmp_path: Path, codec: str, pixel_format: str, options: dict[str, str] | None
) -> None:
    """FFmpeg's default conversion and inverse DCT both depend on the SIMD path.

    Regression: on arm64 the MJPEG, MPEG-2 and MPEG-4 cases fail unless the policy pins the IDCT.
    """
    library = _bundled_avutil()
    if library is None:
        pytest.skip("this wheel layout does not expose libavutil")
    clip = write_clip(tmp_path / "clip.mkv", codec, pixel_format, options, width=320, height=240)

    assert _digest(clip, "") == _digest(clip, library)


def test_the_policy_declares_the_conversion_it_uses() -> None:
    policy = current_decode_policy()

    assert policy.conversion_flags == CONVERSION_FLAGS
    assert {"ACCURATE_RND", "BITEXACT"} <= set(CONVERSION_FLAGS.split("|"))


def test_chroma_is_interpolated_where_it_was_sited_with_no_steps() -> None:
    """Without full chroma the converter repeats chroma samples and misplaces a ramp."""
    rows = _pixels(_chroma_ramp(ChromaLocation.LEFT))
    blue = rows[2 : _WIDTH * 3 : 3]
    steps = [after - before for before, after in pairwise(blue[4:-3])]

    assert max(steps) - min(steps) <= 2
