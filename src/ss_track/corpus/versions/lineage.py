"""What a corpus version owes the versions it declares it supersedes.

Material already evaluated in one split has been seen, so it cannot reappear in another. One version
can drop a source and the next bring it back, so a new version answers to its whole declared chain,
not only to its nearest predecessor. Everything here reads records it is given and touches no disk,
and it reads only source hashes, groups and splits: a source's rights or frame window can change
between versions without moving the source. Reading the chain itself is `corpus.versions.predecessors`.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.projections import NotCompared, Unprojected
from ss_track.corpus.versions.predecessors import (
    Manifest,
    Predecessor,
    predecessor_identity,
    projected,
)

LINKED = "linked"
NO_LINEAGE = "no_lineage"

type StreamRecord = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Placement:
    """Where one version holds one source."""

    source_sha256: str
    group_id: str
    split: str


@dataclass(frozen=True, slots=True)
class VersionDelta:
    """Sources of a version against one other version, each list sorted by hash."""

    added: tuple[Placement, ...]
    removed: tuple[Placement, ...]
    kept: tuple[Placement, ...]


@dataclass(frozen=True, slots=True)
class Lineage:
    """How a built version relates to the chain it named."""

    supersedes: str
    supersedes_manifest_sha256: str
    compared_versions: tuple[str, ...]
    delta: VersionDelta
    not_compared: tuple[NotCompared, ...] = ()

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form. `added` and `removed` read the named version only.

        `not_compared` appears only when a version in the chain could not be compared, so a fully
        compared chain reports exactly what it did before projections existed.
        """
        delta = self.delta
        record: dict[str, JsonValue] = {
            "status": LINKED,
            "supersedes": self.supersedes,
            "supersedes_manifest_sha256": self.supersedes_manifest_sha256,
            "compared_versions": list(self.compared_versions),
            "added": _place_records(delta.added),
            "removed": _place_records(delta.removed),
            "kept": _place_records(delta.kept),
        }
        if self.not_compared:
            record["not_compared"] = [gap.to_record() for gap in self.not_compared]
        return record


def lineage_record(lineage: Lineage | None) -> dict[str, JsonValue]:
    """Report a version's lineage, saying so when it declared none."""
    return lineage.to_record() if lineage is not None else {"status": NO_LINEAGE}


def require_same_places(
    corpus_id: str, streams: Sequence[StreamRecord], predecessors: Sequence[Predecessor]
) -> None:
    """Refuse a source or group that a declared predecessor held elsewhere, naming every one."""
    predecessors = projected(predecessors)
    moved_sources = _moved_sources(corpus_id, streams, predecessors)
    moved_groups = _moved_groups(corpus_id, streams, predecessors)
    if moved_sources or moved_groups:
        raise CorpusRefusal(
            RefusalCode.SPLIT_LEAKAGE,
            f"{corpus_id} moves material its declared predecessors already placed",
            {
                "corpus_id": corpus_id,
                "moved_sources": _in_key_order(moved_sources),
                "moved_groups": _in_key_order(moved_groups),
            },
        )


def _moved_sources(
    corpus_id: str, streams: Sequence[StreamRecord], predecessors: Sequence[Manifest]
) -> dict[str, JsonValue]:
    """Map each moved source to its move. The nearest version comes last, so it is the one named."""
    places = _placements(streams)
    return {
        earlier.source_sha256: _move(version, earlier, corpus_id, places[earlier.source_sha256])
        | {"source_sha256": earlier.source_sha256}
        for version in reversed(predecessors)
        for earlier in _placements(version["streams"]).values()
        if earlier.source_sha256 in places and _differs(places[earlier.source_sha256], earlier)
    }


def _moved_groups(
    corpus_id: str, streams: Sequence[StreamRecord], predecessors: Sequence[Manifest]
) -> dict[str, JsonValue]:
    """Map each group that changed split to its move, as a group's name is a claim of relatedness.

    New sources in a group are related to the ones it held, so no source hash would catch them.
    """
    splits = {stream["group_id"]: stream["split"] for stream in streams}
    return {
        earlier.group_id: _move(
            version, earlier, corpus_id, replace(earlier, split=splits[earlier.group_id])
        )
        for version in reversed(predecessors)
        for earlier in _placements(version["streams"]).values()
        if splits.get(earlier.group_id, earlier.split) != earlier.split
    }


def compare_versions(
    streams: Sequence[StreamRecord], other: Sequence[StreamRecord]
) -> VersionDelta:
    """State which sources one version adds, removes and keeps against another."""
    current = _placements(streams)
    previous = _placements(other)
    return VersionDelta(
        added=_in_hash_order(current, current.keys() - previous.keys()),
        removed=_in_hash_order(previous, previous.keys() - current.keys()),
        kept=_in_hash_order(current, current.keys() & previous.keys()),
    )


def trace_lineage(
    streams: Sequence[StreamRecord], predecessors: Sequence[Predecessor]
) -> Lineage | None:
    """Describe a version that has passed `require_same_places`, or None if it named no version.

    The delta reads the named version, so it is empty when that one could not be compared.
    """
    if not predecessors:
        return None
    nearest = predecessors[0]
    supersedes, manifest_sha256 = predecessor_identity(nearest)
    return Lineage(
        supersedes=supersedes,
        supersedes_manifest_sha256=manifest_sha256,
        compared_versions=tuple(version["corpus_id"] for version in projected(predecessors)),
        delta=(
            VersionDelta((), (), ())
            if isinstance(nearest, Unprojected)
            else compare_versions(streams, nearest["streams"])
        ),
        not_compared=tuple(
            version.gap() for version in predecessors if isinstance(version, Unprojected)
        ),
    )


def _placements(streams: Iterable[StreamRecord]) -> dict[str, Placement]:
    """Return each source's place, which is one because a source stays in one group."""
    return {
        stream["source_sha256"]: Placement(
            stream["source_sha256"], stream["group_id"], stream["split"]
        )
        for stream in streams
    }


def _place_records(places: Sequence[Placement]) -> list[JsonValue]:
    return [asdict(place) for place in places]


def _differs(current: Placement, earlier: Placement) -> bool:
    return (current.group_id, current.split) != (earlier.group_id, earlier.split)


def _move(
    version: Manifest, earlier: Placement, corpus_id: str, now: Placement
) -> dict[str, JsonValue]:
    """State where one thing was and where a new version puts it, naming both versions."""
    return {
        "from": {"corpus_id": version["corpus_id"], **_place(earlier)},
        "to": {"corpus_id": corpus_id, **_place(now)},
    }


def _place(place: Placement) -> dict[str, JsonValue]:
    return {"group_id": place.group_id, "split": place.split}


def _in_key_order(entries: Mapping[str, JsonValue]) -> list[JsonValue]:
    return [entries[key] for key in sorted(entries)]


def _in_hash_order(places: Mapping[str, Placement], hashes: Iterable[str]) -> tuple[Placement, ...]:
    return tuple(places[source_sha256] for source_sha256 in sorted(hashes))
