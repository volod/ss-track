"""Flag pairs of streams in different groups that look alike, for a reviewer to decide.

Two methods flag. `luma-grid-16` is the build's re-encoded-copy fingerprint over this version's
windows. `background-cosine` compares what a discovery run's frozen backbone says each stream
usually shows: the unit mean of the stream's rows, one per tile position of an extractor, the
pair's similarity being the mean cosine over those positions. A flag is a question for a reviewer.
Its threshold was measured on fixtures for each backbone and crop, so it is not ground truth, and a
pair below it is not shown to be unrelated.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ss_track.core.refusal import JsonValue
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.links.review import Flag
from ss_track.corpus.selection.embeddings import StreamEmbedding, stream_embeddings
from ss_track.corpus.versions.fingerprint import GRID, METHOD, SAMPLE_COUNT, SIMILARITY_THRESHOLD
from ss_track.corpus.versions.near_duplicates import version_near_duplicates

BACKGROUND_METHOD = "background-cosine"
BACKGROUND_REVISION = 1
# Least similarity that flags a pair, by architecture and crop, measured on 2026-11-07
# (current/corpus/leakage-review.md#measured-thresholds): each sits at or below the least
# similarity of any two windows of the one real recording, with tiles in a 4 by 2 grid. Backbones
# scale cosine differently, so one value cannot serve both; an unmeasured pair is not compared.
BACKGROUND_THRESHOLDS: dict[tuple[str, str], float] = {
    ("ViT-B-16", "center"): 0.89,
    ("ViT-B-16", "tiled"): 0.85,
    ("dinov3_vitb14", "center"): 0.60,
    ("dinov3_vitb14", "tiled"): 0.75,
}
_SIMILARITY_DIGITS = 4
NO_FEATURE_ROWS = "no_feature_rows"
NO_THRESHOLD = "no_threshold"


@dataclass(frozen=True, slots=True)
class Gap:
    """Streams a method could not compare, and why: unknown, never clear."""

    method: str
    extractor_id: str | None
    reason: str
    stream_ids: tuple[str, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the record's `not_compared` entry."""
        record: dict[str, JsonValue] = {"method": self.method}
        if self.extractor_id is not None:
            record["extractor_id"] = self.extractor_id
        record["reason"] = self.reason
        record["stream_ids"] = list(self.stream_ids)
        return record


@dataclass(frozen=True, slots=True)
class Evidence:
    """What every method flagged, the methods as a record states them, and what went unread."""

    methods: tuple[dict[str, JsonValue], ...]
    flags: tuple[Flag, ...]
    gaps: tuple[Gap, ...]


def luma_evidence(
    corpus_id: str, streams: Sequence[Mapping[str, Any]], data_root: Path
) -> Evidence:
    """Flag re-encoded copies across this version's groups by the build's fingerprint."""
    report = version_near_duplicates(corpus_id, streams, data_root)
    method: dict[str, JsonValue] = {
        "method": METHOD,
        "samples": SAMPLE_COUNT,
        "grid": GRID,
        "threshold": SIMILARITY_THRESHOLD,
    }
    flags = tuple(Flag(METHOD, None, pair.rounded, pair.stream_ids) for pair in report.pairs)
    gaps = tuple(Gap(METHOD, None, gap.reason, gap.stream_ids) for gap in report.not_compared)
    return Evidence((method,), flags, gaps)


@dataclass(frozen=True, slots=True)
class _Base:
    """One plan extractor of a run: its run extractors, in order, and what decides its threshold."""

    extractor_id: str
    views: tuple[str, ...]
    architecture: str
    crop: str

    @property
    def threshold(self) -> float | None:
        return BACKGROUND_THRESHOLDS.get((self.architecture, self.crop))


def _base_extractors(run: Mapping[str, Any]) -> list[_Base]:
    """Group a run's extractors by the plan extractor they came from, tile positions in order."""
    bases: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for extractor in run.get("extractors", []):
        run_id = str(extractor["extractor_id"])
        tiled = "tile" in extractor["preprocessing"]
        bases[run_id.rsplit(".", 1)[0] if tiled else run_id].append(extractor)
    return [
        _Base(
            base,
            tuple(sorted(str(view["extractor_id"]) for view in views)),
            str(views[0]["architecture"]),
            str(views[0]["preprocessing"]["crop"]),
        )
        for base, views in sorted(bases.items())
    ]


def _descriptor(
    views: Sequence[str], stream_id: str, rows: Mapping[tuple[str, str], StreamEmbedding]
) -> np.ndarray | None:
    """Return the stream's backgrounds, one per tile position, scaled so a dot product averages."""
    found = [rows.get((view, stream_id)) for view in views]
    if any(embedding is None or not len(embedding.rows) for embedding in found):
        return None
    scale = 1.0 / np.sqrt(len(views))
    return np.concatenate([embedding.background() * scale for embedding in found if embedding])


def _flags(
    base: _Base,
    threshold: float,
    ordered: Sequence[Mapping[str, Any]],
    held: Mapping[str, np.ndarray | None],
) -> list[Flag]:
    """Compare every pair of described streams in different groups at once, by one product."""
    described = [(stream, held[str(stream["stream_id"])]) for stream in ordered]
    present = [stream for stream, vector in described if vector is not None]
    if len(present) < 2:
        return []
    matrix = np.stack([vector for _, vector in described if vector is not None])
    similarity = np.round(matrix @ matrix.T, _SIMILARITY_DIGITS)
    groups = np.array([str(stream["group_id"]) for stream in present])
    candidates = np.triu((similarity >= threshold) & (groups[:, None] != groups), k=1)
    return [
        Flag(
            BACKGROUND_METHOD,
            base.extractor_id,
            float(similarity[left, right]),
            (str(present[left]["stream_id"]), str(present[right]["stream_id"])),
        )
        for left, right in np.argwhere(candidates)
    ]


def background_evidence(
    streams: Sequence[Mapping[str, Any]], records: DiscoveryRecords
) -> Evidence:
    """Flag pairs of streams in different groups whose backgrounds reach their threshold."""
    rows = stream_embeddings(records.features)
    methods: list[dict[str, JsonValue]] = []
    flags: list[Flag] = []
    gaps: list[Gap] = []
    ordered = sorted(streams, key=lambda stream: str(stream["stream_id"]))
    stream_ids = tuple(str(stream["stream_id"]) for stream in ordered)
    for base in _base_extractors(records.run):
        threshold = base.threshold
        if threshold is None:
            gaps.append(Gap(BACKGROUND_METHOD, base.extractor_id, NO_THRESHOLD, stream_ids))
            continue
        methods.append(
            {
                "method": BACKGROUND_METHOD,
                "revision": BACKGROUND_REVISION,
                "extractor_id": base.extractor_id,
                "run_extractor_ids": list(base.views),
                "threshold": threshold,
            }
        )
        held = {stream_id: _descriptor(base.views, stream_id, rows) for stream_id in stream_ids}
        missing = tuple(stream_id for stream_id, vector in held.items() if vector is None)
        if missing:
            gaps.append(Gap(BACKGROUND_METHOD, base.extractor_id, NO_FEATURE_ROWS, missing))
        flags += _flags(base, threshold, ordered, held)
    return Evidence(tuple(methods), tuple(flags), tuple(gaps))
