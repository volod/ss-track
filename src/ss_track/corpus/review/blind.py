"""`discover blind` and `discover unblind`.

`blind` writes the common audit sample for a reviewer and seals the private mapping apart from
that packet. `unblind` maps the reviewer's item decisions back to one corpus review per discovery
run. The mapped review carries the declared independence, blinding and minutes. It does not turn
an observation into a label.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from ss_track.core.canonical import SEAL_FIELD, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import exclusive_lock
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.review.blind_key import publish_key, read_blinding, require_same_key, seal_key
from ss_track.corpus.review.blind_packet import (
    packet_files,
    packet_frames_match,
    place_files,
    render_frames,
)
from ss_track.corpus.review.blind_review import (
    AuditReview,
    read_audit_review,
    require_corpus_reviews,
)
from ss_track.corpus.review.blind_sample import AuditSample, common_sample
from ss_track.corpus.review.export import declaration_bytes
from ss_track.corpus.storage.layout import blinding_path, discovery_root, discovery_run_directory
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.validation.enforce import is_shared_type

PRESENTED = "presented"
UNBLINDED = "unblinded"
UNCHANGED = "unchanged"


def _identifier(value: str, label: str) -> None:
    if not is_shared_type("identifier", value):
        raise invalid(f"{label} {value!r} is not an identifier")


def _apart(out: Path, data_root: Path, audit_id: str) -> None:
    """Keep the reviewer packet off the directory that holds the private mapping."""
    target = out.resolve()
    private = discovery_run_directory(data_root, audit_id).resolve()
    overlaps = target == private or target.is_relative_to(private) or private.is_relative_to(target)
    if overlaps:
        raise CorpusRefusal(
            RefusalCode.STORAGE_FAILED,
            "the blinded presentation is written apart from its private mapping",
            {"path": str(out)},
        )


def _load_runs(data_root: Path, run_ids: Sequence[str]) -> list[DiscoveryRecords]:
    if len(run_ids) != len(set(run_ids)):
        raise invalid("a discovery run is named twice")
    return [verify_discovery(data_root, run_id) for run_id in run_ids]


def _counts(audit_id: str, sample: AuditSample, review: AuditReview | None) -> dict[str, JsonValue]:
    counts: dict[str, JsonValue] = {
        "audit_id": audit_id,
        "presented": len(sample.items),
        "withheld": sample.withheld_count(),
        "outside_sample": sample.outside_sample,
        "run_count": len(sample.runs),
        "unselected": sample.unselected,
    }
    if review is None:
        return counts
    counts["independence"] = review.independence
    counts["blinding"] = review.blinding
    counts["reviewer_minutes"] = review.reviewer_minutes
    return counts


class BlindResult:
    """What `discover blind` or `discover unblind` reports. Counts name no source."""

    def __init__(
        self,
        status: str,
        audit_id: str,
        sample: AuditSample,
        declaration_path: Path,
        mapping_path: Path,
        mapping_sha256: str,
        declaration_sha256: str | None = None,
        files: Sequence[Path] = (),
        review: AuditReview | None = None,
    ) -> None:
        self._status = status
        self._audit_id = audit_id
        self._sample = sample
        self._declaration_path = declaration_path
        self._declaration_sha256 = declaration_sha256
        self._mapping_path = mapping_path
        self._mapping_sha256 = mapping_sha256
        self._files = files
        self._review = review

    def to_record(self) -> dict[str, JsonValue]:
        """Return the command result."""
        record: dict[str, JsonValue] = {
            "status": self._status,
            "blind": _counts(self._audit_id, self._sample, self._review),
            "declaration_path": str(self._declaration_path),
            "manifest_path": str(self._mapping_path),
            "manifest_sha256": self._mapping_sha256,
        }
        if self._declaration_sha256 is not None:
            record["declaration_sha256"] = self._declaration_sha256
        if self._files:
            record["files"] = [str(path) for path in self._files]
        return record


def _busy(audit_id: str) -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.DISCOVERY_IN_PROGRESS,
        "another command is writing this audit",
        {"audit_id": audit_id},
    )


def present_audit(audit_id: str, run_ids: Sequence[str], out: Path, data_root: Path) -> BlindResult:
    """Write the blinded packet and seal the private mapping for one audit id."""
    _identifier(audit_id, "audit id")
    for run_id in run_ids:
        _identifier(run_id, "run id")
    _apart(out, data_root, audit_id)
    with exclusive_lock(discovery_root(data_root), f".run-{audit_id}.lock", busy=_busy(audit_id)):
        runs = _load_runs(data_root, run_ids)
        corpus = load_corpus_manifest(str(runs[0].run["corpus_id"]), data_root)
        sample = common_sample(runs, corpus)
        pictures = render_frames(corpus, data_root, sample.items)
        sealed = seal_key(audit_id, sample, pictures)
        require_same_key(data_root, sealed)
        wrote_packet = place_files(packet_files(out, audit_id, sample, pictures))
        path, wrote_key = publish_key(data_root, sealed)
    status = PRESENTED if wrote_packet or wrote_key else UNCHANGED
    return BlindResult(
        status,
        audit_id,
        sample,
        out / "review.yaml",
        path,
        str(sealed[SEAL_FIELD]),
        sha256_bytes((out / "review.yaml").read_bytes()),
    )


def _items(record: Mapping[str, JsonValue]) -> list[dict[str, JsonValue]]:
    return cast(list[dict[str, JsonValue]], record["items"])


def _run_ids(record: Mapping[str, JsonValue]) -> list[str]:
    entries = cast(list[dict[str, JsonValue]], record["runs"])
    return [str(entry["run_id"]) for entry in entries]


def unblind_audit(audit_id: str, review_path: Path, out: Path, data_root: Path) -> BlindResult:
    """Map a blinded review onto one corpus review per run the private mapping names."""
    _identifier(audit_id, "audit id")
    _apart(out, data_root, audit_id)
    review = read_audit_review(review_path)
    if review.audit_id != audit_id:
        raise invalid(f"the review names audit {review.audit_id}, not {audit_id}")
    record = read_blinding(data_root, audit_id)
    items = _items(record)
    packet_frames_match(review_path, items)
    run_ids = _run_ids(record)
    corpus = load_corpus_manifest(str(record["corpus_id"]), data_root)
    sample = common_sample(_load_runs(data_root, run_ids), corpus)
    documents = require_corpus_reviews(review, items, run_ids)
    files = [
        (out / f"{document['run_id']}.yaml", declaration_bytes(document)) for document in documents
    ]
    wrote = place_files(files)
    return BlindResult(
        UNBLINDED if wrote else UNCHANGED,
        audit_id,
        sample,
        out,
        blinding_path(data_root, audit_id),
        str(record[SEAL_FIELD]),
        files=[path for path, _ in files],
        review=review,
    )
