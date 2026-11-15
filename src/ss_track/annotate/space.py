"""The pixel grid modules receive, and the display rotation recorded beside it.

Decoded pixels are not rotated for display. The stored orientation is therefore 0 degrees.
Display rotation is a fact copied from the source, and a label drawn in that other orientation
is refused. A video file is identified by its file hash. A retained image sequence is identified
by its sequence identity.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.evidence.sealing import sha256_file
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.decoding.decode import MediaInspection, inspect_media
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.sources.image_sequence import (
    INDEX_NAME,
    match_retained_images,
    read_index,
    sequence_identity,
)
from ss_track.corpus.sources.stored_media import inspect_stored

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
    """Inspect the stored frames one source gives modules.

    A video file's identity is its file hash, which is the identity of its first video stream.
    A retained image sequence's identity is the sequence identity of its ordered image hashes.
    Any other path is refused. Image order is never taken from filenames.
    """
    if path.is_file():
        return _video_space(path)
    if path.is_dir() and (path / INDEX_NAME).is_file():
        return _sequence_space(path)
    raise CorpusRefusal(
        RefusalCode.SOURCE_NOT_FOUND,
        f"source {path.name} is not a video file or an image sequence",
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


def _video_space(path: Path) -> FrameSpace:
    return _from_media(sha256_file(path), inspect_media(path, current_decode_policy()))


def _sequence_space(path: Path) -> FrameSpace:
    """Read one retained sequence: identity from image bytes, geometry from decoded pixels."""
    hashes = _inventory_hashes(read_index(path))
    identity = sequence_identity(hashes)
    try:
        match_retained_images(path, hashes)
    except (OSError, ValueError) as error:
        raise CorpusRefusal(
            RefusalCode.SOURCE_HASH_MISMATCH, str(error), {"source_sha256": identity}
        ) from error
    return _from_media(identity, inspect_stored(path, current_decode_policy()))


def _inventory_hashes(inventory: Mapping[str, Any]) -> list[str]:
    found = inventory.get("hashes")
    if not isinstance(found, list):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "sequence inventory hashes are not a list")
    hashes: list[str] = []
    for item in found:
        if not isinstance(item, str):
            raise CorpusRefusal(
                RefusalCode.RECORD_TAMPERED, "sequence inventory hash is not a string"
            )
        hashes.append(item)
    return hashes


def _from_media(identity: str, media: MediaInspection) -> FrameSpace:
    return FrameSpace(
        source_sha256=identity,
        width=media.decoded_width,
        height=media.decoded_height,
        display_rotation_degrees=media.display_rotation_degrees,
        time_base=media.time_base,
        pts=media.pts,
    )
