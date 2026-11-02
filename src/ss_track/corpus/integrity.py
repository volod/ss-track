"""Container structure checks for the truncation FFmpeg cannot see.

A Matroska file cut just after a cluster header ends cleanly: FFmpeg logs nothing and returns fewer
frames as if none were lost. The file's own header still states how long its segment should be.
"""

from pathlib import Path

_EBML_HEADER_ID = bytes.fromhex("1A45DFA3")
_SEGMENT_ID = bytes.fromhex("18538067")
_ID_BYTES = 4
_HEADER_READ_BYTES = 4096
_MAX_SIZE_FIELD_BYTES = 8


def _read_size_field(header: bytes, offset: int) -> tuple[int | None, int]:
    """Return an EBML element size and the offset after it; an all-ones size means unknown."""
    if offset >= len(header) or header[offset] == 0:
        raise ValueError("no EBML size field")
    width = _MAX_SIZE_FIELD_BYTES + 1 - header[offset].bit_length()
    end = offset + width
    if end > len(header):
        raise ValueError("EBML size field runs past the header")
    value_mask = (1 << (7 * width)) - 1
    value = int.from_bytes(header[offset:end]) & value_mask
    return (None if value == value_mask else value), end


def matroska_segment_end(path: Path) -> int | None:
    """Return the byte offset where the Matroska segment declares its end.

    Returns None when the file cannot show this: a live-written segment of unknown size, or a
    header layout this check does not parse.
    """
    with path.open("rb") as handle:
        header = handle.read(_HEADER_READ_BYTES)
    if header[:_ID_BYTES] != _EBML_HEADER_ID:
        return None
    try:
        ebml_size, body = _read_size_field(header, _ID_BYTES)
        if ebml_size is None:
            return None
        segment = body + ebml_size
        if header[segment : segment + _ID_BYTES] != _SEGMENT_ID:
            return None
        segment_size, segment_body = _read_size_field(header, segment + _ID_BYTES)
    except ValueError:
        return None
    return None if segment_size is None else segment_body + segment_size
