"""Reuse frames a linked corpus version already staged.

The bundle hash is fixed by the source, the decode policy, the pixel layout and the sealed frame
index. Those are known before a decode, so a matching bundle in the declared chain can be checked
and hard-linked. The new version writes its own bundle record. A version the declaration does not
link is not a candidate, and a different policy or window does not match.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_frame_bundle
from ss_track.corpus.bundles.bundle_record import stream_bundle_body, stream_identity, stream_layout
from ss_track.corpus.bundles.frame_store import linked_name
from ss_track.corpus.bundles.frames import FrameBundle, bundle_hash, damage_details, frame_name
from ss_track.corpus.bundles.publish import publish_bundle
from ss_track.corpus.bundles.reuse_offers import BundleOffer, sealed_frames
from ss_track.corpus.sources.stored import (
    VerifiedSource,
    load_source_record,
    load_verified_source,
    source_sequence,
)
from ss_track.corpus.storage.layout import MANIFEST_NAME

type _Media = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ReusedBundle:
    """A bundle this run linked, and the linked version it came from."""

    bundle: FrameBundle
    origin_corpus_id: str
    origin_stream_id: str


@dataclass(frozen=True, slots=True)
class ReusePass:
    """Streams linked from the chain, streams that still need a decode, and a checked source."""

    reused: tuple[ReusedBundle, ...]
    remaining: tuple[dict[str, Any], ...]
    verified_source: VerifiedSource | None


class _DecodeInstead(Exception):
    """This host cannot hard-link the candidate, so the stream is decoded."""


def reuse_streams(
    streams: Sequence[dict[str, Any]],
    offers: Sequence[BundleOffer],
    corpus: Mapping[str, JsonValue],
    policy_sha256: str,
    root: Path,
    data_root: Path,
) -> ReusePass:
    """Link streams whose bundle hash a linked version already sealed. The rest stay pending.

    Frame files are checked before any link. A damaged candidate is refused and nothing from this
    source is linked. A filesystem that cannot link one stream decodes that stream.
    """
    if not streams or not offers:
        return ReusePass((), tuple(streams), None)
    source_sha256 = str(streams[0]["source_sha256"])
    media = source_sequence(load_source_record(source_sha256, data_root))
    chosen: list[tuple[dict[str, Any], BundleOffer, list[JsonValue]]] = []
    remaining: list[dict[str, Any]] = []
    for stream in streams:
        match = _match(stream, media, policy_sha256, offers)
        if match is None:
            remaining.append(stream)
        else:
            chosen.append((stream, *match))
    if not chosen:
        return ReusePass((), tuple(remaining), None)
    verified = load_verified_source(source_sha256, data_root)
    ready: list[tuple[dict[str, Any], BundleOffer, list[JsonValue], FrameBundle]] = []
    for stream, offer, frames in chosen:
        ready.append((stream, offer, frames, _require_intact(offer, str(stream["stream_id"]))))
    reused: list[ReusedBundle] = []
    for stream, offer, frames, bundle in ready:
        published = _publish(stream, corpus, media, policy_sha256, offer, frames, bundle, root)
        if published is None:
            remaining.append(stream)
        else:
            reused.append(ReusedBundle(published, offer.corpus_id, offer.stream_id))
    return ReusePass(tuple(reused), tuple(remaining), verified)


def _match(
    stream: Mapping[str, Any],
    media: Mapping[str, Any],
    policy_sha256: str,
    offers: Sequence[BundleOffer],
) -> tuple[BundleOffer, list[JsonValue]] | None:
    """Return the nearest bundle whose predicted hash is its sealed hash."""
    expected = stream_layout(stream, media, policy_sha256)
    for offer in offers:
        if offer.layout != expected:
            continue
        frames = sealed_frames(offer.directory)
        identity = stream_identity(stream, media, policy_sha256, frames)
        if bundle_hash(identity) == offer.bundle_sha256:
            return offer, frames
    return None


def _require_intact(offer: BundleOffer, stream_id: str) -> FrameBundle:
    """Refuse a candidate whose files differ from the index it would be linked from."""
    bundle = open_frame_bundle(offer.directory)
    damage = bundle.damage()
    if not damage:
        return bundle
    raise CorpusRefusal(
        RefusalCode.FRAME_CORRUPTED,
        f"bundle {offer.corpus_id}/{offer.stream_id} does not match its sealed index, "
        f"first {damage[0].frame}; it was not linked",
        {
            "stream_id": stream_id,
            "candidate_corpus_id": offer.corpus_id,
            "candidate_stream_id": offer.stream_id,
        }
        | damage_details(damage),
    )


def _publish(
    stream: Mapping[str, Any],
    corpus: Mapping[str, JsonValue],
    media: Mapping[str, Any],
    policy_sha256: str,
    offer: BundleOffer,
    frames: Sequence[JsonValue],
    bundle: FrameBundle,
    root: Path,
) -> FrameBundle | None:
    """Link one bundle into this version, or return None when this host cannot link."""
    target = root / str(stream["stream_id"])
    try:
        with publish_bundle(root, target) as staged:
            if not _link_frames(bundle, staged):
                raise _DecodeInstead
            body = stream_bundle_body(stream, corpus, media, policy_sha256, frames)
            _require_same_hash(stream, offer, body["bundle_sha256"])
            write_sealed(staged / MANIFEST_NAME, seal(body))
    except _DecodeInstead:
        return None
    return open_frame_bundle(target)


def _require_same_hash(stream: Mapping[str, Any], offer: BundleOffer, digest: JsonValue) -> None:
    """A reused record that hashes differently is a defect, and it is not published."""
    if digest == offer.bundle_sha256:
        return
    raise CorpusRefusal(
        RefusalCode.RECORD_INVALID,
        "reused bundle hash does not match its candidate",
        {
            "stream_id": stream["stream_id"],
            "candidate_corpus_id": offer.corpus_id,
            "bundle_sha256": digest,
            "candidate_bundle_sha256": offer.bundle_sha256,
        },
    )


def _link_frames(bundle: FrameBundle, staged: Path) -> bool:
    """Link every frame. False means stop and decode, leaving this scratch unpublished."""
    for entry in bundle.entries:
        name = frame_name(entry.frame_index, bundle.pixel_format)
        if not linked_name(bundle.directory / name, staged / name):
            return False
    return True
