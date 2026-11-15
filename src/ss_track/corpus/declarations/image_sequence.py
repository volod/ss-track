"""Explicit image membership and timing in a recording declaration."""

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from ss_track.corpus.declarations.fields import Fields, invalid


@dataclass(frozen=True, slots=True)
class ImageMember:
    index: int
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class ImageSequence:
    frames: tuple[ImageMember, ...]
    frame_rate: Fraction | None


def read_image_sequence(source: Fields, root: Path) -> ImageSequence | None:
    """Require consecutive explicit indices; never infer order from filenames."""
    if not source.has("frames"):
        if source.has("frame_rate"):
            raise invalid("frame_rate requires an image sequence")
        return None
    if source.has("video_stream_index"):
        raise invalid("image sequence cannot select a video stream")
    frames = tuple(_member(raw, root) for raw in source.items("frames"))
    for expected, member in enumerate(frames):
        if member.index != expected:
            raise invalid(
                f"sequence index {expected} missing or out of order at {member.path.name}"
            )
    if len({member.path.resolve() for member in frames}) != len(frames):
        raise invalid("sequence repeats an image path")
    rate = Fraction(source.text("frame_rate")) if source.has("frame_rate") else None
    return ImageSequence(frames, rate)


def _member(raw: object, root: Path) -> ImageMember:
    fields = Fields(raw, "source.frames")
    return ImageMember(fields.index("index"), root / fields.text("path"), fields.text("sha256"))
