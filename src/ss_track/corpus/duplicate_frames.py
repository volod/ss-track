"""Read the frame indexes of a staged version and of its declared chain, for the shared-run rule.

`shared_runs.py` owns the rule and reads what it is given. This module finds what there is to give it
on disk, and says what it could not find, because a version that was not compared has not been
shown to be clear. Only streams are read: a generated case stays in its parent's group and holds
nothing but its parent's frames or new ones.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.corpus.builder import load_corpus_manifest
from ss_track.corpus.frame_set import frame_set_path
from ss_track.corpus.frames import frames_root, open_corpus_bundle
from ss_track.corpus.lineage import follow_links
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.shared_runs import (
    MIN_SHARED_FRAMES,
    StreamFrames,
    require_unshared_runs,
    stream_frames,
)

MANIFEST_REMOVED = "manifest_removed"
NO_FRAME_SET = "no_frame_set"
BUNDLES_REMOVED = "bundles_removed"
OTHER_DECODE_POLICY = "other_decode_policy"

type Manifest = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class NotCompared:
    """A declared predecessor, or some of its streams, that this check cannot speak for."""

    corpus_id: str
    reason: str
    stream_ids: tuple[str, ...] = ()

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {
            "corpus_id": self.corpus_id,
            "reason": self.reason,
            "stream_ids": list(self.stream_ids),
        }


@dataclass(frozen=True, slots=True)
class SharedFramesCheck:
    """What a passed check compared. Everything else in the chain stays unknown, not clear."""

    compared_versions: tuple[str, ...]
    not_compared: tuple[NotCompared, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {
            "min_shared_frames": MIN_SHARED_FRAMES,
            "compared_versions": list(self.compared_versions),
            "not_compared": [entry.to_record() for entry in self.not_compared],
        }


@dataclass(frozen=True, slots=True)
class _ChainStep:
    """What one predecessor gave the check, and what it could not show."""

    indexes: list[StreamFrames]
    gaps: list[NotCompared]


def _indexed(version: Manifest, stream: Mapping[str, Any], data_root: Path) -> StreamFrames:
    corpus_id = version["corpus_id"]
    bundle = open_corpus_bundle(stream["stream_id"], version, frames_root(data_root, corpus_id))
    entries = ((entry.frame_index, entry.sha256) for entry in bundle.entries)
    return stream_frames(corpus_id, stream, entries)


def _linked_versions(
    corpus: Manifest, data_root: Path
) -> tuple[list[Manifest], NotCompared | None]:
    """Return what the chain reaches. A removed manifest ends it, as older links went with it."""
    reached: list[Manifest] = []
    try:
        for version in follow_links(corpus, lambda name: load_corpus_manifest(name, data_root)):
            reached.append(version)
    except CorpusRefusal as refusal:
        if refusal.code is not RefusalCode.CORPUS_NOT_BUILT:
            raise
        return reached, NotCompared(str(refusal.details["corpus_id"]), MANIFEST_REMOVED)
    return reached, None


def _staged_streams(version: Manifest, policy: str, data_root: Path) -> _ChainStep:
    """Read one predecessor's indexes, and say what they cannot show.

    A version with no frame set never finished staging, so nothing ever pinned it. Comparing with
    one would also refuse the very version that repairs it, since its streams still hold the copy.
    Another decode policy can hash the same frames differently, so a match there still refuses and
    finding none proves nothing.
    """
    corpus_id = version["corpus_id"]
    if not frame_set_path(data_root, corpus_id).is_file():
        return _ChainStep([], [NotCompared(corpus_id, NO_FRAME_SET)])
    root = frames_root(data_root, corpus_id)
    indexes: list[StreamFrames] = []
    removed: list[str] = []
    for stream in version["streams"]:
        if (root / stream["stream_id"]).is_dir():
            indexes.append(_indexed(version, stream, data_root))
        else:
            removed.append(stream["stream_id"])
    gaps = [NotCompared(corpus_id, BUNDLES_REMOVED, tuple(removed))] if removed else []
    if indexes and version["decode_policy_sha256"] != policy:
        gaps.append(NotCompared(corpus_id, OTHER_DECODE_POLICY))
    return _ChainStep(indexes, gaps)


def require_unshared_frames(corpus: Manifest, data_root: Path) -> SharedFramesCheck:
    """Refuse a run of identical frames across groups, here or against the declared chain."""
    versions, broken = _linked_versions(corpus, data_root)
    steps = [
        (version["corpus_id"], _staged_streams(version, corpus["decode_policy_sha256"], data_root))
        for version in versions
    ]
    current = [_indexed(corpus, stream, data_root) for stream in corpus["streams"]]
    earlier = [stream for _, step in steps for stream in step.indexes]
    require_unshared_runs(corpus["corpus_id"], current, earlier)
    gaps = [gap for _, step in steps for gap in step.gaps]
    return SharedFramesCheck(
        tuple(corpus_id for corpus_id, step in steps if step.indexes),
        (*gaps, *([broken] if broken else [])),
    )
