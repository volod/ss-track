"""Likely re-encoded copies across groups.

Not sealed: a corpus hash does not change when the report does, and a match refuses nothing.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue
from ss_track.corpus.records.kinds import CORPUS_MANIFEST, RecordFormat
from ss_track.corpus.records.projections import NotCompared, Unprojected
from ss_track.corpus.versions.fingerprint import (
    GRID,
    METHOD,
    SAMPLE_COUNT,
    SIMILARITY_THRESHOLD,
    Grid,
    sample_indexes,
    similarity,
)
from ss_track.corpus.versions.near_duplicate_samples import sampled_frames
from ss_track.corpus.versions.near_duplicate_scan import WINDOW_UNKNOWN, outside_chain
from ss_track.corpus.versions.predecessors import Predecessor

_SOURCE_UNREADABLE = "source_unreadable"
_SIMILARITY_DIGITS = 4

type ManifestLoader = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class _Window:
    corpus_id: str
    stream_id: str
    group_id: str
    split: str
    source_sha256: str
    start: int
    end: int

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "corpus_id": self.corpus_id,
            "stream_id": self.stream_id,
            "group_id": self.group_id,
            "split": self.split,
        }


@dataclass(frozen=True, slots=True)
class _Pair:
    similarity: float
    streams: tuple[_Window, _Window]

    def to_record(self) -> dict[str, JsonValue]:
        ordered = tuple(sorted(self.streams, key=_stream_order))
        return {
            "similarity": round(self.similarity, _SIMILARITY_DIGITS),
            "streams": [window.to_record() for window in ordered],
        }


@dataclass(frozen=True, slots=True)
class NearDuplicates:
    """What a build found across groups. Empty means nothing to report."""

    pairs: tuple[_Pair, ...]
    not_compared: tuple[NotCompared, ...]
    scan: str | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form. Each list is absent when it is empty."""
        record: dict[str, JsonValue] = {
            "method": METHOD,
            "samples": SAMPLE_COUNT,
            "grid": GRID,
            "threshold": SIMILARITY_THRESHOLD,
        }
        if self.pairs:
            record["pairs"] = [pair.to_record() for pair in self.pairs]
        if self.not_compared:
            record["not_compared"] = [gap.to_record() for gap in self.not_compared]
        if self.scan is not None:
            record["scan"] = self.scan
        return record

    def when_present(self) -> dict[str, JsonValue]:
        """Return the `near_duplicates` field, or nothing when this report is empty."""
        if not self.pairs and not self.not_compared and self.scan is None:
            return {}
        return {"near_duplicates": self.to_record()}


def report_near_duplicates(
    corpus_id: str,
    streams: Sequence[Mapping[str, Any]],
    predecessors: Sequence[Predecessor],
    data_root: Path,
    load_manifest: ManifestLoader,
    record_format: RecordFormat = CORPUS_MANIFEST,
) -> NearDuplicates:
    """Compare windows in different groups and report pairs at the measured threshold.

    `streams` are this version. `predecessors` are the linked versions, nearest first.
    `load_manifest` reads a linked version's frame window. Other built versions on
    `data_root`, read as `record_format`, follow that chain. A window, source, or version that
    cannot be read is named.
    """
    windows, gaps = _windows(corpus_id, streams, predecessors, load_manifest)
    groups = {window.group_id for window in windows}
    outside = outside_chain(corpus_id, predecessors, groups, data_root, record_format)
    for version in outside.versions:
        windows.extend(_window(version.corpus_id, stream) for stream in version.streams)
    gaps.extend(outside.not_compared)
    if len({window.group_id for window in windows}) < 2:
        return NearDuplicates((), tuple(gaps), outside.scan)
    codes, unread = _codes(windows, data_root)
    return NearDuplicates(_pairs(windows, codes), tuple(gaps) + tuple(unread), outside.scan)


def _windows(
    corpus_id: str,
    streams: Sequence[Mapping[str, Any]],
    predecessors: Sequence[Predecessor],
    load_manifest: ManifestLoader,
) -> tuple[list[_Window], list[NotCompared]]:
    windows = [_window(corpus_id, stream) for stream in streams]
    groups = {window.group_id for window in windows}
    gaps: list[NotCompared] = []
    for version in predecessors:
        if isinstance(version, Unprojected):
            gaps.append(version.gap())
            continue
        _add_predecessor(version, groups, load_manifest, windows, gaps)
    return windows, gaps


