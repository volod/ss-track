"""The private mapping from a blinded audit item back to discovery candidates.

The mapping is sealed under the audit id. Reading it recomputes the sample and the picture
hashes from the discovery runs and the staged frames, so a record that still seals but names
other windows is refused. The presentation given to a reviewer does not include this file.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import seal, write_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import exclusive_lock, scratch_directory
from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.records.kinds import AUDIT_BLINDING
from ss_track.corpus.review.blind_packet import frame_sha256, render_frames
from ss_track.corpus.review.blind_sample import AuditSample, common_sample
from ss_track.corpus.storage.layout import (
    BLINDING_NAME,
    DISCOVERY_PUBLISH_LOCK,
    blinding_path,
    discovery_root,
)
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.validation.enforce import is_shared_type, require_record


def key_body(
    audit_id: str, sample: AuditSample, pictures: Mapping[str, Sequence[bytes]]
) -> dict[str, JsonValue]:
    """Return the unsealed mapping, including each item's picture hash."""
    items: list[JsonValue] = []
    for item in sample.items:
        record = item.to_record()
        record["frame_sha256"] = frame_sha256(pictures[item.item_id])
        items.append(record)
    return {
        **AUDIT_BLINDING.stamp(),
        "audit_id": audit_id,
        "corpus_id": sample.corpus_id,
        "frame_set_sha256": sample.frame_set_sha256,
        "runs": [{"run_id": run_id, "run_sha256": digest} for run_id, digest in sample.runs],
        "items": items,
        "withheld": [dict(item) for item in sample.withheld],
        "outside_sample": sample.outside_sample,
    }


def _mismatch(audit_id: str) -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.RECORD_INVALID,
        "blinding record does not match the discovery runs",
        {"audit_id": audit_id},
    )


def load_runs(data_root: Path, record: Mapping[str, Any]) -> list[DiscoveryRecords]:
    """Load the runs a mapping names, in the record's order."""
    entries: Sequence[Mapping[str, Any]] = record["runs"]
    return [verify_discovery(data_root, str(entry["run_id"])) for entry in entries]


def require_current(data_root: Path, record: Mapping[str, Any]) -> AuditSample:
    """Refuse a mapping whose items, pictures or runs are not what those runs produce now."""
    audit_id = str(record["audit_id"])
    runs = load_runs(data_root, record)
    corpus = load_corpus_manifest(str(record["corpus_id"]), data_root)
    sample = common_sample(runs, corpus)
    pictures = render_frames(corpus, data_root, sample.items)
    if key_body(audit_id, sample, pictures) | {SEAL_FIELD: record[SEAL_FIELD]} != dict(record):
        raise _mismatch(audit_id)
    return sample


def read_blinding(data_root: Path, audit_id: str) -> dict[str, JsonValue]:
    """Read one private mapping and require it to match the runs and frames it names."""
    path = blinding_path(data_root, audit_id)
    if not is_shared_type("identifier", audit_id) or not path.is_file():
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "no such blinding record",
            {"record": BLINDING_NAME, "audit_id": audit_id},
        )
    record = read_sealed(path, AUDIT_BLINDING)
    require_record(record)
    require_current(data_root, record)
    return record


def require_same_key(data_root: Path, record: Mapping[str, Any]) -> None:
    """Refuse an audit id that already holds a different mapping or another kind of run."""
    path = blinding_path(data_root, str(record["audit_id"]))
    if not path.parent.exists():
        return
    if not path.is_file():
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this audit id already holds another run; choose a new audit id",
            {"audit_id": record["audit_id"], "path": str(path.parent)},
        )
    existing = read_sealed(path, AUDIT_BLINDING)
    if existing[SEAL_FIELD] != record[SEAL_FIELD]:
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this blinded audit already holds a different mapping; choose a new audit id",
            {
                "audit_id": record["audit_id"],
                "path": str(path),
                "manifest_sha256": existing[SEAL_FIELD],
                "proposed_manifest_sha256": record[SEAL_FIELD],
            },
        )


def publish_key(data_root: Path, record: dict[str, JsonValue]) -> tuple[Path, bool]:
    """Publish the mapping by one rename. The same mapping again changes nothing."""
    audit_id = str(record["audit_id"])
    root = discovery_root(data_root)
    path = blinding_path(data_root, audit_id)
    with exclusive_lock(root, DISCOVERY_PUBLISH_LOCK, clear=(root,)):
        require_same_key(data_root, record)
        if path.is_file():
            return path, False
        with scratch_directory(root) as staged:
            write_sealed(staged / BLINDING_NAME, record)
            staged.rename(path.parent)
    return path, True


def seal_key(
    audit_id: str, sample: AuditSample, pictures: Mapping[str, Sequence[bytes]]
) -> dict[str, JsonValue]:
    """Seal one mapping once its contract holds."""
    return seal(key_body(audit_id, sample, pictures))
