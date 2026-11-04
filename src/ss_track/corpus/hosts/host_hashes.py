"""What one host staged, in a record another host's can be compared with.

Two frame-set hashes say only whether two hosts agree. This record keeps every bundle's frame hashes
beside the facts of the host, so `hash_comparison` can name a disagreement per source and per frame
without moving any frames between hosts. Host facts would break a frame set's single hash, so they
live only here.
"""

import platform
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.frame_set import read_frame_set
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.bundles.frames import frames_root as bundles_root
from ss_track.corpus.bundles.staging import verify_corpus_frames
from ss_track.corpus.records.kinds import STAGED_HASHES_KIND, RecordFormat
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.sources.stored import load_source_record
from ss_track.corpus.versions.builder import load_corpus_manifest
from ss_track.schema.validation.enforce import is_shared_type

RUN_DIRECTORY = "run"
STAGED_HASHES_NAME = "staged-hashes.json"
STAGED_HASHES = RecordFormat(STAGED_HASHES_KIND, major=1)


@dataclass(frozen=True, slots=True)
class StagedHashesResult:
    """Where one host's record went, and the hash it holds."""

    corpus_id: str
    frame_set_sha256: str
    bundle_count: int
    host: Mapping[str, JsonValue]
    record_path: Path

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": "recorded",
            "corpus_id": self.corpus_id,
            "frame_set_sha256": self.frame_set_sha256,
            "bundle_count": self.bundle_count,
            "host": dict(self.host),
            "record_path": str(self.record_path),
        }


def run_directory(data_root: Path, run_id: str) -> Path:
    """Return one run's directory, refusing an identifier that cannot name one."""
    if not is_shared_type("identifier", run_id):
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "run id must be a shared/types identifier",
            {"run_id": run_id},
        )
    return data_root / RUN_DIRECTORY / run_id


def _host() -> dict[str, JsonValue]:
    return {
        "machine": platform.machine(),
        "system": platform.system(),
        "python": platform.python_version(),
    }


def _frames(bundle: FrameBundle) -> list[JsonValue]:
    return [[entry.frame_index, entry.pts, entry.sha256] for entry in bundle.entries]


def _source_facts(source_sha256: str, data_root: Path) -> dict[str, JsonValue]:
    """State what a reader needs to tell which decoder path a difference belongs to."""
    manifest: dict[str, Any] = load_source_record(source_sha256, data_root)
    sequence = manifest["sequence"]
    return {
        "source_sha256": source_sha256,
        "source_manifest_sha256": manifest[SEAL_FIELD],
        "codec": sequence["codec"],
        "source_pixel_format": sequence["source_pixel_format"],
    }


def record_staged_hashes(corpus_id: str, run_id: str, data_root: Path) -> StagedHashesResult:
    """Verify a staged corpus, then record its hashes under one run.

    Verifying first means the record states frames that are on disk now, not what a stage reported.
    """
    target = run_directory(data_root, run_id) / STAGED_HASHES_NAME
    verified = verify_corpus_frames(corpus_id, data_root)
    corpus = load_corpus_manifest(corpus_id, data_root)
    frame_set: dict[str, Any] = read_frame_set(data_root, corpus_id)
    root = bundles_root(data_root, corpus_id)
    bundles: list[JsonValue] = [
        dict(line) | {"frames": _frames(open_corpus_bundle(line["stream_id"], corpus, root))}
        for line in frame_set["bundles"]
    ]
    source_hashes = sorted({line["source_sha256"] for line in frame_set["bundles"]})
    sources: list[JsonValue] = [_source_facts(sha256, data_root) for sha256 in source_hashes]
    host = _host()
    record = seal(
        {
            **STAGED_HASHES.stamp(),
            "corpus_id": corpus_id,
            "corpus_manifest_sha256": frame_set["corpus_manifest_sha256"],
            "decode_policy_sha256": corpus["decode_policy_sha256"],
            "frame_set_sha256": verified.frame_set_sha256,
            "host": host,
            "sources": sources,
            "bundles": bundles,
        }
    )
    write_sealed(target, record)
    return StagedHashesResult(corpus_id, verified.frame_set_sha256, len(bundles), host, target)


def read_staged_hashes(path: Path) -> dict[str, Any]:
    """Read one host's record, refusing a damaged one or another schema."""
    return read_sealed(path, STAGED_HASHES)
