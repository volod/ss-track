"""Bind each discovery stream to the collections on its sealed source record.

A stream with no recorded origin, or whose pinned source record cannot be read,
stays unbound. Nothing in the license, the path or a missing field is used as a
collection.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.evaluation.domains import CollectionId
from ss_track.corpus.sources.stored import pinned_source_record

UNAVAILABLE = "pinned source record is unavailable"
NO_ORIGIN = "source record has no origin"
INCOMPLETE_ORIGIN = "source record origin is incomplete"
UNNAMED = "inventory does not name a sealed source"
DISAGREE = "paired runs disagree on sealed source membership"
UNREAD = "source membership was not read"
_PROVIDERS = frozenset({"huggingface", "zenodo"})


@dataclass(frozen=True, slots=True)
class BoundStream:
    """Collections recorded for one stream, or a reason membership could not be read."""

    collections: tuple[CollectionId, ...]
    reason: str | None


def bind_membership(records: DiscoveryRecords, data_root: Path) -> dict[str, BoundStream]:
    """Return each stream's sealed collections. A failure is a reason, not an exception."""
    return {
        str(stream_id): _one(inventory, data_root)
        for stream_id, inventory in records.inventories.items()
    }


def paired_membership(
    diverse: DiscoveryRecords, uniform: DiscoveryRecords, data_root: Path
) -> dict[str, BoundStream]:
    """Bind both runs and keep a stream only when they name the same collections."""
    left = bind_membership(diverse, data_root)
    right = bind_membership(uniform, data_root)
    merged: dict[str, BoundStream] = {}
    for stream in sorted(set(left) | set(right)):
        one = left.get(stream)
        other = right.get(stream)
        merged[stream] = one if one is not None and one == other else BoundStream((), DISAGREE)
    return merged


def _one(inventory: Mapping[str, Any], data_root: Path) -> BoundStream:
    source = inventory.get("source_sha256")
    seal = inventory.get("source_manifest_sha256")
    if not isinstance(source, str) or not isinstance(seal, str):
        return BoundStream((), UNNAMED)
    try:
        record = pinned_source_record(source, seal, data_root)
    except CorpusRefusal:
        return BoundStream((), UNAVAILABLE)
    origin = record.get("origin")
    if not isinstance(origin, list) or not origin:
        return BoundStream((), NO_ORIGIN)
    collections = _collections(origin)
    if collections is None:
        return BoundStream((), INCOMPLETE_ORIGIN)
    return BoundStream(collections, None)


def _collections(origin: Sequence[object]) -> tuple[CollectionId, ...] | None:
    found: list[CollectionId] = []
    seen: set[tuple[str, str]] = set()
    for item in origin:
        if not isinstance(item, dict):
            return None
        provider = item.get("provider")
        collection = item.get("collection_id")
        if provider not in _PROVIDERS or not isinstance(collection, str) or not collection:
            return None
        key = (provider, collection)
        if key in seen:
            continue
        seen.add(key)
        found.append(CollectionId(provider, collection))
    found.sort(key=lambda item: (item.provider, item.collection_id))
    return tuple(found)
