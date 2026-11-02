from pathlib import Path

import pytest

from ss_track.corpus.integrity import matroska_segment_end

EBML_HEADER = bytes.fromhex("1A45DFA3") + bytes.fromhex("82") + b"\x00\x00"
SEGMENT = bytes.fromhex("18538067")
UNKNOWN_ONE_BYTE = bytes.fromhex("FF")
UNKNOWN_EIGHT_BYTES = bytes.fromhex("01FFFFFFFFFFFFFF")


def _file(tmp_path: Path, payload: bytes) -> Path:
    path = tmp_path / "x.mkv"
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize(
    ("size_field", "expected_end"),
    [
        (bytes.fromhex("85"), 7 + 4 + 1 + 5),
        (bytes.fromhex("4005"), 7 + 4 + 2 + 5),
        (bytes.fromhex("0100000000000005"), 7 + 4 + 8 + 5),
    ],
)
def test_segment_end_reads_every_size_field_width(
    tmp_path: Path, size_field: bytes, expected_end: int
) -> None:
    path = _file(tmp_path, EBML_HEADER + SEGMENT + size_field)

    assert matroska_segment_end(path) == expected_end


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(EBML_HEADER + SEGMENT + UNKNOWN_ONE_BYTE, id="unknown-size"),
        pytest.param(EBML_HEADER + SEGMENT + UNKNOWN_EIGHT_BYTES, id="unknown-size-long"),
        pytest.param(b"not matroska at all", id="other-format"),
        pytest.param(EBML_HEADER + b"\x00\x00\x00\x00", id="no-segment"),
        pytest.param(EBML_HEADER + SEGMENT, id="no-size-field"),
        pytest.param(EBML_HEADER + SEGMENT + b"\x00", id="invalid-size-field"),
        pytest.param(EBML_HEADER + SEGMENT + bytes.fromhex("40"), id="short-size-field"),
        pytest.param(bytes.fromhex("1A45DFA3") + UNKNOWN_ONE_BYTE, id="unknown-header-size"),
        pytest.param(b"", id="empty"),
    ],
)
def test_segment_end_is_unknown_rather_than_guessed(tmp_path: Path, payload: bytes) -> None:
    assert matroska_segment_end(_file(tmp_path, payload)) is None
