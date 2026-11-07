"""`ss-track discover links`: write one link review of a staged corpus version.

The review first applies the checks that already refuse known leakage, so a link review exists only
for a version that passes them: one source in one group (the build's rule) and no run of identical
frames shared by two groups (stage's rule, over the version and its chain). It then flags pairs of
streams in different groups that look alike, applies the reviewer's decisions, and refuses a
version that keeps related recordings in different groups. What remains undecided is written as
`unresolved`, never merged. The record is built whole and published by one rename, in the
discovery namespace of run ids, so a reader meets a whole review or none.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.duplicate_frames import SharedFramesCheck, require_unshared_frames
from ss_track.corpus.bundles.frame_set import read_frame_set
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.links.decisions import Decisions, read_decisions
from ss_track.corpus.links.evidence import Evidence, background_evidence, luma_evidence
from ss_track.corpus.links.records import read_links
from ss_track.corpus.links.result import LinksResult
from ss_track.corpus.links.review import Review, require_no_related_links, review_links
from ss_track.corpus.records.kinds import CORPUS_LINKS
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.storage.layout import (
    DISCOVERY_PUBLISH_LOCK,
    LINKS_NAME,
    discovery_root,
    frame_set_path,
    links_path,
)
from ss_track.corpus.storage.scratch import exclusive_lock, scratch_directory
from ss_track.corpus.versions.grouping import require_separate_sources
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.validation.enforce import is_shared_type

WRITTEN = "written"
UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class LinkRequest:
    """What one `discover links` command was asked to review."""

    run_id: str
    corpus_id: str
    features_run_id: str | None = None
    decisions_path: Path | None = None


def _features(
    request: LinkRequest, streams: Sequence[Mapping[str, Any]], data_root: Path
) -> tuple[Evidence | None, dict[str, JsonValue]]:
    """Read the discovery run whose rows the background method compares, bound to this version."""
    if request.features_run_id is None:
        return None, {}
    records = verify_discovery(data_root, request.features_run_id)
    if records.run["corpus_id"] != request.corpus_id:
        raise invalid(
            f"discovery run {request.features_run_id} read corpus version "
            f"{records.run['corpus_id']}, not {request.corpus_id}"
        )
    found = {"run_id": records.run_id, "run_sha256": records.run[SEAL_FIELD]}
    return background_evidence(streams, records), {"features": found}


def _body(
    request: LinkRequest,
    corpus: Mapping[str, Any],
    frame_set: Mapping[str, Any],
    shared: SharedFramesCheck,
    evidence: Sequence[Evidence],
    review: Review,
    decisions: Decisions | None,
) -> dict[str, JsonValue]:
    body: dict[str, JsonValue] = {
        **CORPUS_LINKS.stamp(),
        "run_id": request.run_id,
        "corpus_id": request.corpus_id,
        "corpus_manifest_sha256": corpus[SEAL_FIELD],
        "frame_set_sha256": frame_set[SEAL_FIELD],
        "shared_frames": shared.to_record(),
        "methods": [method for found in evidence for method in found.methods],
        "not_compared": [gap.to_record() for found in evidence for gap in found.gaps],
    }
    if decisions is not None:
        body["review"] = {"reviewer": decisions.reviewer, "decision_count": len(decisions.by_pair)}
        body["decisions_outside_links"] = review.outside_records()
    body["links"] = [link.to_record() for link in review.links]
    body["status"] = review.status
    return body


def _frame_set(corpus_id: str, data_root: Path) -> dict[str, JsonValue]:
    """Return the version's frame set; a version whose staging never finished is not reviewed."""
    if not frame_set_path(data_root, corpus_id).is_file():
        raise CorpusRefusal(
            RefusalCode.FRAME_SET_NOT_STAGED,
            "no frame set: staging this corpus version has not finished",
            {"corpus_id": corpus_id},
        )
    return read_frame_set(data_root, corpus_id)


def build_links(request: LinkRequest, data_root: Path) -> dict[str, JsonValue]:
    """Check, flag, decide and seal one review, writing nothing."""
    decisions = None if request.decisions_path is None else read_decisions(request.decisions_path)
    corpus = load_corpus_manifest(request.corpus_id, data_root)
    manifest: Any = corpus
    streams: list[dict[str, Any]] = list(manifest["streams"])
    require_separate_sources(streams)
    shared = require_unshared_frames(corpus, data_root)
    frame_set = _frame_set(request.corpus_id, data_root)
    background, features = _features(request, streams, data_root)
    evidence = [luma_evidence(request.corpus_id, streams, data_root)]
    if background is not None:
        evidence.append(background)
    flags = [flag for found in evidence for flag in found.flags]
    review = review_links(streams, flags, decisions)
    require_no_related_links(request.corpus_id, review)
    body = _body(request, corpus, frame_set, shared, evidence, review, decisions)
    return seal(body | features)


def _publish(data_root: Path, record: dict[str, JsonValue]) -> tuple[Path, bool]:
    """Publish a review by one rename; the same review again changes nothing."""
    run_id = str(record["run_id"])
    root = discovery_root(data_root)
    path = links_path(data_root, run_id)
    with exclusive_lock(root, DISCOVERY_PUBLISH_LOCK, clear=(root,)):
        if path.parent.exists():
            _require_same(data_root, path, record)
            return path, False
        with scratch_directory(root) as staged:
            write_sealed(staged / LINKS_NAME, record)
            staged.rename(path.parent)
    return path, True


def _require_same(data_root: Path, path: Path, record: Mapping[str, JsonValue]) -> None:
    if not path.exists():
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this run id already holds another run; choose a new run id",
            {"run_id": record["run_id"], "path": str(path.parent)},
        )
    existing = read_links(data_root, str(record["run_id"]))
    if existing[SEAL_FIELD] != record[SEAL_FIELD]:
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this link review already holds a different record; choose a new run id",
            {
                "run_id": record["run_id"],
                "path": str(path),
                "manifest_sha256": existing[SEAL_FIELD],
                "proposed_manifest_sha256": record[SEAL_FIELD],
            },
        )


def write_links(request: LinkRequest, data_root: Path) -> LinksResult:
    """Write the review a request asks for, holding its run id so no other command computes it."""
    if not is_shared_type("identifier", request.run_id):
        raise invalid(f"run id {request.run_id!r} is not an identifier")
    busy = CorpusRefusal(
        RefusalCode.DISCOVERY_IN_PROGRESS,
        "another command is writing this run",
        {"run_id": request.run_id},
    )
    with exclusive_lock(discovery_root(data_root), f".run-{request.run_id}.lock", busy=busy):
        record = build_links(request, data_root)
        path, written = _publish(data_root, record)
    return LinksResult(WRITTEN if written else UNCHANGED, record, path)
