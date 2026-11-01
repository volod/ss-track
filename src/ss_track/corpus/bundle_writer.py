"""Write one frame bundle: strictly decode a source, keep the selected frames, seal the index."""

import logging
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import av

from ss_track.corpus.builder import load_verified_source, require_policy
from ss_track.corpus.decode import DecodePolicy, inspect_media
from ss_track.corpus.frames import (
    FRAME_BUNDLE_KIND,
    FrameBundle,
    bundle_hash,
    frame_name,
    open_frame_bundle,
)
from ss_track.corpus.importer import (
    MANIFEST_NAME,
    SCHEMA_VERSION,
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
    SEAL_FIELD,
    seal,
    sha256_bytes,
    write_sealed,
)

SCRATCH_PREFIX = ".incoming-"

_LOG = logging.getLogger(__name__)


def write_bundle(
    sequence: dict[str, Any],
    corpus: dict[str, JsonValue],
    policy: DecodePolicy,
    root: Path,
    data_root: Path,
) -> FrameBundle:
    """Write into a scratch directory and publish with one rename, so a failure leaves nothing."""
    source: dict[str, Any] = load_verified_source(sequence["source_sha256"], data_root)
    policy_sha256 = decode_policy_sha256(policy.as_record())
    require_policy(
        source["decode_policy_sha256"], policy_sha256, f"source {sequence['source_sha256']}"
    )
    media: dict[str, Any] = source["sequence"]
    stored = (
        source_directory(data_root, sequence["source_sha256"]) / source["source"]["stored_name"]
    )
    _require_space(root, media, sequence["selection"])
    target = root / sequence["sequence_id"]
    with TemporaryDirectory(prefix=SCRATCH_PREFIX, dir=root) as scratch:
        staged = Path(scratch) / "staged"
        staged.mkdir()
        converter = PixelConverter(policy.conversion_flags, policy.thread_count)
        writer = _FrameWriter(staged, sequence["selection"], converter)
        inspection = inspect_media(stored, policy, writer.accept)
        _require_same_decode(decoded_facts(inspection), media, sequence)
        body = _bundle_body(sequence, corpus, media, policy_sha256, writer)
        write_sealed(staged / MANIFEST_NAME, seal(body))
        # Moving a directory rewrites its parent link, so it must stay writable until it arrives.
        staged.rename(target)
    target.chmod(READ_ONLY_DIRECTORY_MODE)
    _warn_about_conversion(sequence["sequence_id"], media)
    return open_frame_bundle(target)


def _require_space(root: Path, media: dict[str, Any], selection: dict[str, int]) -> None:
    """Refuse before a long decode that could not finish. Raw frames dwarf their source."""
    frames = selection["end_frame"] - selection["start_frame"]
    required = frames * frame_size_bytes(media["decoded_width"], media["decoded_height"])
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
        path = self._directory / frame_name(frame_index, OUTPUT_PIXEL_FORMAT)
        path.write_bytes(pixels)
        path.chmod(READ_ONLY_FILE_MODE)
        self.frames.append(
            {"frame_index": frame_index, "pts": frame.pts, "sha256": sha256_bytes(pixels)}
        )


def _require_same_decode(
    decoded: dict[str, JsonValue], media: dict[str, Any], sequence: dict[str, Any]
) -> None:
    """A decode that disagrees with the import record means the decoder is not reproducing it."""
    differing = sorted(key for key, value in decoded.items() if media[key] != value)
    if differing:
        raise CorpusRefusal(
            RefusalCode.DECODE_DRIFT,
            "this decode differs from the imported source record",
            {"sequence_id": sequence["sequence_id"], "fields": list(differing)},
        )


def _bundle_body(
    sequence: dict[str, Any],
    corpus: dict[str, JsonValue],
    media: dict[str, Any],
    policy_sha256: str,
    writer: _FrameWriter,
) -> dict[str, JsonValue]:
    """Build the record. Its identity block alone decides the bundle hash."""
    identity: dict[str, JsonValue] = {
        "source_sha256": sequence["source_sha256"],
        "decode_policy_sha256": policy_sha256,
        "pixel_format": OUTPUT_PIXEL_FORMAT,
        "width": media["decoded_width"],
        "height": media["decoded_height"],
        "bytes_per_frame": frame_size_bytes(media["decoded_width"], media["decoded_height"]),
        "time_base": media["time_base"],
        "selection": sequence["selection"],
        "frames": writer.frames,
    }
    return {
        "kind": FRAME_BUNDLE_KIND,
        "schema_version": SCHEMA_VERSION,
        "corpus_id": corpus["corpus_id"],
        "corpus_manifest_sha256": corpus[SEAL_FIELD],
        "sequence_id": sequence["sequence_id"],
        "source_manifest_sha256": sequence["source_manifest_sha256"],
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
    }


def _warn_about_conversion(sequence_id: str, media: dict[str, Any]) -> None:
    """Both facts stay in the bundle record; the operator should also hear them at staging."""
    bits = media["source_bits_per_component"]
    if bits > OUTPUT_BITS_PER_COMPONENT:
        _LOG.warning("sequence %s: %d-bit source staged at 8 bits", sequence_id, bits)
    unspecified = media["color"]["matrix"] == UNSPECIFIED_COLOR_MATRIX
    if unspecified and uses_color_matrix(media["source_pixel_format"]):
        _LOG.warning("sequence %s: no color matrix tag, converted as BT.601", sequence_id)
