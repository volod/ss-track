"""`ss-track corpus verify`: the source terms hold, the bundles are the frame set's, frames are intact.

Each bundle record is opened once, and a frame file with more than one name is hashed once.
"""

from datetime import date
from pathlib import Path

from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.duplicate_frames import require_unshared_frames
from ss_track.corpus.bundles.frame_set import require_frame_set
from ss_track.corpus.bundles.frames import FileDigests, FrameDamage, frames_corrupted
from ss_track.corpus.bundles.stage_report import FramesResult, bundle_hashes, summarize
from ss_track.corpus.bundles.version_bundles import (
    declared_cases,
    declared_streams,
    open_case,
    require_sources_hold,
)
from ss_track.corpus.sources.terms import evaluation_date
from ss_track.corpus.storage.layout import frame_set_path, frames_root
from ss_track.corpus.versions.manifests import load_corpus_manifest

VERIFIED = "verified"


def verify_corpus_frames(
    corpus_id: str, data_root: Path, *, today: date | None = None
) -> FramesResult:
    """Prove the source terms hold, the bundles are the frame set's, and every frame is intact.

    Source records are read and stored sources are not: a frame's hash covers what modules receive,
    and staging is what ties those frames to the source bytes. Shared frames are checked again
    because a predecessor staged after this version was not there to compare with.
    """
    checked_on = evaluation_date(today)
    corpus = load_corpus_manifest(corpus_id, data_root)
    require_sources_hold(corpus, data_root, checked_on)
    root = frames_root(data_root, corpus_id)
    streams = {
        stream["stream_id"]: open_corpus_bundle(stream["stream_id"], corpus, root)
        for stream in declared_streams(corpus)
    }
    cases = [open_case(case, corpus, root, streams.__getitem__) for case in declared_cases(corpus)]
    bundles = [*streams.values(), *cases]
    hashes = bundle_hashes(bundles)
    if frame_set_path(data_root, corpus_id).is_file():
        frame_set_sha256 = require_frame_set(corpus, hashes, data_root)
        shared_frames = require_unshared_frames(corpus, data_root, streams.__getitem__)
    else:
        shared_frames = require_unshared_frames(corpus, data_root, streams.__getitem__)
        frame_set_sha256 = require_frame_set(corpus, hashes, data_root)
    digests = FileDigests()
    damage: list[FrameDamage] = [item for bundle in bundles for item in bundle.damage(digests)]
    if damage:
        raise frames_corrupted(damage)
    return FramesResult(
        VERIFIED,
        corpus_id,
        frame_set_sha256,
        tuple(summarize(bundle, VERIFIED) for bundle in bundles),
        shared_frames,
    )
