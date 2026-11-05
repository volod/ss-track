"""Pinned RGB PNG for a case contact sheet.

Rows are stored in uncompressed deflate blocks. The bytes follow from the pixels alone, so a zlib
build cannot change them. Checksums use the CRC-32 and Adler-32 algorithms; they are not a
compressor. A declared region is outlined on its own perimeter pixels, inside the half-open
rectangle.
"""

import zlib
from collections.abc import Sequence

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.cases.case_model import Region
from ss_track.corpus.decoding.pixels import OUTPUT_BYTES_PER_PIXEL

PNG_ENCODER = "stored-deflate-rgb24-v1"
OUTLINE_RGB = (255, 0, 0)
REMOVED_RGB = (255, 0, 255)
_OUTLINE = bytes(OUTLINE_RGB)
_REMOVED = bytes(REMOVED_RGB)
_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ZLIB_HEADER = b"\x78\x01"  # deflate, 32 KiB window, no preset dictionary
_STORED_BLOCK = 65535
_MAX_DIMENSION = 2**31 - 1
_FILTER_NONE = 0
_BIT_DEPTH = 8
_COLOR_RGB = 2


def removed_panel(width: int, height: int) -> bytes:
    """Return a solid panel that stands in for a frame a case removed."""
    _require_size(width, height, width * height * OUTPUT_BYTES_PER_PIXEL)
    return _REMOVED * (width * height)


def paint_outline(pixels: bytes, width: int, height: int, region: Region) -> bytes:
    """Replace the rectangle's perimeter with the outline color. Other pixels stay."""
    _require_size(width, height, len(pixels))
    if not _region_inside(width, height, region):
        raise CorpusRefusal(
            RefusalCode.CASE_INVALID,
            "region runs past the frame",
            {"region": region.record()},
        )
    painted = bytearray(pixels)
    right = region.x + region.width - 1
    bottom = region.y + region.height - 1
    for x in range(region.x, right + 1):
        _put(painted, width, x, region.y)
        _put(painted, width, x, bottom)
    for y in range(region.y, bottom + 1):
        _put(painted, width, region.x, y)
        _put(painted, width, right, y)
    return bytes(painted)


def join_horizontal(panels: Sequence[bytes], width: int, height: int) -> bytes:
    """Place equal frames side by side, with no gap. The first panel is the leftmost."""
    row_bytes = width * OUTPUT_BYTES_PER_PIXEL
    expected = row_bytes * height
    if not panels or any(len(panel) != expected for panel in panels):
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID,
            "sheet panels do not match the frame size",
            {"width": width, "height": height, "panels": len(panels)},
        )
    sheet = bytearray()
    for y in range(height):
        start = y * row_bytes
        for panel in panels:
            sheet += panel[start : start + row_bytes]
    return bytes(sheet)


def encode_rgb_png(width: int, height: int, pixels: bytes) -> bytes:
    """Encode tightly packed RGB as one PNG. The same pixels always yield the same bytes."""
    _require_size(width, height, len(pixels))
    scanlines = _scanlines(width, height, pixels)
    chunks = (
        _chunk(b"IHDR", _ihdr(width, height))
        + _chunk(b"IDAT", _stored_zlib(scanlines))
        + _chunk(b"IEND", b"")
    )
    return _SIGNATURE + chunks


def _require_size(width: int, height: int, size: int) -> None:
    fits = 1 <= width <= _MAX_DIMENSION and 1 <= height <= _MAX_DIMENSION
    if not fits or size != width * height * OUTPUT_BYTES_PER_PIXEL:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID,
            "sheet pixels do not match width and height",
            {"width": width, "height": height, "byte_count": size},
        )


def _region_inside(width: int, height: int, region: Region) -> bool:
    return (
        region.x >= 0
        and region.y >= 0
        and region.width >= 1
        and region.height >= 1
        and region.x + region.width <= width
        and region.y + region.height <= height
    )


def _put(painted: bytearray, width: int, x: int, y: int) -> None:
    start = (y * width + x) * OUTPUT_BYTES_PER_PIXEL
    painted[start : start + OUTPUT_BYTES_PER_PIXEL] = _OUTLINE


def _scanlines(width: int, height: int, pixels: bytes) -> bytes:
    row_bytes = width * OUTPUT_BYTES_PER_PIXEL
    rows = (
        bytes((_FILTER_NONE,)) + pixels[y * row_bytes : (y + 1) * row_bytes] for y in range(height)
    )
    return b"".join(rows)


def _ihdr(width: int, height: int) -> bytes:
    return (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((_BIT_DEPTH, _COLOR_RGB, 0, 0, 0))
    )


def _stored_zlib(payload: bytes) -> bytes:
    """Wrap payload in a zlib stream of stored blocks, independent of the compressor."""
    blocks = bytearray()
    offset = 0
    while True:
        final = offset + _STORED_BLOCK >= len(payload)
        chunk = payload[offset : offset + _STORED_BLOCK]
        offset += len(chunk)
        blocks.append(1 if final else 0)
        blocks += len(chunk).to_bytes(2, "little")
        blocks += (len(chunk) ^ 0xFFFF).to_bytes(2, "little")
        blocks += chunk
        if final:
            break
    checksum = zlib.adler32(payload) & 0xFFFFFFFF
    return _ZLIB_HEADER + bytes(blocks) + checksum.to_bytes(4, "big")


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return len(data).to_bytes(4, "big") + tag + data + crc.to_bytes(4, "big")
