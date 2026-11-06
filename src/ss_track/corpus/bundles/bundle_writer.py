"""Write the frame bundles of one source from a single strict decode."""

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import av

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_frame_bundle
from ss_track.corpus.bundles.frame_store import require_space, store_frame
from ss_track.corpus.bundles.frames import FRAME_BUNDLE, FrameBundle, bundle_hash
from ss_track.corpus.bundles.publish import publish_bundles
from ss_track.corpus.decoding.declared_color import (
    DECLARED_COLOR,
    recorded_matrix,
    sws_colorspace,
)
from ss_track.corpus.decoding.decode import FrameConsumer, inspect_media
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from ss_track.corpus.decoding.pixels import (
    OUTPUT_BITS_PER_COMPONENT,
    OUTPUT_PIXEL_FORMAT,
    UNSPECIFIED_COLOR_MATRIX,
    PixelConverter,
    frame_size_bytes,
    uses_color_matrix,
)
from ss_track.corpus.decoding.streams import VIDEO_STREAM_INDEX, recorded_video_stream_index
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.sources.importer import (
    MANIFEST_NAME,
    decode_policy_sha256,
    decoded_facts,
    source_directory,
)
from ss_track.corpus.sources.stored import load_verified_source

_LOG = logging.getLogger(__name__)


def write_source_bundles(
    streams: Sequence[dict[str, Any]],
    corpus: dict[str, JsonValue],
    policy: DecodePolicy,
    root: Path,
    data_root: Path,
) -> tuple[FrameBundle, ...]:
    """Decode one source once and publish each stream. A failure publishes none of them.

    Every frame is decoded, including frames no stream stores. Seeking to a window would skip the
    proof that this decode still matches the import. Each stream keeps its own converter, so its
    frames are produced in the same sequence as a stage of that stream alone.
    """
    source_sha256 = _one_source(streams)
    source: dict[str, Any] = load_verified_source(source_sha256, data_root)
    policy_sha256 = decode_policy_sha256(policy.as_record())
    media: dict[str, Any] = source["sequence"]
    stored = source_directory(data_root, source_sha256) / source["source"]["stored_name"]
    width, height = media["decoded_width"], media["decoded_height"]
    require_space(root, sum(_selection_length(stream) for stream in streams), width, height)
    targets = tuple(root / str(stream["stream_id"]) for stream in streams)
    matrix = recorded_matrix(media)
    with publish_bundles(root, targets) as staged_dirs:
        writers = _writers(staged_dirs, streams, policy, matrix)
        inspection = inspect_media(
            stored,
            policy,
            _fan_out(writers),
            video_stream_index=recorded_video_stream_index(media),
        )
        _require_same_decode(decoded_facts(inspection), media, streams)
        _seal_bundles(streams, writers, staged_dirs, corpus, media, policy_sha256)
        _warn_about_conversion([str(stream["stream_id"]) for stream in streams], media, matrix)
    return tuple(open_frame_bundle(target) for target in targets)


def _one_source(streams: Sequence[Mapping[str, Any]]) -> str:
    """Return the source these streams share. Staging groups them before it decodes."""
    source_sha256 = str(streams[0]["source_sha256"])
    if any(stream["source_sha256"] != source_sha256 for stream in streams):
        raise AssertionError("one decode serves one source")
    return source_sha256


def _selection_length(stream: Mapping[str, Any]) -> int:
    selection = stream["selection"]
    return int(selection["end_frame"]) - int(selection["start_frame"])


class _FrameWriter:
    """Writes one stream's selection and keeps the index a solo decode would have written."""

    def __init__(self, directory: Path, selection: Mapping[str, Any], converter: PixelConverter):
        self.window = range(int(selection["start_frame"]), int(selection["end_frame"]))
        self._directory = directory
        self._converter = converter
        self.frames: list[JsonValue] = []

    def store(self, frame_index: int, frame: av.VideoFrame) -> None:
        """Convert and store one frame. This converter sees only this stream's frames."""
        pixels = self._converter.pixels(frame)
        self.frames.append(store_frame(self._directory, frame_index, frame.pts, pixels))


