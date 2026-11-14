"""`ss-track corpus stage`: one immutable frame bundle per corpus stream and generated case.

A stage opens a parent bundle once for a run of its cases and hashes a linked frame file once,
however many cases or names share it. `corpus verify` is `corpus.bundles.verification`.
"""

from datetime import date
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.core.scratch import exclusive_lock
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.bundle_writer import write_source_bundles
from ss_track.corpus.bundles.duplicate_frames import SharedFramesCheck, require_unshared_frames
from ss_track.corpus.bundles.frame_set import commit_frame_set
from ss_track.corpus.bundles.frames import FileDigests, FrameBundle, frames_corrupted
from ss_track.corpus.bundles.reuse import reuse_streams
from ss_track.corpus.bundles.reuse_offers import bundle_offers
from ss_track.corpus.bundles.stage_report import (
    BundleSummary,
    FramesResult,
    bundle_hashes,
    summarize,
)
from ss_track.corpus.bundles.version_bundles import (
    Manifest,
    ParentBundle,
    declared_cases,
    declared_streams,
    open_case,
    require_sources_hold,
)
from ss_track.corpus.cases.generated import write_case_bundle
from ss_track.corpus.cases.transforms import require_transform_revision
from ss_track.corpus.decoding.decode_policy import (
    DecodePolicy,
    current_decode_policy,
    require_policy,
)
from ss_track.corpus.sources.terms import evaluation_date
from ss_track.corpus.storage.layout import frame_set_path, frames_root
from ss_track.corpus.versions.manifests import load_corpus_manifest

STAGED = "staged"
REUSED = "reused"
UNCHANGED = "unchanged"
_LOCK_NAME = ".staging.lock"


def stage_corpus(corpus_id: str, data_root: Path, *, today: date | None = None) -> FramesResult:
    """Stage every stream and case, then seal the frame set. A failure leaves it unwritten.

    Pending streams of one source share one strict decode. A first stage refuses a repeated run
    before its cases. An existing frame set is matched first.

    The staging lock proves no other run owns a scratch directory, and a killed run's raw frames
    could otherwise fill the disk with nothing to remove them. Only the frame set is written beside
    the manifest, and a stage implies a finished build, so a partial file there is ours as well.
    """
    checked_on = evaluation_date(today)
    corpus = load_corpus_manifest(corpus_id, data_root)
    require_sources_hold(corpus, data_root, checked_on)
    policy = current_decode_policy()
    require_policy(corpus["decode_policy_sha256"], policy.sha256(), f"corpus {corpus_id}")
    for case in declared_cases(corpus):
        require_transform_revision(case)
    root = frames_root(data_root, corpus_id)
    busy = CorpusRefusal(
        RefusalCode.STAGING_IN_PROGRESS,
        "another run is staging this corpus version",
        {"corpus_id": corpus_id},
    )
    with exclusive_lock(root, _LOCK_NAME, clear=(root, root.parent), busy=busy):
        digests = FileDigests()
        streams = _stage_streams(corpus, policy, root, data_root, digests)
        frame_set_sha256, written, bundles, shared_frames = _seal_stage(
            corpus, streams, root, data_root, digests
        )
    changed = written or any(bundle.status in {STAGED, REUSED} for bundle in bundles)
    status = STAGED if changed else UNCHANGED
    return FramesResult(status, corpus_id, frame_set_sha256, bundles, shared_frames)


def _seal_stage(
    corpus: Manifest,
    streams: tuple[BundleSummary, ...],
    root: Path,
    data_root: Path,
    digests: FileDigests,
) -> tuple[str, bool, tuple[BundleSummary, ...], SharedFramesCheck]:
    """Match an existing frame set before a repeated run, and a run before a new frame set."""
    path = frame_set_path(data_root, str(corpus["corpus_id"]))
    shared = None if path.is_file() else require_unshared_frames(corpus, data_root)
    cases = _stage_cases(corpus, root, digests)
    bundles = (*streams, *cases)
    sealed, written = commit_frame_set(corpus, bundle_hashes(bundles), data_root)
    if shared is None:
        shared = require_unshared_frames(corpus, data_root)
    return sealed, written, bundles, shared


def _stage_streams(
    corpus: Manifest,
    policy: DecodePolicy,
    root: Path,
    data_root: Path,
    digests: FileDigests,
) -> tuple[BundleSummary, ...]:
    """Stage each missing stream. One source is decoded once, however many streams it still owes."""
    declared = declared_streams(corpus)
    summaries: dict[str, BundleSummary] = {}
    pending: dict[str, list[dict[str, Any]]] = {}
    for stream in declared:
        stream_id = str(stream["stream_id"])
        if (root / stream_id).exists():
            bundle = open_corpus_bundle(stream_id, corpus, root)
            summaries[stream_id] = _unchanged(bundle, digests)
        else:
            pending.setdefault(str(stream["source_sha256"]), []).append(stream)
    offers = bundle_offers(corpus, data_root) if pending else ()
    policy_sha256 = policy.sha256()
    for streams in pending.values():
        passed = reuse_streams(streams, offers, corpus, policy_sha256, root, data_root)
        for item in passed.reused:
            summaries[item.bundle.stream_id] = summarize(
                item.bundle, REUSED, origin=(item.origin_corpus_id, item.origin_stream_id)
            )
        if passed.remaining:
            for bundle in write_source_bundles(
                passed.remaining,
                corpus,
                policy,
                root,
                data_root,
                verified_source=passed.verified_source,
            ):
                summaries[bundle.stream_id] = summarize(bundle, STAGED)
    return tuple(summaries[str(stream["stream_id"])] for stream in declared)


def _stage_cases(corpus: Manifest, root: Path, digests: FileDigests) -> tuple[BundleSummary, ...]:
    """Stage each missing case and re-hash each existing one, in `case_id` order."""
    parent_of = ParentBundle(corpus, root)
    staged: list[BundleSummary] = []
    for case in declared_cases(corpus):
        if (root / case["case_id"]).exists():
            staged.append(_unchanged(open_case(case, corpus, root, parent_of), digests))
        else:
            parent = parent_of(case["parent_stream_id"])
            staged.append(summarize(write_case_bundle(case, parent, root), STAGED))
    return tuple(staged)


def _unchanged(bundle: FrameBundle, digests: FileDigests) -> BundleSummary:
    """Re-hash a bundle that already exists, because staging repairs nothing."""
    if damage := bundle.damage(digests):
        raise frames_corrupted(damage)
    return summarize(bundle, UNCHANGED)
