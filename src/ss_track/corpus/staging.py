"""`ss-track corpus stage` and `corpus verify`: one immutable frame bundle per corpus stream."""

import fcntl
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ss_track.corpus.builder import load_corpus_manifest, require_policy, require_source_record
from ss_track.corpus.bundle_writer import SCRATCH_PREFIX, write_bundle
from ss_track.corpus.decode import DecodePolicy, current_decode_policy
from ss_track.corpus.frames import (
    FrameBundle,
    FrameDamage,
    frames_corrupted,
    frames_root,
    open_frame_bundle,
)
from ss_track.corpus.generated import write_case_bundle
from ss_track.corpus.importer import MANIFEST_NAME, decode_policy_sha256
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import SEAL_FIELD
from ss_track.corpus.terms import evaluation_date, require_retention
from ss_track.corpus.transforms import require_transform_revision

STAGED = "staged"
UNCHANGED = "unchanged"
VERIFIED = "verified"
_LOCK_NAME = ".staging.lock"


@dataclass(frozen=True, slots=True)
class BundleSummary:
    """One stream's bundle as reported to the operator."""

    stream_id: str
    status: str
    transform: str
    bundle_sha256: str
    frame_count: int
    pixel_format: str
    width: int
    height: int
    manifest_path: str


@dataclass(frozen=True, slots=True)
class FramesResult:
    """Outcome of staging or verifying every bundle of a corpus version."""

    status: str
    corpus_id: str
    bundles: tuple[BundleSummary, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        record: dict[str, JsonValue] = asdict(self)
        record["bundles"] = [asdict(bundle) for bundle in self.bundles]
        return record


def _summary(bundle: FrameBundle, status: str) -> BundleSummary:
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
    )


def _streams(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    streams: list[dict[str, Any]] = corpus["streams"]
    return streams


def _cases(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = corpus["generated_cases"]
    return cases


def stage_corpus(corpus_id: str, data_root: Path, *, today: date | None = None) -> FramesResult:
    """Stage every stream and generated case, leaving each bundle complete or absent."""
    checked_on = evaluation_date(today)
    corpus = load_corpus_manifest(corpus_id, data_root)
    for stream in _streams(corpus):
        require_retention(stream, checked_on)
    policy = current_decode_policy()
    policy_sha256 = decode_policy_sha256(policy.as_record())
    require_policy(corpus["decode_policy_sha256"], policy_sha256, f"corpus {corpus_id}")
    for stream in _streams(corpus):
        require_source_record(stream, data_root)
    for case in _cases(corpus):
        require_transform_revision(case)
    root = frames_root(data_root, corpus_id)
    root.mkdir(parents=True, exist_ok=True)
    with _exclusive_staging(root, corpus_id):
        streams = [
            _stage_stream(stream, corpus, policy, root, data_root) for stream in _streams(corpus)
        ]
        bundles = (*streams, *(_stage_case(case, corpus, root) for case in _cases(corpus)))
    changed = any(bundle.status == STAGED for bundle in bundles)
    return FramesResult(STAGED if changed else UNCHANGED, corpus_id, bundles)


@contextmanager
def _exclusive_staging(root: Path, corpus_id: str) -> Iterator[None]:
    """Hold a lock the kernel drops however a run ends, then clear what a killed run left.

    Holding the lock proves no other run owns a scratch directory, and a killed run's raw frames
    could otherwise fill the disk with nothing to remove them.
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
        yield


def verify_corpus_frames(
    corpus_id: str, data_root: Path, *, today: date | None = None
) -> FramesResult:
    """Compare every staged frame of a corpus version with its sealed index."""
    checked_on = evaluation_date(today)
    corpus = load_corpus_manifest(corpus_id, data_root)
    for stream in _streams(corpus):
        require_retention(stream, checked_on)
    root = frames_root(data_root, corpus_id)
    bundles = [_open_for_corpus(stream["stream_id"], corpus, root) for stream in _streams(corpus)]
    bundles += [_open_case(case, corpus, root) for case in _cases(corpus)]
    damage: list[FrameDamage] = [item for bundle in bundles for item in bundle.damage()]
    if damage:
        raise frames_corrupted(damage)
    return FramesResult(
        VERIFIED, corpus_id, tuple(_summary(bundle, VERIFIED) for bundle in bundles)
    )


def _open_for_corpus(stream_id: str, corpus: dict[str, JsonValue], root: Path) -> FrameBundle:
    """Open one bundle, which must have been staged from this exact corpus version."""
    directory = root / stream_id
    if not directory.is_dir():
        raise CorpusRefusal(
            RefusalCode.BUNDLE_NOT_STAGED,
            "this stream has no staged frame bundle",
            {"stream_id": stream_id},
        )
    bundle = open_frame_bundle(directory)
    if bundle.corpus_manifest_sha256 != corpus[SEAL_FIELD]:
        raise CorpusRefusal(
            RefusalCode.BUNDLE_CONFLICT,
            "this bundle was staged from a different corpus version",
            {
                "stream_id": stream_id,
                "bundle_corpus_manifest_sha256": bundle.corpus_manifest_sha256,
                "corpus_manifest_sha256": corpus[SEAL_FIELD],
            },
        )
    if bundle.stream_id != stream_id:
        raise CorpusRefusal(
            RefusalCode.BUNDLE_CONFLICT,
            "this bundle belongs to another stream, which may sit in another split",
            {"stream_id": stream_id, "bundle_stream_id": bundle.stream_id},
        )
    return bundle


def _open_case(case: dict[str, Any], corpus: dict[str, JsonValue], root: Path) -> FrameBundle:
    """Open one case's bundle, which must derive from the parent frames staged here now."""
    bundle = _open_for_corpus(case["case_id"], corpus, root)
    parent = _open_for_corpus(case["parent_stream_id"], corpus, root)
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


def _stage_stream(
    stream: dict[str, Any],
    corpus: dict[str, JsonValue],
    policy: DecodePolicy,
    root: Path,
    data_root: Path,
) -> BundleSummary:
    if (root / stream["stream_id"]).exists():
        return _unchanged(_open_for_corpus(stream["stream_id"], corpus, root))
    return _summary(write_bundle(stream, corpus, policy, root, data_root), STAGED)


def _stage_case(case: dict[str, Any], corpus: dict[str, JsonValue], root: Path) -> BundleSummary:
    if (root / case["case_id"]).exists():
        return _unchanged(_open_case(case, corpus, root))
    parent = _open_for_corpus(case["parent_stream_id"], corpus, root)
    return _summary(write_case_bundle(case, parent, root), STAGED)


def _unchanged(bundle: FrameBundle) -> BundleSummary:
    """Re-hash a bundle that already exists, because staging repairs nothing."""
    if damage := bundle.damage():
        raise frames_corrupted(damage)
    return _summary(bundle, UNCHANGED)
