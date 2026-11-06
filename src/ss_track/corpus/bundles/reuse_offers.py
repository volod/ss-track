"""Bundles in a declared chain that a later version may reuse.

A candidate is a finished bundle on this data root. Its layout is known without reading frame
bytes. A record this code cannot read, or whose hash does not describe an identity, is not a
candidate. A bundle staged for another version or stream still refuses.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import require_bundle_place
from ss_track.corpus.bundles.bundle_record import LAYOUT_FIELDS
from ss_track.corpus.bundles.duplicate_frames import linked_versions
from ss_track.corpus.records.kinds import FRAME_BUNDLE
from ss_track.corpus.records.read_refusals import incomplete_record
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.storage.layout import MANIFEST_NAME, frame_set_path, frames_root


@dataclass(frozen=True, slots=True)
class BundleOffer:
    """One staged bundle whose layout can be compared before a decode."""

    corpus_id: str
    stream_id: str
    directory: Path
    bundle_sha256: str
    layout: dict[str, JsonValue]


def bundle_offers(corpus: Mapping[str, Any], data_root: Path) -> tuple[BundleOffer, ...]:
    """Return reusable bundles of the declared chain, nearest version first."""
    versions, _gap = linked_versions(corpus, data_root)
    offers: list[BundleOffer] = []
    for version in versions:
        corpus_id = str(version["corpus_id"])
        if not frame_set_path(data_root, corpus_id).is_file():
            continue
        root = frames_root(data_root, corpus_id)
        for stream in _streams(version):
            stream_id = str(stream["stream_id"])
            directory = root / stream_id
            if directory.is_dir() and (offer := _offer(version, stream_id, directory)) is not None:
                offers.append(offer)
    return tuple(offers)


def sealed_frames(directory: Path) -> list[JsonValue]:
    """Return the sealed frame index a predicted bundle hash covers."""
    manifest = read_sealed(directory / MANIFEST_NAME, FRAME_BUNDLE)
    with incomplete_record(MANIFEST_NAME):
        frames = _identity(manifest)["frames"]
    if not isinstance(frames, list):
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "bundle frame index is not a list",
            {"record": MANIFEST_NAME},
        )
    return cast(list[JsonValue], frames)


def _streams(version: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    streams = version["streams"]
    if not isinstance(streams, list):
        return []
    return [stream for stream in streams if isinstance(stream, Mapping)]


def _offer(version: Mapping[str, Any], stream_id: str, directory: Path) -> BundleOffer | None:
    """Read one candidate. An unusable record is skipped; a misplaced bundle still refuses."""
    try:
        manifest = read_sealed(directory / MANIFEST_NAME, FRAME_BUNDLE)
    except CorpusRefusal as refusal:
        if refusal.code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED:
            return None
        raise
    try:
        with incomplete_record(MANIFEST_NAME):
            require_bundle_place(
                stream_id,
                version,
                manifest["corpus_manifest_sha256"],
                manifest["stream_id"],
            )
            layout = {key: _identity(manifest)[key] for key in LAYOUT_FIELDS}
            digest = manifest["bundle_sha256"]
    except CorpusRefusal as refusal:
        if refusal.code is RefusalCode.RECORD_TAMPERED:
            return None
        raise
    if not isinstance(digest, str):
        return None
    return BundleOffer(str(version["corpus_id"]), stream_id, directory, digest, layout)


def _identity(manifest: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Return a bundle identity. A missing one is an incomplete record for the caller."""
    identity = manifest["identity"]
    if not isinstance(identity, dict):
        raise TypeError(MANIFEST_NAME)
    return cast(dict[str, JsonValue], identity)
