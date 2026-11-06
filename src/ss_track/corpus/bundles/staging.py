"""`ss-track corpus stage` and `corpus verify`: one immutable frame bundle per corpus stream."""

import fcntl
import shutil
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.bundle_writer import write_source_bundles
from ss_track.corpus.bundles.duplicate_frames import SharedFramesCheck, require_unshared_frames
from ss_track.corpus.bundles.frame_set import commit_frame_set, frame_set_path, require_frame_set
from ss_track.corpus.bundles.frames import FrameBundle, FrameDamage, frames_corrupted, frames_root
from ss_track.corpus.bundles.reuse import reuse_streams
from ss_track.corpus.bundles.reuse_offers import bundle_offers
from ss_track.corpus.bundles.stage_report import BundleSummary, FramesResult
from ss_track.corpus.cases.generated import write_case_bundle
from ss_track.corpus.cases.transforms import require_transform_revision
from ss_track.corpus.decoding.decode_policy import DecodePolicy, current_decode_policy
from ss_track.corpus.records.sealing import SCRATCH_PREFIX
from ss_track.corpus.sources.importer import MANIFEST_NAME, decode_policy_sha256
from ss_track.corpus.sources.stored import require_source_record
from ss_track.corpus.sources.terms import evaluation_date, require_retention
from ss_track.corpus.versions.builder import load_corpus_manifest, require_policy

STAGED = "staged"
REUSED = "reused"
UNCHANGED = "unchanged"
VERIFIED = "verified"
_LOCK_NAME = ".staging.lock"


def _summary(
    bundle: FrameBundle, status: str, *, origin: tuple[str, str] | None = None
) -> BundleSummary:
    corpus_id, stream_id = origin if origin is not None else (None, None)
    return BundleSummary(
        stream_id=bundle.stream_id,
        status=status,
        transform=bundle.transform,
        bundle_sha256=bundle.bundle_sha256,
        frame_count=len(bundle),
        pixel_format=bundle.pixel_format,
        width=bundle.width,
        height=bundle.height,
        manifest_path=str(bundle.directory / MANIFEST_NAME),
        origin_corpus_id=corpus_id,
        origin_stream_id=stream_id,
    )


def _hashes(bundles: Iterable[BundleSummary | FrameBundle]) -> dict[str, str]:
    return {bundle.stream_id: bundle.bundle_sha256 for bundle in bundles}


