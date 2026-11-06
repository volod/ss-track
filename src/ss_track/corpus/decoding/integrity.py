"""Container structure checks for the truncation FFmpeg cannot see, and the refusal they raise.

A Matroska file cut just after a cluster header ends cleanly: FFmpeg logs nothing and returns fewer
frames as if none were lost. The file's own header still states how long its segment should be, and
a container with a sample table states how many frames it stores.
"""

from collections.abc import Sequence
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, RefusalCode

FRAME_COUNT_CHECK = "frame_count"
SEGMENT_SIZE_CHECK = "matroska_segment_size"
_MATROSKA_FORMAT = "matroska"

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


def damaged(reason: str, frames_decoded: int) -> CorpusRefusal:
    """Refuse a source that decoding or a completeness check shows to be truncated or corrupt."""
    return CorpusRefusal(
        RefusalCode.SOURCE_DAMAGED,
        f"source is truncated or corrupt: {reason}",
        {"reason": reason, "frames_decoded": frames_decoded},
    )


def completeness_checks(
    path: Path,
    container_format: str,
    declared_frames: int,
    pts: Sequence[int | None],
    discarded: int,
) -> tuple[str, ...]:
    """Name each container-level check that showed a complete decode, refusing one that failed."""
    checks = _frame_count_checks(declared_frames, len(pts), discarded)
    if _MATROSKA_FORMAT in container_format:
        checks += _matroska_checks(path, len(pts))
    return checks


def _frame_count_checks(declared_frames: int, decoded: int, discarded: int) -> tuple[str, ...]:
    """Compare against the container's own frame count, when it stores one.

    An edit list can mark stored samples as never presented. They are present in the file, so
    they count toward the total without becoming frames of the sequence.
    """
    if declared_frames <= 0:
        return ()
    accounted = decoded + discarded
    if accounted < declared_frames:
        raise damaged(f"container declares {declared_frames} frames", decoded)
    return (FRAME_COUNT_CHECK,) if accounted == declared_frames else ()


def _matroska_checks(path: Path, decoded_frames: int) -> tuple[str, ...]:
    """Compare the file against the segment length written in its own header."""
    segment_end = matroska_segment_end(path)
    if segment_end is None:
        return ()
    size = path.stat().st_size
    if size < segment_end:
        raise damaged(f"segment ends at byte {segment_end}, file has {size}", decoded_frames)
    return (SEGMENT_SIZE_CHECK,)
