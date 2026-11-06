"""The pinned PNG encoder and the outline that sits on a declared rectangle."""

import io
import zlib

import av
import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode
from ss_track.corpus.cases.case_model import Region
from ss_track.corpus.cases.preview_png import (
    OUTLINE_RGB,
    PNG_ENCODER,
    REMOVED_RGB,
    encode_rgb_png,
    join_horizontal,
    paint_outline,
    removed_panel,
)
from ss_track.corpus.decoding.pixels import OUTPUT_PIXEL_FORMAT, packed_rows

_WIDTH = 10
_HEIGHT = 8
_FILL = bytes((10, 20, 30))
_OUTLINE = bytes(OUTLINE_RGB)
_REMOVED = bytes(REMOVED_RGB)
# Perimeter of the half-open rectangle x=3, y=2, width=5, height=4, listed by hand.
_PERIMETER = (
    (3, 2),
    (4, 2),
    (5, 2),
    (6, 2),
    (7, 2),
    (3, 5),
    (4, 5),
    (5, 5),
    (6, 5),
    (7, 5),
    (3, 3),
    (3, 4),
    (7, 3),
    (7, 4),
)
_INTERIOR = ((4, 3), (5, 3), (6, 3), (4, 4), (5, 4), (6, 4))


def _pixel(packed: bytes, width: int, x: int, y: int) -> bytes:
    start = (y * width + x) * 3
    return packed[start : start + 3]


def _png_rgb(payload: bytes) -> tuple[int, int, bytes]:
    with av.open(io.BytesIO(payload), mode="r", format="png_pipe") as container:
        frame = next(container.decode(video=0))
    rgb = frame.reformat(format=OUTPUT_PIXEL_FORMAT)
    return rgb.width, rgb.height, packed_rows(rgb)


def _chunks(payload: bytes) -> list[tuple[bytes, bytes]]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    found = []
    while offset < len(payload):
        length = int.from_bytes(payload[offset : offset + 4], "big")
        tag = payload[offset + 4 : offset + 8]
        data = payload[offset + 8 : offset + 8 + length]
        crc = int.from_bytes(payload[offset + 8 + length : offset + 12 + length], "big")
        assert zlib.crc32(tag + data) & 0xFFFFFFFF == crc
        found.append((tag, data))
        offset += 12 + length
    return found


def test_the_encoder_name_and_colors_stay_pinned() -> None:
    assert PNG_ENCODER == "stored-deflate-rgb24-v1"
    assert OUTLINE_RGB == (255, 0, 0)
    assert REMOVED_RGB == (255, 0, 255)


def test_one_input_encodes_to_identical_bytes_and_the_outline_is_only_the_perimeter() -> None:
    region = Region(3, 2, 5, 4)
    source = _FILL * (_WIDTH * _HEIGHT)
    painted = paint_outline(source, _WIDTH, _HEIGHT, region)
    assert source == _FILL * (_WIDTH * _HEIGHT)
    sheet = join_horizontal([source, painted, removed_panel(_WIDTH, _HEIGHT)], _WIDTH, _HEIGHT)
    width = _WIDTH * 3
    first = encode_rgb_png(width, _HEIGHT, sheet)
    assert encode_rgb_png(width, _HEIGHT, sheet) == first

    tags = [tag for tag, _ in _chunks(first)]
    assert tags == [b"IHDR", b"IDAT", b"IEND"]
    decoded_width, decoded_height, pixels = _png_rgb(first)
    assert (decoded_width, decoded_height) == (width, _HEIGHT)
    for x, y in _PERIMETER:
        assert _pixel(pixels, width, _WIDTH + x, y) == _OUTLINE
    for x, y in _INTERIOR:
        assert _pixel(pixels, width, _WIDTH + x, y) == _FILL
    assert _pixel(pixels, width, _WIDTH + 2, 2) == _FILL
    assert _pixel(pixels, width, _WIDTH + 3, 6) == _FILL
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            assert _pixel(pixels, width, x, y) == _FILL
            assert _pixel(pixels, width, 2 * _WIDTH + x, y) == _REMOVED


def test_a_rectangle_on_the_frame_edge_and_a_single_pixel_stay_inside() -> None:
    source = _FILL * (_WIDTH * _HEIGHT)
    edge = paint_outline(source, _WIDTH, _HEIGHT, Region(0, 0, _WIDTH, 1))
    assert _pixel(edge, _WIDTH, 0, 0) == _OUTLINE
    assert _pixel(edge, _WIDTH, _WIDTH - 1, 0) == _OUTLINE
    assert _pixel(edge, _WIDTH, 0, 1) == _FILL
    single = paint_outline(source, _WIDTH, _HEIGHT, Region(_WIDTH - 1, _HEIGHT - 1, 1, 1))
    assert _pixel(single, _WIDTH, _WIDTH - 1, _HEIGHT - 1) == _OUTLINE
    assert _pixel(single, _WIDTH, _WIDTH - 2, _HEIGHT - 2) == _FILL


def test_a_region_past_the_frame_and_a_short_buffer_are_refused() -> None:
    source = _FILL * (_WIDTH * _HEIGHT)
    with pytest.raises(CorpusRefusal) as caught:
        paint_outline(source, _WIDTH, _HEIGHT, Region(8, 0, 4, 1))
    assert caught.value.code is RefusalCode.CASE_INVALID

    with pytest.raises(CorpusRefusal) as bad_size:
        encode_rgb_png(_WIDTH, _HEIGHT, source + b"\x00")
    assert bad_size.value.code is RefusalCode.RECORD_INVALID


def test_a_frame_larger_than_one_stored_block_roundtrips() -> None:
    width, height = 200, 120
    pixels = bytes((7, 8, 9)) * (width * height)
    payload = encode_rgb_png(width, height, pixels)
    assert encode_rgb_png(width, height, pixels) == payload
    idat = next(data for tag, data in _chunks(payload) if tag == b"IDAT")
    raw = zlib.decompress(idat)
    assert len(raw) > 65535
    rows = [raw[y * (1 + width * 3) + 1 : (y + 1) * (1 + width * 3)] for y in range(height)]
    assert b"".join(rows) == pixels
    decoded_width, decoded_height, decoded = _png_rgb(payload)
    assert (decoded_width, decoded_height, decoded) == (width, height, pixels)
