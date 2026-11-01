"""Write one frame bundle: strictly decode a source, keep the selected frames, seal the index."""

import logging
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import av

from ss_track.corpus.builder import load_verified_source
from ss_track.corpus.decode import DecodePolicy, inspect_media
from ss_track.corpus.frames import (
    BUNDLE_SCHEMA_VERSION,
    FRAME_BUNDLE_KIND,
    FrameBundle,
    bundle_hash,
    frame_name,
    open_frame_bundle,
)
from ss_track.corpus.importer import (
    MANIFEST_NAME,
    decode_policy_sha256,
    decoded_facts,
    source_directory,
)
from ss_track.corpus.pixels import (
    OUTPUT_BITS_PER_COMPONENT,
    OUTPUT_PIXEL_FORMAT,
    UNSPECIFIED_COLOR_MATRIX,
    PixelConverter,
    frame_size_bytes,
    uses_color_matrix,
)
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import (
    READ_ONLY_DIRECTORY_MODE,
    READ_ONLY_FILE_MODE,
    SCRATCH_PREFIX,
    SEAL_FIELD,
    seal,
    sha256_bytes,
    write_sealed,
)

_LOG = logging.getLogger(__name__)


def write_bundle(
    stream: dict[str, Any],
    corpus: dict[str, JsonValue],
    policy: DecodePolicy,
    root: Path,
    data_root: Path,
) -> FrameBundle:
    """Write into a scratch directory and publish with one rename, so a failure leaves nothing."""
    source: dict[str, Any] = load_verified_source(stream["source_sha256"], data_root)
    policy_sha256 = decode_policy_sha256(policy.as_record())
    media: dict[str, Any] = source["sequence"]
    stored = source_directory(data_root, stream["source_sha256"]) / source["source"]["stored_name"]
    selection = stream["selection"]
    width, height = media["decoded_width"], media["decoded_height"]
    require_space(root, selection["end_frame"] - selection["start_frame"], width, height)
    target = root / stream["stream_id"]
    with publish_bundle(root, target) as staged:
        converter = PixelConverter(policy.conversion_flags, policy.thread_count)
        writer = _FrameWriter(staged, stream["selection"], converter)
        inspection = inspect_media(stored, policy, writer.accept)
        _require_same_decode(decoded_facts(inspection), media, stream)
        body = _bundle_body(stream, corpus, media, policy_sha256, writer)
        write_sealed(staged / MANIFEST_NAME, seal(body))
    _warn_about_conversion(stream["stream_id"], media)
    return open_frame_bundle(target)


@contextmanager
def publish_bundle(root: Path, target: Path) -> Iterator[Path]:
    """Yield a scratch directory and publish it complete by one rename, or leave nothing."""
    with TemporaryDirectory(prefix=SCRATCH_PREFIX, dir=root) as scratch:
        staged = Path(scratch) / "staged"
        staged.mkdir()
        yield staged
        # Moving a directory rewrites its parent link, so it must stay writable until it arrives.
        staged.rename(target)
    target.chmod(READ_ONLY_DIRECTORY_MODE)


def store_frame(
    directory: Path, frame_index: int, pts: int | None, pixels: bytes
) -> dict[str, JsonValue]:
    """Write one read-only frame and return its line of the sealed index."""
    path = directory / frame_name(frame_index, OUTPUT_PIXEL_FORMAT)
    path.write_bytes(pixels)
    path.chmod(READ_ONLY_FILE_MODE)
    return {"frame_index": frame_index, "pts": pts, "sha256": sha256_bytes(pixels)}


def require_space(root: Path, frames: int, width: int, height: int) -> None:
    """Refuse before work that could not finish. Raw frames dwarf their source."""
    required = frames * frame_size_bytes(width, height)
    free = shutil.disk_usage(root).free
    if free < required:
        raise CorpusRefusal(
            RefusalCode.STORAGE_FAILED,
            "not enough free space to stage these frames",
            {"required_bytes": required, "free_bytes": free},
        )


class _FrameWriter:
    """Writes the selected frames of one decode and keeps the index of what it wrote."""

    def __init__(self, directory: Path, selection: dict[str, int], converter: PixelConverter):
        self._directory = directory
        self._window = range(selection["start_frame"], selection["end_frame"])
        self._converter = converter
        self.frames: list[JsonValue] = []

    def accept(self, frame_index: int, frame: av.VideoFrame) -> None:
        """Store one frame if the selection includes it."""
        if frame_index not in self._window:
            return
        pixels = self._converter.pixels(frame)
        self.frames.append(store_frame(self._directory, frame_index, frame.pts, pixels))


def _require_same_decode(
    decoded: dict[str, JsonValue], media: dict[str, Any], stream: dict[str, Any]
) -> None:
    """A decode that disagrees with the import record means the decoder is not reproducing it."""
    differing = sorted(key for key, value in decoded.items() if media[key] != value)
    if differing:
        raise CorpusRefusal(
            RefusalCode.DECODE_DRIFT,
            "this decode differs from the imported source record",
            {"stream_id": stream["stream_id"], "fields": list(differing)},
        )


def _bundle_body(
    stream: dict[str, Any],
    corpus: dict[str, JsonValue],
    media: dict[str, Any],
    policy_sha256: str,
    writer: _FrameWriter,
) -> dict[str, JsonValue]:
    """Build the record. Its identity block alone decides the bundle hash."""
    identity: dict[str, JsonValue] = {
        "source_sha256": stream["source_sha256"],
        "decode_policy_sha256": policy_sha256,
        "pixel_format": OUTPUT_PIXEL_FORMAT,
        "width": media["decoded_width"],
        "height": media["decoded_height"],
        "bytes_per_frame": frame_size_bytes(media["decoded_width"], media["decoded_height"]),
        "time_base": media["time_base"],
        "selection": stream["selection"],
        "frames": writer.frames,
    }
    return {
        "kind": FRAME_BUNDLE_KIND,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "corpus_id": corpus["corpus_id"],
        "corpus_manifest_sha256": corpus[SEAL_FIELD],
        "stream_id": stream["stream_id"],
        "source_manifest_sha256": stream["source_manifest_sha256"],
        "bundle_sha256": bundle_hash(identity),
        "identity": identity,
        "source_pixel_format": media["source_pixel_format"],
        "source_bits_per_component": media["source_bits_per_component"],
        "precision_reduced": media["source_bits_per_component"] > OUTPUT_BITS_PER_COMPONENT,
        "color": media["color"],
        "display_rotation_degrees": media["display_rotation_degrees"],
        "interlaced_frames": media["interlaced_frames"],
        "timestamp_quality": media["timestamp_quality"],
        "capture_clock_evidence": media["capture_clock_evidence"],
        "generated": None,
    }


def _warn_about_conversion(stream_id: str, media: dict[str, Any]) -> None:
    """Both facts stay in the bundle record; the operator should also hear them at staging."""
    bits = media["source_bits_per_component"]
    if bits > OUTPUT_BITS_PER_COMPONENT:
        _LOG.warning("stream %s: %d-bit source staged at 8 bits", stream_id, bits)
    unspecified = media["color"]["matrix"] == UNSPECIFIED_COLOR_MATRIX
    if unspecified and uses_color_matrix(media["source_pixel_format"]):
        _LOG.warning("stream %s: no color matrix tag, converted as BT.601", stream_id)
