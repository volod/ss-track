"""An operator-declared color matrix for a source that stores none.

The names are the matrices swscale can apply. ``bt601`` records SMPTE 170M, FFmpeg code 6.
swscale selects those coefficients with ``SWS_CS_ITU601``, whose value is 5, so conversion passes
that colorspace and keeps 6 in the record.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from av.video.reformatter import Colorspace

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.decoding.pixels import UNSPECIFIED_COLOR_MATRIX, uses_color_matrix

DECLARED_COLOR = "declared_color"
ORIGIN_DECLARED = "declared"
DECLARED_COLOR_FACT = "sequence.declared_color"


@dataclass(frozen=True, slots=True)
class _Matrix:
    name: str
    code: int
    colorspace: Colorspace


_MATRICES = (
    _Matrix("bt709", 1, Colorspace.ITU709),
    _Matrix("bt601", 6, Colorspace.ITU601),
    _Matrix("bt2020", 9, Colorspace.BT2020),
    _Matrix("fcc", 4, Colorspace.FCC),
    _Matrix("smpte240m", 7, Colorspace.SMPTE240M),
)
MATRIX_CODES = {item.name: item.code for item in _MATRICES}
_BY_CODE = {item.code: item for item in _MATRICES}


def matrix_code(name: str) -> int:
    """Return the FFmpeg color-space code for one declared matrix name."""
    try:
        return MATRIX_CODES[name]
    except KeyError as error:
        raise TypeError(f"color.matrix {name} is not a declared matrix") from error


def sws_colorspace(code: int) -> Colorspace:
    """Return the swscale colorspace that applies one declared matrix code."""
    try:
        return _BY_CODE[code].colorspace
    except KeyError as error:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID,
            "declared color matrix is not one conversion applies",
            {"matrix": code},
        ) from error


def recorded_matrix(record: Mapping[str, Any]) -> int | None:
    """Return a record's declared matrix code, when conversion used one."""
    declared = record.get(DECLARED_COLOR)
    if not isinstance(declared, dict):
        return None
    return _integer(declared.get("matrix"))


def declaration_changed(sequence: Mapping[str, Any], declared: int | None) -> bool:
    """Say whether this declaration would record a different matrix from the one stored."""
    recorded = recorded_matrix(sequence)
    stored = _stored_matrix(sequence)
    if declared is None:
        return recorded is not None
    if stored == UNSPECIFIED_COLOR_MATRIX:
        return recorded != declared
    return stored != declared


def apply_declared_color(
    sequence: dict[str, JsonValue], pixel_format: str, declared: int | None
) -> None:
    """Record a declared matrix when the source has none, or refuse one the source contradicts.

    A matching stored tag is left as the file recorded it. An absent declaration changes nothing.
    """
    if declared is None:
        return
    if not uses_color_matrix(pixel_format):
        raise _conflict(
            f"color matrix {_name(declared)} does not apply to {pixel_format}",
            {"source_pixel_format": pixel_format, "declared_matrix": declared},
        )
    stored = _stored_matrix(sequence)
    if stored != UNSPECIFIED_COLOR_MATRIX and stored != declared:
        raise _conflict(
            f"color matrix {_name(declared)} disagrees with the stored tag",
            {"declared_matrix": declared, "stored_matrix": stored},
        )
    if stored == UNSPECIFIED_COLOR_MATRIX:
        sequence[DECLARED_COLOR] = {"matrix": declared, "origin": ORIGIN_DECLARED}


def _name(code: int) -> str:
    item = _BY_CODE.get(code)
    return str(code) if item is None else item.name


def _stored_matrix(sequence: Mapping[str, Any]) -> int | None:
    color = sequence.get("color")
    if not isinstance(color, dict):
        return None
    return _integer(color.get("matrix"))


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _conflict(message: str, details: dict[str, JsonValue]) -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.COLOR_TAG_CONFLICT, message, details)
