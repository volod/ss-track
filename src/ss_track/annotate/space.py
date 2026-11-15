"""The pixel grid modules receive, and the display rotation recorded beside it.

Decoded pixels are not rotated for display. The stored orientation is therefore 0 degrees.
Display rotation is a fact copied from the source, and a label drawn in that other orientation
is refused.
"""

from dataclasses import dataclass
from pathlib import Path

from ss_track.core.evidence.sealing import sha256_file
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.decoding.decode import inspect_media
from ss_track.corpus.decoding.decode_policy import current_decode_policy

STORED_ORIENTATION_DEGREES = 0


@dataclass(frozen=True, slots=True)
class FrameSpace:
    """The stored frame a label or a seed must match."""

    source_sha256: str
    width: int
    height: int
    display_rotation_degrees: int
    time_base: str | None
    pts: tuple[int | None, ...]

    @property
    def frame_count(self) -> int:
        """Return how many frames the source decoded to."""
        return len(self.pts)


@dataclass(frozen=True, slots=True)
class DeclaredSpace:
    """The frame the operator said the coordinates were drawn on."""

    source_sha256: str
    width: int
    height: int
    frame_count: int
    orientation_degrees: int
    display_rotation_degrees: int


def read_frame_space(path: Path) -> FrameSpace:
    """Inspect one video file and return the stored frame modules receive.

    The source identity is the file hash, which is the identity of its first video stream.
    A directory is not a video file; an image sequence has a different identity.
    """
    if not path.is_file():
        raise CorpusRefusal(RefusalCode.SOURCE_NOT_FOUND, f"source {path.name} is not a video file")
    media = inspect_media(path, current_decode_policy())
    return FrameSpace(
        source_sha256=sha256_file(path),
        width=media.decoded_width,
        height=media.decoded_height,
        display_rotation_degrees=media.display_rotation_degrees,
        time_base=media.time_base,
        pts=media.pts,
    )


def require_space(declared: DeclaredSpace, actual: FrameSpace, where: str) -> None:
    """Refuse coordinates that are not in the stored orientation of this source."""
    if declared.orientation_degrees != STORED_ORIENTATION_DEGREES:
        raise invalid(
            f"{where} orientation {declared.orientation_degrees} is not the stored "
            f"orientation {STORED_ORIENTATION_DEGREES}"
        )
    found = (
        ("display rotation", declared.display_rotation_degrees, actual.display_rotation_degrees),
        ("source_sha256", declared.source_sha256, actual.source_sha256),
        ("width", declared.width, actual.width),
        ("height", declared.height, actual.height),
        ("frame_count", declared.frame_count, actual.frame_count),
    )
    for name, left, right in found:
        if left != right:
            raise invalid(f"{where} {name} is {left}, source is {right}")
