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

from ss_track.corpus.builder import load_corpus_manifest
from ss_track.corpus.fields import IDENTIFIER_PATTERN
from ss_track.corpus.frame_set import read_frame_set
from ss_track.corpus.frames import FrameBundle, open_corpus_bundle
from ss_track.corpus.frames import frames_root as bundles_root
from ss_track.corpus.importer import MANIFEST_NAME, SOURCE_MANIFEST_KIND, source_directory
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.sealed import SEAL_FIELD, read_sealed, require_schema, seal, write_sealed
from ss_track.corpus.staging import verify_corpus_frames

RUN_DIRECTORY = "run"
STAGED_HASHES_KIND = "ss-track.staged-hashes"
STAGED_HASHES_SCHEMA_VERSION = 1
STAGED_HASHES_NAME = "staged-hashes.json"


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
    if not IDENTIFIER_PATTERN.fullmatch(run_id):
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            f"run id must match {IDENTIFIER_PATTERN.pattern}",
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
    path = source_directory(data_root, source_sha256) / MANIFEST_NAME
    manifest: dict[str, Any] = read_sealed(path, SOURCE_MANIFEST_KIND)
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
            "kind": STAGED_HASHES_KIND,
            "schema_version": STAGED_HASHES_SCHEMA_VERSION,
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
    record = read_sealed(path, STAGED_HASHES_KIND)
    require_schema(record, STAGED_HASHES_SCHEMA_VERSION, path)
    return record