def _writers(
    staged_dirs: Sequence[Path],
    streams: Sequence[Mapping[str, Any]],
    policy: DecodePolicy,
    matrix: int | None,
) -> tuple[_FrameWriter, ...]:
    return tuple(
        _FrameWriter(staged, stream["selection"], _converter(policy, matrix))
        for staged, stream in zip(staged_dirs, streams, strict=True)
    )


def _converter(policy: DecodePolicy, matrix: int | None) -> PixelConverter:
    colorspace = None if matrix is None else sws_colorspace(matrix)
    return PixelConverter(policy.conversion_flags, policy.thread_count, matrix=colorspace)


def _fan_out(writers: Sequence[_FrameWriter]) -> FrameConsumer:
    """Deliver each frame to every stream whose window contains it."""
    routes = _routes(writers)

    def accept(frame_index: int, frame: av.VideoFrame) -> None:
        for writer in routes.get(frame_index, ()):
            writer.store(frame_index, frame)

    return accept


def _routes(writers: Sequence[_FrameWriter]) -> dict[int, tuple[_FrameWriter, ...]]:
    grouped: dict[int, list[_FrameWriter]] = {}
    for writer in writers:
        for index in writer.window:
            grouped.setdefault(index, []).append(writer)
    return {index: tuple(chosen) for index, chosen in grouped.items()}


def _seal_bundles(
    streams: Sequence[dict[str, Any]],
    writers: Sequence[_FrameWriter],
    staged_dirs: Sequence[Path],
    corpus: dict[str, JsonValue],
    media: dict[str, Any],
    policy_sha256: str,
) -> None:
    for stream, writer, staged in zip(streams, writers, staged_dirs, strict=True):
        body = _bundle_body(stream, corpus, media, policy_sha256, writer)
        write_sealed(staged / MANIFEST_NAME, seal(body))


def _compared_facts(decoded: Mapping[str, JsonValue], media: Mapping[str, Any]) -> set[str]:
    """Return the decode facts to compare, treating an absent stream index as the first stream."""
    keys = set(decoded)
    if VIDEO_STREAM_INDEX in media:
        keys.add(VIDEO_STREAM_INDEX)
    return keys


def _fact_differs(decoded: Mapping[str, JsonValue], media: Mapping[str, Any], key: str) -> bool:
    if key == VIDEO_STREAM_INDEX:
        return bool(decoded.get(key, 0) != media.get(key, 0))
    return bool(media[key] != decoded[key])


def _require_same_decode(
    decoded: Mapping[str, JsonValue],
    media: Mapping[str, Any],
    streams: Sequence[Mapping[str, Any]],
) -> None:
    """A decode that disagrees with the import record means the decoder is not reproducing it."""
    compared = _compared_facts(decoded, media)
    differing = sorted(key for key in compared if _fact_differs(decoded, media, key))
    if not differing:
        return
    raise CorpusRefusal(
        RefusalCode.DECODE_DRIFT,
        "this decode differs from the imported source record",
        _drift_details(differing, [str(stream["stream_id"]) for stream in streams]),
    )


def _drift_details(fields: list[str], stream_ids: list[str]) -> dict[str, JsonValue]:
    """Name the fields that moved and every stream this pass was writing."""
    listed: list[JsonValue] = []
    named: list[JsonValue] = []
    for field in fields:
        listed.append(field)
    for stream_id in stream_ids:
        named.append(stream_id)
    if len(named) == 1:
        return {"fields": listed, "stream_id": named[0]}
    return {"fields": listed, "stream_ids": named}


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


def _warn_about_conversion(
    stream_ids: Sequence[str], media: Mapping[str, Any], matrix: int | None
) -> None:
    """Both facts stay in each bundle record; say them once for the source."""
    subject = _stream_subject(stream_ids)
    bits = media["source_bits_per_component"]
    if bits > OUTPUT_BITS_PER_COMPONENT:
        _LOG.warning("%s: %d-bit source staged at 8 bits", subject, bits)
    unspecified = media["color"]["matrix"] == UNSPECIFIED_COLOR_MATRIX
    if matrix is None and unspecified and uses_color_matrix(media["source_pixel_format"]):
        _LOG.warning("%s: no color matrix tag, converted as BT.601", subject)


def _stream_subject(stream_ids: Sequence[str]) -> str:
    if len(stream_ids) == 1:
        return f"stream {stream_ids[0]}"
    return "streams " + ", ".join(stream_ids)
