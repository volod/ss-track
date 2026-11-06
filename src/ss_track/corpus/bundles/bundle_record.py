"""The sealed record of one decoded stream.

The identity block is the bundle hash. A fresh decode and a reused bundle both build that block
here, so a linked copy cannot drift from a decode of the same source, policy and window.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.corpus.bundles.frames import FRAME_BUNDLE, bundle_hash
from ss_track.corpus.decoding.declared_color import DECLARED_COLOR
from ss_track.corpus.decoding.pixels import (
    OUTPUT_BITS_PER_COMPONENT,
    OUTPUT_PIXEL_FORMAT,
    frame_size_bytes,
)

# Identity fields a decode has not yet produced frames for. The sealed index is the rest.
LAYOUT_FIELDS = (
    "source_sha256",
    "decode_policy_sha256",
    "pixel_format",
    "width",
    "height",
    "bytes_per_frame",
    "time_base",
    "selection",
)


def stream_identity(
    stream: Mapping[str, Any],
    media: Mapping[str, Any],
    policy_sha256: str,
    frames: Sequence[JsonValue],
) -> dict[str, JsonValue]:
    """Return the identity block whose hash is `bundle_sha256`.

    Nothing about the corpus or the stream's name enters it. `frames` is the sealed index: frame
    index, presentation time and frame hash, in presentation order.
    """
    width = media["decoded_width"]
    height = media["decoded_height"]
    identity: dict[str, JsonValue] = {
        "source_sha256": stream["source_sha256"],
        "decode_policy_sha256": policy_sha256,
        "pixel_format": OUTPUT_PIXEL_FORMAT,
        "width": width,
        "height": height,
        "bytes_per_frame": frame_size_bytes(width, height),
        "time_base": media["time_base"],
        "selection": stream["selection"],
        "frames": list(frames),
    }
    return identity


def stream_layout(
    stream: Mapping[str, Any], media: Mapping[str, Any], policy_sha256: str
) -> dict[str, JsonValue]:
    """Return the identity fields known before a decode, which a candidate must already have."""
    identity = stream_identity(stream, media, policy_sha256, ())
    return {key: identity[key] for key in LAYOUT_FIELDS}


def stream_bundle_body(
    stream: Mapping[str, Any],
    corpus: Mapping[str, JsonValue],
    media: Mapping[str, Any],
    policy_sha256: str,
    frames: Sequence[JsonValue],
) -> dict[str, JsonValue]:
    """Build the record a stream seals. Its identity block alone decides the bundle hash."""
    identity = stream_identity(stream, media, policy_sha256, frames)
    return {
        **FRAME_BUNDLE.stamp(),
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
        **_declared_color(media),
        "display_rotation_degrees": media["display_rotation_degrees"],
        "interlaced_frames": media["interlaced_frames"],
        "timestamp_quality": media["timestamp_quality"],
        "capture_clock_evidence": media["capture_clock_evidence"],
        "generated": None,
    }


def _declared_color(media: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Return the declared matrix when conversion used one, and nothing otherwise."""
    if DECLARED_COLOR not in media:
        return {}
    return {DECLARED_COLOR: media[DECLARED_COLOR]}
