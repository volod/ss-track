"""Opening a staged bundle: its sealed record, its place in a corpus version, and its index.

A bundle record is read through the read path, and its bundle hash must cover its frame index
before anything else is believed. `corpus.bundles.frames` holds the opened bundle and its frame checks.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.frames import (
    FRAME_BUNDLE,
    IDENTITY_TRANSFORM,
    FrameBundle,
    FrameEntry,
    bundle_hash,
)
from ss_track.corpus.records.read_refusals import incomplete_record
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.sources.importer import MANIFEST_NAME


def read_bundle_record(directory: Path) -> dict[str, Any]:
    """Read a bundle's sealed record, refusing one whose bundle hash does not cover its index."""
    manifest: dict[str, Any] = read_sealed(directory / MANIFEST_NAME, FRAME_BUNDLE)
    with incomplete_record(MANIFEST_NAME):
        covered = bundle_hash(_identity(manifest)) == manifest["bundle_sha256"]
    if not covered:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "bundle hash does not cover this frame index",
            {"record": MANIFEST_NAME},
        )
    return manifest


def open_frame_bundle(directory: Path) -> FrameBundle:
    """Open a bundle directory, refusing one whose record is not intact."""
    manifest = read_bundle_record(directory)
    with incomplete_record(MANIFEST_NAME):
        return _parse_bundle(directory, manifest)


def content_frame_index(entry: Mapping[str, Any]) -> int:
    """Return the source frame whose pixels an index entry holds: its own unless it repeats one."""
    return int(entry.get("content_frame_index", entry["frame_index"]))


def open_corpus_bundle(stream_id: str, corpus: Mapping[str, Any], root: Path) -> FrameBundle:
    """Open one bundle, which must have been staged from this exact corpus version."""
    directory = root / stream_id
    if not directory.is_dir():
        raise CorpusRefusal(
            RefusalCode.BUNDLE_NOT_STAGED,
            "this stream has no staged frame bundle",
            {"stream_id": stream_id},
        )
    bundle = open_frame_bundle(directory)
    require_bundle_place(stream_id, corpus, bundle.corpus_manifest_sha256, bundle.stream_id)
    return bundle


def require_bundle_place(
    stream_id: str, corpus: Mapping[str, Any], staged_from: JsonValue, bundle_stream_id: JsonValue
) -> None:
    """Refuse a bundle staged from another corpus version, or holding another stream."""
    if staged_from != corpus[SEAL_FIELD]:
        raise CorpusRefusal(
            RefusalCode.BUNDLE_CONFLICT,
            "this bundle was staged from a different corpus version",
            {
                "stream_id": stream_id,
                "bundle_corpus_manifest_sha256": staged_from,
                "corpus_manifest_sha256": corpus[SEAL_FIELD],
            },
        )
    if bundle_stream_id != stream_id:
        raise CorpusRefusal(
            RefusalCode.BUNDLE_CONFLICT,
            "this bundle belongs to another stream, which may sit in another split",
            {"stream_id": stream_id, "bundle_stream_id": bundle_stream_id},
        )


def _identity(manifest: Mapping[str, Any]) -> dict[str, JsonValue]:
    identity: dict[str, JsonValue] = manifest["identity"]
    return identity


def _parse_bundle(directory: Path, manifest: Mapping[str, Any]) -> FrameBundle:
    identity: Mapping[str, Any] = _identity(manifest)
    window = identity["selection"]
    # Only a generated bundle has a recipe; its lookups stay inside this KeyError guard.
    recipe = identity["recipe"] if manifest["generated"] is not None else None
    return FrameBundle(
        directory=directory,
        stream_id=manifest["stream_id"],
        corpus_manifest_sha256=manifest["corpus_manifest_sha256"],
        bundle_sha256=manifest["bundle_sha256"],
        source_sha256=identity["source_sha256"],
        pixel_format=identity["pixel_format"],
        width=identity["width"],
        height=identity["height"],
        time_base=identity["time_base"],
        timestamp_quality=manifest["timestamp_quality"],
        capture_clock_evidence=manifest["capture_clock_evidence"],
        selection=range(window["start_frame"], window["end_frame"]),
        entries=tuple(
            FrameEntry(
                entry["frame_index"],
                # `content_frame_index` inline: a call per frame is 2% of opening a million frames
                entry.get("content_frame_index", entry["frame_index"]),
                entry["pts"],
                entry["sha256"],
            )
            for entry in identity["frames"]
        ),
        transform=IDENTITY_TRANSFORM if recipe is None else recipe["transform"],
        parent_bundle_sha256=None if recipe is None else identity["parent_bundle_sha256"],
    )
