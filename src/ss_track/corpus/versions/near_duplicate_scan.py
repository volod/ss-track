"""Built versions on one data root that a declaration does not link.

The near-duplicate report compares these after the declared chain, with the same fingerprint.
A missing or unreadable version is named. The scan stays on this data root and assigns no group.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.evidence.sealed import read_comparable
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.projections import NotCompared
from ss_track.corpus.versions.predecessors import Predecessor, predecessor_name
from ss_track.corpus.versions.scan import scan_versions

WINDOW_UNKNOWN = "window_unknown"
_STREAM_FIELDS = ("stream_id", "group_id", "split", "source_sha256")


@dataclass(frozen=True, slots=True)
class OutsideVersion:
    """One readable version that can meet a stream in another group."""

    corpus_id: str
    streams: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class OutsideChain:
    """What the scan found outside the declared chain. Empty means nothing to add."""

    versions: tuple[OutsideVersion, ...]
    not_compared: tuple[NotCompared, ...]
    scan: str | None = None


def fingerprint_manifest(path: Path, record_format: RecordFormat) -> dict[str, JsonValue]:
    """Return a corpus version's comparison projection, which carries its frame window.

    The near-duplicate report is not sealed evidence. A retired major is compared through that
    projection. A manifest that cannot be read, or whose major keeps no projection, is refused
    so the report can name it.
    """
    projected = read_comparable(path, record_format).projected
    streams = projected.get("streams") if projected is not None else None
    if projected is None or not isinstance(streams, list):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "corpus manifest cannot be read")
    return projected


def outside_chain(
    corpus_id: str,
    predecessors: Sequence[Predecessor],
    chain_groups: set[str],
    data_root: Path,
    record_format: RecordFormat,
) -> OutsideChain:
    """Return versions whose group differs, and name a version that cannot be read.

    `chain_groups` are the groups already collected from the version being built and from
    the chain. A version that stays inside the only group in the union is not a near-duplicate
    question, so it is not fingerprinted. `scan` is set when the corpus directory itself
    cannot be listed; the declared chain is unaffected.
    """
    excluded = {corpus_id, *(predecessor_name(item) for item in predecessors)}
    found = scan_versions(data_root, record_format, excluded=excluded, name_missing=True)
    gaps = [NotCompared(gap.corpus_id, gap.reason, ()) for gap in found.not_compared]
    readable = [
        (other_id, projected, groups)
        for other_id, projected in found.compared
        if (groups := _groups(projected))
    ]
    versions, named = _select(readable, gaps, chain_groups)
    return OutsideChain(versions, named, found.scan)


def _groups(projected: Mapping[str, JsonValue]) -> set[str]:
    streams = projected.get("streams")
    if not isinstance(streams, list):
        return set()
    found: set[str] = set()
    for stream in streams:
        group_id = stream.get("group_id") if isinstance(stream, dict) else None
        if isinstance(group_id, str):
            found.add(group_id)
    return found


def _select(
    readable: Sequence[tuple[str, Mapping[str, JsonValue], set[str]]],
    gaps: list[NotCompared],
    chain_groups: set[str],
) -> tuple[tuple[OutsideVersion, ...], tuple[NotCompared, ...]]:
    union = set(chain_groups)
    for _corpus_id, _projected, groups in readable:
        union.update(groups)
    versions: list[OutsideVersion] = []
    for corpus_id, projected, groups in readable:
        if _crosses(groups, union):
            _take(corpus_id, projected, versions, gaps)
    versions.sort(key=lambda item: item.corpus_id)
    gaps.sort(key=lambda gap: (gap.corpus_id, gap.reason, gap.stream_ids))
    return tuple(versions), tuple(gaps)


def _crosses(groups: set[str], union: set[str]) -> bool:
    """A version takes part when one of its groups is not the only group present."""
    if len(groups) >= 2:
        return True
    if len(groups) != 1:
        return False
    only = next(iter(groups))
    return any(group != only for group in union)


def _take(
    corpus_id: str,
    projected: Mapping[str, JsonValue],
    versions: list[OutsideVersion],
    gaps: list[NotCompared],
) -> None:
    placed, unknown = _placed_streams(projected)
    if placed:
        versions.append(OutsideVersion(corpus_id, placed))
    if unknown:
        gaps.append(NotCompared(corpus_id, WINDOW_UNKNOWN, unknown))
    elif not placed:
        gaps.append(NotCompared(corpus_id, WINDOW_UNKNOWN, ()))


def _placed_streams(
    projected: Mapping[str, JsonValue],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[str, ...]]:
    streams = projected.get("streams")
    if not isinstance(streams, list):
        return (), ()
    placed: list[Mapping[str, Any]] = []
    unknown: list[str] = []
    for stream in streams:
        usable = _usable(stream)
        if usable is not None:
            placed.append(usable)
            continue
        stream_id = stream.get("stream_id") if isinstance(stream, dict) else None
        if isinstance(stream_id, str):
            unknown.append(stream_id)
    return tuple(placed), tuple(unknown)


def _usable(stream: object) -> Mapping[str, Any] | None:
    if not isinstance(stream, dict):
        return None
    if not all(isinstance(stream.get(key), str) for key in _STREAM_FIELDS):
        return None
    selection = stream.get("selection")
    if not isinstance(selection, dict) or not _frame_bounds(selection):
        return None
    return stream


def _frame_bounds(selection: Mapping[str, Any]) -> bool:
    start = selection.get("start_frame")
    end = selection.get("end_frame")
    return type(start) is int and type(end) is int
