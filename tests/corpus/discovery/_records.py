"""A golden discovery run over two streams, built from stated facts, for the discovery tests.

Each stream holds 24 frames cut into three pool windows of eight. One stream also holds a window an
ss-video time named: at 25 frames per second sampled at 5 per second, slot 3 holds frames 13 to 17.
Selection is deterministic and ranks two windows; one window lacks a feature and is excluded, yet
stays in the audit pool; the audit draws two of the six pool windows in one stratum.
"""

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import JsonValue
from ss_track.corpus.discovery.records import DiscoveryRecords, seal_discovery
from ss_track.corpus.storage.layout import corpus_manifest_path, frame_set_path
from tests.corpus.discovery._run_body import CORPUS_ID, GROUP_ID, RUN_ID, WINDOW_FRAMES, run_body

SELECTED = {("one", "pool-001"): 1, ("two", "pool-000"): 2}
EXCLUDED = ("two", "pool-002")
SAMPLED = {("one", "pool-000"), ("two", "pool-002")}
SIBLING_ID = "sibling-ss-video-1-3"
SIBLING_WINDOW = {"start_frame": 13, "end_frame": 18}


@dataclass(frozen=True, slots=True)
class Stream:
    """The facts of one staged stream that its inventory repeats."""

    stream_id: str
    group_id: str
    bundle_sha256: str
    source_sha256: str
    source_manifest_sha256: str
    start_frame: int
    end_frame: int


def _digest(name: str) -> str:
    return sha256_bytes(name.encode("ascii"))


def synthetic_streams() -> list[Stream]:
    """Two streams of 24 frames whose hashes are stated, not staged."""
    return [
        Stream(
            name, GROUP_ID, _digest(f"b-{name}"), _digest(f"s-{name}"), _digest(f"m-{name}"), 0, 24
        )
        for name in ("one", "two")
    ]


def staged_streams(data_root: Path, corpus_id: str = CORPUS_ID) -> tuple[str, list[Stream]]:
    """Read the frame-set seal and the streams a staged corpus version holds."""
    frame_set = json.loads(frame_set_path(data_root, corpus_id).read_text(encoding="ascii"))
    corpus = json.loads(corpus_manifest_path(data_root, corpus_id).read_text(encoding="ascii"))
    lines = {line["stream_id"]: line for line in frame_set["bundles"]}
    streams = [
        Stream(
            stream["stream_id"],
            stream["group_id"],
            lines[stream["stream_id"]]["bundle_sha256"],
            stream["source_sha256"],
            stream["source_manifest_sha256"],
            stream["selection"]["start_frame"],
            stream["selection"]["end_frame"],
        )
        for stream in corpus["streams"]
    ]
    return str(frame_set["manifest_sha256"]), streams


def _scores(value: float, novelty: bool = True) -> list[JsonValue]:
    motion: dict[str, JsonValue] = {"status": "computed", "score_id": "motion", "value": value}
    if novelty:
        return [motion, {"status": "computed", "score_id": "novelty", "value": value / 2}]
    unavailable = {"status": "unavailable", "score_id": "novelty", "reason": "extractor_failed"}
    return [motion, unavailable]


def _selection(key: tuple[str, str]) -> dict[str, JsonValue]:
    if key == EXCLUDED:
        return {"status": "excluded", "reason": "features_unavailable"}
    if key in SELECTED:
        return {"status": "selected", "rank": SELECTED[key], "probability": 1.0}
    return {"status": "not_selected", "probability": 0.0}


def _pool_candidate(stream: Stream, index: int, probability: float) -> dict[str, JsonValue]:
    candidate_id = f"pool-{index:03d}"
    key = (stream.stream_id, candidate_id)
    start = stream.start_frame + index * WINDOW_FRAMES
    return {
        "candidate_id": candidate_id,
        "window": {"start_frame": start, "end_frame": min(start + WINDOW_FRAMES, stream.end_frame)},
        "origin": {"source": "pool"},
        "scores": _scores(float(10 - index), novelty=key != EXCLUDED),
        "selection": _selection(key),
        "audit": {
            "status": "sampled" if key in SAMPLED else "not_sampled",
            "stratum_id": GROUP_ID,
            "inclusion_probability": probability,
        },
    }


def _sibling_candidate() -> dict[str, JsonValue]:
    return {
        "candidate_id": SIBLING_ID,
        "window": dict(SIBLING_WINDOW),
        "origin": {"source": "sibling_time", "hint_source_id": "ss-video-1", "slot": 3},
        "scores": _scores(4.0),
        "selection": {"status": "not_selected", "probability": 0.0},
        "audit": {"status": "ineligible", "reason": "no_inclusion_probability"},
    }


def inventory_bodies(streams: list[Stream]) -> list[dict[str, JsonValue]]:
    """One inventory body per stream: its pool windows, and the sibling window on the first."""
    per_stream = -(-(streams[0].end_frame - streams[0].start_frame) // WINDOW_FRAMES)
    probability = len(SAMPLED) / (per_stream * len(streams))
    bodies = []
    for position, stream in enumerate(streams):
        candidates: list[JsonValue] = [
            _pool_candidate(stream, index, probability) for index in range(per_stream)
        ]
        if position == 0:
            candidates.append(_sibling_candidate())
        bodies.append(
            {
                "run_id": RUN_ID,
                "corpus_id": CORPUS_ID,
                "stream_id": stream.stream_id,
                "group_id": stream.group_id,
                "bundle_sha256": stream.bundle_sha256,
                "source_sha256": stream.source_sha256,
                "source_manifest_sha256": stream.source_manifest_sha256,
                "bundle_frames": {"start_frame": stream.start_frame, "end_frame": stream.end_frame},
                "candidates": candidates,
            }
        )
    return bodies


@dataclass(frozen=True, slots=True)
class Bodies:
    """A run body and its inventory bodies, which a test may damage before sealing."""

    run: dict[str, Any]
    inventories: list[dict[str, Any]]

    def inventory(self, stream_id: str) -> dict[str, Any]:
        return next(item for item in self.inventories if item["stream_id"] == stream_id)

    def candidate(self, stream_id: str, candidate_id: str) -> dict[str, Any]:
        candidates = self.inventory(stream_id)["candidates"]
        return next(item for item in candidates if item["candidate_id"] == candidate_id)

    def seal(self) -> DiscoveryRecords:
        return seal_discovery(self.run, self.inventories)


def bodies(frame_set_sha256: str, streams: list[Stream]) -> Bodies:
    """Return fresh golden bodies over the given streams."""
    inventories = inventory_bodies(streams)
    pool = sum(
        1 for item in inventories for c in item["candidates"] if c["origin"] == {"source": "pool"}
    )
    run = run_body(frame_set_sha256, pool, len(SELECTED), len(SAMPLED))
    return Bodies(copy.deepcopy(run), copy.deepcopy(inventories))


def synthetic_bodies() -> Bodies:
    """Golden bodies over stated streams, needing no data root."""
    return bodies(_digest("frame-set"), synthetic_streams())


def written_form(record: Mapping[str, JsonValue]) -> str:
    """The bytes `write_sealed` writes, so an example can be compared with a writer's output."""
    return json.dumps(record, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