def _add_predecessor(
    version: Mapping[str, Any],
    groups: set[str],
    load_manifest: ManifestLoader,
    windows: list[_Window],
    gaps: list[NotCompared],
) -> None:
    corpus_id = str(version["corpus_id"])
    try:
        manifest = load_manifest(corpus_id)
    except CorpusRefusal:
        _gap_for_unreadable_window(version, groups, gaps)
        return
    for stream in manifest["streams"]:
        if isinstance(stream, dict) and isinstance(stream.get("selection"), dict):
            windows.append(_window(corpus_id, stream))
        else:
            gaps.append(NotCompared(corpus_id, WINDOW_UNKNOWN, (str(stream["stream_id"]),)))


def _gap_for_unreadable_window(
    version: Mapping[str, Any], groups: set[str], gaps: list[NotCompared]
) -> None:
    """Name a predecessor only when one of its groups is not a group of this version.

    The same group is not a near-duplicate question. A predecessor whose window cannot be
    read, in some other group, is unknown rather than clear.
    """
    streams = version.get("streams", ())
    if not isinstance(streams, list):
        gaps.append(NotCompared(str(version["corpus_id"]), WINDOW_UNKNOWN, ()))
        return
    elsewhere = tuple(
        str(stream["stream_id"])
        for stream in streams
        if isinstance(stream, dict) and stream.get("group_id") not in groups
    )
    if elsewhere:
        gaps.append(NotCompared(str(version["corpus_id"]), WINDOW_UNKNOWN, elsewhere))


def _window(corpus_id: str, stream: Mapping[str, Any]) -> _Window:
    selection = stream["selection"]
    return _Window(
        corpus_id=corpus_id,
        stream_id=str(stream["stream_id"]),
        group_id=str(stream["group_id"]),
        split=str(stream["split"]),
        source_sha256=str(stream["source_sha256"]),
        start=int(selection["start_frame"]),
        end=int(selection["end_frame"]),
    )


def _codes(
    windows: Sequence[_Window], data_root: Path
) -> tuple[dict[_Window, tuple[Grid, ...]], tuple[NotCompared, ...]]:
    by_source: dict[str, list[_Window]] = {}
    for window in windows:
        by_source.setdefault(window.source_sha256, []).append(window)
    coded: dict[_Window, tuple[Grid, ...]] = {}
    unread: list[NotCompared] = []
    for source_sha256, group in by_source.items():
        try:
            spans = tuple((window.start, window.end) for window in group)
            frames = sampled_frames(source_sha256, spans, data_root)
        except (CorpusRefusal, OSError):
            unread.extend(_unreadable(group))
            continue
        for window in group:
            indexes = sample_indexes(window.start, window.end)
            coded[window] = tuple(frames[index] for index in indexes)
    return coded, tuple(unread)


def _unreadable(windows: Sequence[_Window]) -> tuple[NotCompared, ...]:
    by_corpus: dict[str, list[str]] = {}
    for window in windows:
        by_corpus.setdefault(window.corpus_id, []).append(window.stream_id)
    return tuple(
        NotCompared(corpus_id, _SOURCE_UNREADABLE, tuple(stream_ids))
        for corpus_id, stream_ids in sorted(by_corpus.items())
    )


def _pairs(
    windows: Sequence[_Window], codes: Mapping[_Window, tuple[Grid, ...]]
) -> tuple[_Pair, ...]:
    found: list[_Pair] = []
    ordered = tuple(windows)
    for index, left in enumerate(ordered):
        left_code = codes.get(left)
        if left_code is None:
            continue
        for right in ordered[index + 1 :]:
            if left.group_id == right.group_id:
                continue
            right_code = codes.get(right)
            if right_code is None:
                continue
            score = similarity(left_code, right_code)
            if score >= SIMILARITY_THRESHOLD:
                found.append(_Pair(score, (left, right)))
    return tuple(sorted(found, key=_pair_order))


def _pair_order(pair: _Pair) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(_stream_order(window) for window in pair.streams))


def _stream_order(window: _Window) -> tuple[str, str]:
    return window.corpus_id, window.stream_id
