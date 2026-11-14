"""Feature rows: one sealed record per extractor and stream, beside the float32 file of its rows.

The record keys each row by frame index and frame hash, and seals the vector file by hash and size,
so a row cannot drift from the frame it describes or the bytes it was. `verify` binds the keys to
the bundle's sealed index at the record's stride, so the rows name exactly the frames embedded.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ss_track.core.canonical import SEAL_FIELD, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.discovery.findings import RUN_RECORD, Finding
from ss_track.corpus.discovery.run_rules import ordered
from ss_track.corpus.records.kinds import FEATURE_ROWS
from ss_track.corpus.records.sealing import seal, sha256_file
from ss_track.corpus.siblings.embedding import StreamRows
from ss_track.corpus.storage.layout import feature_rows_name, feature_vectors_name

FLOAT32_BYTES = 4


@dataclass(frozen=True, slots=True)
class FeatureFile:
    """A sealed feature-rows record and the vector bytes it seals."""

    record: dict[str, JsonValue]
    vectors: bytes

    @property
    def extractor_id(self) -> str:
        return str(self.record["extractor_id"])

    @property
    def stream_id(self) -> str:
        return str(self.record["stream_id"])

    @property
    def name(self) -> str:
        """Return the record's path inside its run directory."""
        return feature_rows_name(self.extractor_id, self.stream_id)

    def line(self) -> dict[str, JsonValue]:
        """Return the run's line that seals this record."""
        rows = self.record["rows"]
        return {
            "extractor_id": self.extractor_id,
            "stream_id": self.stream_id,
            "rows_sha256": self.record[SEAL_FIELD],
            "row_count": len(rows) if isinstance(rows, list) else 0,
        }


def seal_feature_rows(
    run_id: str,
    corpus_id: str,
    extractor_id: str,
    rows: StreamRows,
    frame_stride: int,
    dimensions: int,
) -> FeatureFile:
    """Seal one stream's rows of one extractor."""
    body: dict[str, JsonValue] = {
        **FEATURE_ROWS.stamp(),
        "run_id": run_id,
        "corpus_id": corpus_id,
        "stream_id": rows.stream_id,
        "extractor_id": extractor_id,
        "bundle_sha256": rows.bundle_sha256,
        "frame_stride": frame_stride,
        "dimensions": dimensions,
        "vectors": {
            "file": feature_vectors_name(rows.stream_id),
            "sha256": sha256_bytes(rows.vectors),
            "size_bytes": len(rows.vectors),
            "dtype": "float32",
            "byte_order": "little",
        },
        "rows": [{"frame_index": index, "frame_sha256": sha} for index, sha in rows.keys],
    }
    return FeatureFile(seal(body), rows.vectors)


def feature_findings(record: Mapping[str, Any], label: str) -> list[Finding]:
    """Check a feature-rows record's order and the vector size it states."""
    found = [
        *ordered([row["frame_index"] for row in record["rows"]], label, "/rows", "frame_index")
    ]
    expected = FLOAT32_BYTES * record["dimensions"] * len(record["rows"])
    if record["vectors"]["size_bytes"] != expected:
        message = f"size_bytes must be {expected}: 4 bytes per value, dimensions per row"
        found.append(Finding(label, "/vectors/size_bytes", "vectors", message))
    return found


def lines_findings(run: Mapping[str, Any], inventories: Mapping[str, Any]) -> Iterator[Finding]:
    """Check the run's feature lines: ordered, and naming its extractors and its streams."""
    lines = run.get("feature_rows", [])
    keys = [(line["extractor_id"], line["stream_id"]) for line in lines]
    yield from ordered(keys, RUN_RECORD, "/feature_rows", "extractor_id and stream_id")
    extractors = {extractor["extractor_id"] for extractor in run["extractors"]}
    for index, (extractor_id, stream_id) in enumerate(keys):
        if extractor_id not in extractors or stream_id not in inventories:
            message = "a feature line must name an extractor of the run and a stream it inventories"
            yield Finding(RUN_RECORD, f"/feature_rows/{index}", "features", message)


def read_vectors(directory: Path, record: Mapping[str, Any]) -> bytes:
    """Read a record's vector file, refusing bytes that are not the ones it sealed."""
    vectors = record["vectors"]
    path: Path = directory / str(vectors["file"])
    if not path.is_file() or sha256_file(path) != vectors["sha256"]:
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "a feature vector file is missing or not the one its record sealed",
            {"record": str(vectors["file"])},
        )
    payload: bytes = path.read_bytes()
    if not np.isfinite(np.frombuffer(payload, dtype="<f4")).all():
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID,
            "a feature vector file holds a value that is not finite",
            {"record": str(vectors["file"])},
        )
    return payload


def binding_findings(record: Mapping[str, Any], bundle: FrameBundle, label: str) -> list[Finding]:
    """Check that the rows name exactly the bundle's frames at the record's stride, by hash."""
    if record["bundle_sha256"] != bundle.bundle_sha256:
        return [Finding(label, "/bundle_sha256", "binding", "the rows name another bundle")]
    start, stride = bundle.selection.start, record["frame_stride"]
    expected = [
        {"frame_index": entry.frame_index, "frame_sha256": entry.sha256}
        for entry in bundle.entries
        if (entry.frame_index - start) % stride == 0
    ]
    if record["rows"] != expected:
        message = "the rows must name the bundle's frames at frame_stride, each by its sealed hash"
        return [Finding(label, "/rows", "binding", message)]
    return []


def feature_labels(lines: Sequence[Mapping[str, Any]]) -> list[str]:
    """Name each feature record as a finding states it."""
    return [feature_rows_name(line["extractor_id"], line["stream_id"]) for line in lines]
