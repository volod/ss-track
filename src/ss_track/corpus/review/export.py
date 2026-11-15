"""`ss-track discover export`: the corpus declaration of a frozen version, from reviewed decisions.

The export reads the review, verifies the discovery run against the pool version it read, and
writes the declaration that `corpus build` then turns into the frozen version through the existing
build, stage and verify flows. The same review of the same run writes the same bytes, so replaying
it yields the same membership and, through build and stage, the same hashes. The terms each
included source holds now are checked here, as the discovery records promise: retention that has
ended is `RETENTION_EXPIRED`, and a record amended since the run read it, such as withdrawn rights,
is `SOURCE_RECORD_CHANGED`, because the reviewer decided under the terms the run read.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.corpus.bundles.version_bundles import require_sources_hold
from ss_track.corpus.declarations.declaration import CORPUS_CONTRACT, CORPUS_SCHEMA_VERSION
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.review.decisions import Review, read_review
from ss_track.corpus.review.membership import Membership, corpus_document, review_membership
from ss_track.corpus.review.queue import ReviewQueue, review_queue
from ss_track.corpus.review.result import ExportResult, review_counts
from ss_track.corpus.sources.terms import evaluation_date
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.validation.enforce import (
    installed_contracts,
    is_shared_type,
    require_conforming,
)

EXPORTED = "exported"
UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class Reviewed:
    """A review applied to the verified run it names and the pool version that run read."""

    review: Review
    pool: Mapping[str, Any]
    run: Mapping[str, Any]
    queue: ReviewQueue
    membership: Membership


def apply_review(review_path: Path, data_root: Path) -> Reviewed:
    """Read a review and make its membership from the verified run it names."""
    review = read_review(review_path)
    records = verify_discovery(data_root, review.run_id)
    pool = load_corpus_manifest(str(records.run["corpus_id"]), data_root)
    queue = review_queue(records, pool)
    return Reviewed(review, pool, records.run, queue, review_membership(queue, review, pool))


def require_current_terms(reviewed: Reviewed, data_root: Path, today: date) -> None:
    """Refuse an included source whose retention ended or whose record changed since the run."""
    streams = {
        str(item.pool_stream["stream_id"]): item.pool_stream for item in reviewed.membership.members
    }
    require_sources_hold({"streams": list(streams.values())}, data_root, today)


def _require_declaration(document: Mapping[str, JsonValue]) -> None:
    """Hold the export to the corpus contract, so build never meets a declaration it refuses."""
    installed = installed_contracts()
    contract = installed.contracts.named(CORPUS_CONTRACT)
    frozen = contract.newest(CORPUS_SCHEMA_VERSION)
    assert frozen is not None, "the corpus contract has a frozen version of its major"
    require_conforming(
        document,
        installed.contracts,
        contract,
        frozen,
        code=RefusalCode.MANIFEST_INVALID,
        label="exported declaration",
        registry=installed.registry,
    )


def declaration_bytes(document: Mapping[str, JsonValue]) -> bytes:
    """Return the one YAML form of an exported declaration."""
    text = yaml.safe_dump(dict(document), sort_keys=False, default_flow_style=False)
    return text.encode("ascii")


def write_once(out: Path, payload: bytes) -> str:
    """Write a declaration once; the same bytes again change nothing, others are refused."""
    if out.exists():
        if out.is_file() and out.read_bytes() == payload:
            return UNCHANGED
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "the output path already holds something else; choose another path",
            {"path": str(out)},
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(out, payload)
    return EXPORTED


def export_review(
    review_path: Path,
    corpus_id: str,
    out: Path,
    data_root: Path,
    *,
    supersedes: str | None = None,
    today: date | None = None,
) -> ExportResult:
    """Write the declaration of the frozen version a review makes of its run."""
    checked_on = evaluation_date(today)
    for name in (corpus_id, supersedes):
        if name is not None and not is_shared_type("identifier", name):
            raise invalid(f"corpus id {name!r} is not an identifier")
    reviewed = apply_review(review_path, data_root)
    require_current_terms(reviewed, data_root, checked_on)
    document = corpus_document(corpus_id, supersedes, reviewed.pool, reviewed.membership.members)
    _require_declaration(document)
    payload = declaration_bytes(document)
    status = write_once(out, payload)
    return ExportResult(
        status,
        reviewed.queue.run_id,
        corpus_id,
        out,
        sha256_bytes(payload),
        review_counts(reviewed.queue, reviewed.membership),
    )
