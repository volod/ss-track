"""The pixel grid modules receive, and the display rotation recorded beside it.

Decoded pixels are not rotated for display. The stored orientation is therefore 0 degrees.
Display rotation is a fact copied from the source, and a label drawn in that other orientation
is refused. The identity is the one a corpus stream names: the file hash for the first video
stream of a file, the stream identity for a later one, and the sequence identity for a retained
image sequence.
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
from ss_track.corpus.sources.identity import source_identity
from ss_track.corpus.sources.image_sequence import (
    INDEX_NAME,
    match_retained_images,
    read_index,
    sequence_identity,
)
from ss_track.corpus.sources.stored_media import inspect_stored


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


def read_frame_space(path: Path, video_stream_index: int | None = None) -> FrameSpace:
    """Inspect the stored frames one source gives modules.

    `video_stream_index` counts the video streams of a file from zero. Omit it when the file has
    one. The first stream's identity is the file hash, and a later stream's is its stream
    identity, as a corpus names it. A retained image sequence's identity is the sequence identity
    of its ordered image hashes, and it has no stream to name. Any other path is refused. Image
    order is never taken from filenames.
    """
    if path.is_file():
        return _video_space(path, video_stream_index)
    if path.is_dir() and (path / INDEX_NAME).is_file():
        if video_stream_index is not None:
            raise invalid(f"source {path.name} is an image sequence and has no video stream index")
        return _sequence_space(path)
    raise CorpusRefusal(
        RefusalCode.SOURCE_NOT_FOUND,
        f"source {path.name} is not a video file or an image sequence",
    )


def _video_space(path: Path, video_stream_index: int | None) -> FrameSpace:
    media = inspect_media(path, current_decode_policy(), video_stream_index=video_stream_index)
    return _from_media(source_identity(sha256_file(path), media.video_stream_index), media)


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
