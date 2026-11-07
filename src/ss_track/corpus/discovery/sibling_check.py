"""Recompute every sibling window of a run from its stream's PTS, by the slot rule.

A `sibling_time` window states its slot and names a hint source with the sampling rate. The window
must be exactly the source frames that fall in that slot, read from the source record the stream's
corpus version pinned, and must lie whole inside the bundle. A window that disagrees was mapped
wrongly or altered, and is refused instead of trusted.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from ss_track.corpus.discovery.findings import Finding, inventory_label
from ss_track.corpus.discovery.inventory_rules import SIBLING_TIME
from ss_track.corpus.siblings.slots import parse_rational
from ss_track.corpus.siblings.video_hints import SlotCache, StreamTiming, sibling_window
from ss_track.corpus.sources.stored import pinned_source_record, source_sequence


def stream_timing(inventory: Mapping[str, Any], data_root: Path) -> StreamTiming:
    """Return the slot rule's facts for an inventory's stream, from its pinned source record."""
    record = pinned_source_record(
        inventory["source_sha256"], inventory["source_manifest_sha256"], data_root
    )
    bundle = inventory["bundle_frames"]
    return StreamTiming(
        inventory["stream_id"],
        inventory["source_sha256"],
        bundle["start_frame"],
        bundle["end_frame"],
        source_sequence(record),
    )


def sibling_findings(
    run: Mapping[str, Any], inventories: Mapping[str, Mapping[str, Any]], data_root: Path
) -> Iterator[Finding]:
    """Find each sibling window the slot rule does not reproduce."""
    rates = {source["hint_source_id"]: source["sample_rate"] for source in run["hint_sources"]}
    cache = SlotCache()
    for stream_id, inventory in sorted(inventories.items()):
        siblings = [
            (index, candidate)
            for index, candidate in enumerate(inventory["candidates"])
            if candidate["origin"]["source"] == SIBLING_TIME
        ]
        if not siblings:
            continue
        timing = stream_timing(inventory, data_root)
        reason = timing.unmappable()
        for index, candidate in siblings:
            yield from _check(candidate, timing, reason, rates, cache, stream_id, index)


def _check(
    candidate: Mapping[str, Any],
    timing: StreamTiming,
    reason: str | None,
    rates: Mapping[str, str],
    cache: SlotCache,
    stream_id: str,
    index: int,
) -> Iterator[Finding]:
    origin = candidate["origin"]
    rate = rates.get(origin["hint_source_id"])
    if rate is None:
        return  # the run's own rules name an undeclared hint source
    expected = reason or sibling_window(
        timing, cache.of(timing, parse_rational(rate)), origin["slot"]
    )
    window = candidate["window"]
    if expected == (window["start_frame"], window["end_frame"]):
        return
    stated = expected if isinstance(expected, str) else f"frames {expected[0]} to {expected[1] - 1}"
    message = f"the slot rule maps slot {origin['slot']} to {stated}, not this window"
    yield Finding(inventory_label(stream_id), f"/candidates/{index}/window", "sibling", message)