def _streams(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    streams: list[dict[str, Any]] = corpus["streams"]
    return streams


def _cases(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = corpus["generated_cases"]
    return cases


def _require_sources_hold(corpus: dict[str, Any], data_root: Path, today: date) -> None:
    """Refuse a corpus outside its recorded terms, before any bundle is written, skipped or hashed.

    Retention goes first because it reads only the corpus, so removing expired material, which is
    the operator's to do, cannot turn the reason into a missing record. A generated case holds its
    parent's rights, so checking every stream covers every case.
    """
    for stream in _streams(corpus):
        require_retention(stream, today)
    for stream in _streams(corpus):
        require_source_record(stream, data_root)


def stage_corpus(corpus_id: str, data_root: Path, *, today: date | None = None) -> FramesResult:
    """Stage every stream and case, then seal the frame set. A failure leaves it unwritten.

    Pending streams of one source share one strict decode. A first stage refuses a repeated run
    before its cases. An existing frame set is matched first.
    """
    checked_on = evaluation_date(today)
    corpus = load_corpus_manifest(corpus_id, data_root)
    _require_sources_hold(corpus, data_root, checked_on)
    policy = current_decode_policy()
    policy_sha256 = decode_policy_sha256(policy.as_record())
    require_policy(corpus["decode_policy_sha256"], policy_sha256, f"corpus {corpus_id}")
    for case in _cases(corpus):
        require_transform_revision(case)
    root = frames_root(data_root, corpus_id)
    root.mkdir(parents=True, exist_ok=True)
    with _exclusive_staging(root, corpus_id):
        streams = _stage_streams(corpus, policy, root, data_root)
        frame_set_sha256, written, bundles, shared_frames = _seal_stage(
            corpus, streams, root, data_root
        )
    changed = written or any(bundle.status in {STAGED, REUSED} for bundle in bundles)
    status = STAGED if changed else UNCHANGED
    return FramesResult(status, corpus_id, frame_set_sha256, bundles, shared_frames)


def _seal_stage(
    corpus: dict[str, JsonValue],
    streams: tuple[BundleSummary, ...],
    root: Path,
    data_root: Path,
) -> tuple[str, bool, tuple[BundleSummary, ...], SharedFramesCheck]:
    """Match an existing frame set before a repeated run, and a run before a new frame set."""
    path = frame_set_path(data_root, str(corpus["corpus_id"]))
    shared = None if path.is_file() else require_unshared_frames(corpus, data_root)
    cases = tuple(_stage_case(case, corpus, root) for case in _cases(corpus))
    bundles = (*streams, *cases)
    sealed, written = commit_frame_set(corpus, _hashes(bundles), data_root)
    if shared is None:
        shared = require_unshared_frames(corpus, data_root)
    return sealed, written, bundles, shared


@contextmanager
def _exclusive_staging(root: Path, corpus_id: str) -> Iterator[None]:
    """Hold a lock the kernel drops however a run ends, then clear what a killed run left.

    Holding the lock proves no other run owns a scratch directory, and a killed run's raw frames
    could otherwise fill the disk with nothing to remove them. Only the frame set is written beside
    the manifest, and a stage implies a finished build, so a partial file there is ours as well.
    """
    with (root / _LOCK_NAME).open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CorpusRefusal(
                RefusalCode.STAGING_IN_PROGRESS,
                "another run is staging this corpus version",
                {"corpus_id": corpus_id},
            ) from error
        for leftover in root.glob(f"{SCRATCH_PREFIX}*"):
            shutil.rmtree(leftover)
        for partial in root.parent.glob(f"{SCRATCH_PREFIX}*"):
            partial.unlink()
        yield


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
    _require_sources_hold(corpus, data_root, checked_on)
    root = frames_root(data_root, corpus_id)
    bundles = [open_corpus_bundle(stream["stream_id"], corpus, root) for stream in _streams(corpus)]
    bundles += [_open_case(case, corpus, root) for case in _cases(corpus)]
    hashes = _hashes(bundles)
    if frame_set_path(data_root, corpus_id).is_file():
        frame_set_sha256 = require_frame_set(corpus, hashes, data_root)
        shared_frames = require_unshared_frames(corpus, data_root)
    else:
        shared_frames = require_unshared_frames(corpus, data_root)
        frame_set_sha256 = require_frame_set(corpus, hashes, data_root)
    damage: list[FrameDamage] = [item for bundle in bundles for item in bundle.damage()]
    if damage:
        raise frames_corrupted(damage)
    return FramesResult(
        VERIFIED,
        corpus_id,
        frame_set_sha256,
        tuple(_summary(bundle, VERIFIED) for bundle in bundles),
        shared_frames,
    )


def _open_case(case: dict[str, Any], corpus: dict[str, JsonValue], root: Path) -> FrameBundle:
    """Open one case's bundle, which must derive from the parent frames staged here now."""
    bundle = open_corpus_bundle(case["case_id"], corpus, root)
    parent = open_corpus_bundle(case["parent_stream_id"], corpus, root)
    if bundle.parent_bundle_sha256 != parent.bundle_sha256:
        raise CorpusRefusal(
            RefusalCode.BUNDLE_CONFLICT,
            "this generated case derives from frames other than its parent's",
            {
                "stream_id": case["case_id"],
                "parent_stream_id": case["parent_stream_id"],
                "case_parent_bundle_sha256": bundle.parent_bundle_sha256,
                "parent_bundle_sha256": parent.bundle_sha256,
            },
        )
    return bundle


def _stage_streams(
    corpus: dict[str, JsonValue],
    policy: DecodePolicy,
    root: Path,
    data_root: Path,
) -> tuple[BundleSummary, ...]:
    """Stage each missing stream. One source is decoded once, however many streams it still owes."""
    declared = _streams(corpus)
    summaries: dict[str, BundleSummary] = {}
    pending: dict[str, list[dict[str, Any]]] = {}
    for stream in declared:
        stream_id = str(stream["stream_id"])
        if (root / stream_id).exists():
            summaries[stream_id] = _unchanged(open_corpus_bundle(stream_id, corpus, root))
        else:
            pending.setdefault(str(stream["source_sha256"]), []).append(stream)
    offers = bundle_offers(corpus, data_root) if pending else ()
    policy_sha256 = decode_policy_sha256(policy.as_record())
    for streams in pending.values():
        passed = reuse_streams(streams, offers, corpus, policy_sha256, root, data_root)
        for item in passed.reused:
            summaries[item.bundle.stream_id] = _summary(
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
                summaries[bundle.stream_id] = _summary(bundle, STAGED)
    return tuple(summaries[str(stream["stream_id"])] for stream in declared)


def _stage_case(case: dict[str, Any], corpus: dict[str, JsonValue], root: Path) -> BundleSummary:
    if (root / case["case_id"]).exists():
        return _unchanged(_open_case(case, corpus, root))
    parent = open_corpus_bundle(case["parent_stream_id"], corpus, root)
    return _summary(write_case_bundle(case, parent, root), STAGED)


def _unchanged(bundle: FrameBundle) -> BundleSummary:
    """Re-hash a bundle that already exists, because staging repairs nothing."""
    if damage := bundle.damage():
        raise frames_corrupted(damage)
    return _summary(bundle, UNCHANGED)
