"""The frame an operator says coordinates were drawn on, and the two things it must match.

Coordinates use the stored orientation modules receive, which is 0 degrees. A label, a seed or a
frozen revision states its source identity and frame shape, and each is checked against the
decoded source or against the corpus stream it sits under by one comparison.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from ss_track.annotate.sources.frame_space import FrameSpace
from ss_track.corpus.declarations.fields import Fields, invalid

STORED_ORIENTATION_DEGREES = 0
_STREAM_FACTS = ("source_sha256", "width", "height", "frame_count")


@dataclass(frozen=True, slots=True)
class DeclaredSpace:
    """The frame the operator said the coordinates were drawn on."""

    source_sha256: str
    width: int
    height: int
    frame_count: int
    orientation_degrees: int
    display_rotation_degrees: int


def read_declared_space(fields: Fields) -> DeclaredSpace:
    """Read the space a label or a seed document states in its header."""
    return DeclaredSpace(
        source_sha256=fields.string("source_sha256"),
        width=fields.index("width"),
        height=fields.index("height"),
        frame_count=fields.index("frame_count"),
        orientation_degrees=fields.index("orientation_degrees"),
        display_rotation_degrees=fields.index("display_rotation_degrees"),
    )


def require_stored_orientation(declared: DeclaredSpace, where: str) -> None:
    """Refuse coordinates drawn in any orientation other than the stored one."""
    if declared.orientation_degrees != STORED_ORIENTATION_DEGREES:
        raise invalid(
            f"{where} orientation {declared.orientation_degrees} is not the stored "
            f"orientation {STORED_ORIENTATION_DEGREES}"
        )


def require_space(declared: DeclaredSpace, actual: FrameSpace, where: str) -> None:
    """Refuse coordinates that are not in the stored orientation of this source."""
    require_stored_orientation(declared, where)
    _require_equal(
        where,
        "source",
        (
            (
                "display rotation",
                declared.display_rotation_degrees,
                actual.display_rotation_degrees,
            ),
            ("source_sha256", declared.source_sha256, actual.source_sha256),
            ("width", declared.width, actual.width),
            ("height", declared.height, actual.height),
            ("frame_count", declared.frame_count, actual.frame_count),
        ),
    )


def require_stream(declared: DeclaredSpace, stream: Mapping[str, object], where: str) -> None:
    """Refuse labels that were not drawn on the source and stored frames of this corpus stream.

    A corpus stream states its source identity and the frame shape its pinned decode gave. Labels
    of another source, or of another decode of this one, would move every case derived from them.
    """
    stated = {
        "source_sha256": declared.source_sha256,
        "width": declared.width,
        "height": declared.height,
        "frame_count": declared.frame_count,
    }
    _require_equal(
        where,
        f"stream {stream.get('stream_id')}",
        tuple((name, stated[name], stream.get(name)) for name in _STREAM_FACTS),
    )


def _require_equal(where: str, other: str, found: tuple[tuple[str, object, object], ...]) -> None:
    for name, left, right in found:
        if left != right:
            raise invalid(f"{where} {name} is {left}, {other} is {right}")
