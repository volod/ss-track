"""Per-collection estimates that keep each audit stratum's sampling design.

A sampled window keeps the weight of its stratum, ``population / sample_size``,
including windows that belong to other collections. A collection is not
reweighted as a sample of its own. Totals for a collection with no reviewed
sample stay null rather than zero.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

OBSERVATIONS = ("target_present", "target_absent", "confuser", "unknown")
_KNOWN = frozenset({"target_present", "target_absent", "confuser"})
WEIGHTING = "stratum_design"


@dataclass(frozen=True, slots=True)
class CollectionId:
    """One sealed provider collection."""

    provider: str
    collection_id: str

    def to_record(self) -> dict[str, str]:
        """Return the collection identity a command result can carry."""
        return {"provider": self.provider, "collection_id": self.collection_id}


@dataclass(frozen=True, slots=True)
class SampledWindow:
    """One audit draw, the two decisions, and the collections that contain it."""

    observation: str | None
    diverse: bool
    uniform: bool
    collections: tuple[CollectionId, ...]


@dataclass(frozen=True, slots=True)
class DomainStratum:
    """One audit stratum and how its population is divided across collections.

    ``population`` is the stratum's sealed frame. ``population_by_collection``
    counts a window once for each collection that records it. Windows with no
    collection increment ``incomplete_population`` instead.
    """

    name: str
    population: int
    sample: tuple[SampledWindow, ...]
    population_by_collection: tuple[tuple[CollectionId, int], ...]
    incomplete_population: int


def estimate_domains(strata: Sequence[DomainStratum]) -> dict[str, Any]:
    """Estimate each collection and the covariance of collections that share a stratum."""
    from ss_track.corpus.evaluation.collection_metrics import collection_metrics
    from ss_track.corpus.evaluation.covariance import source_covariance

    for stratum in strata:
        _check(stratum)
    collections = _collection_ids(strata)
    return {
        "weighting": WEIGHTING,
        "provenance": _provenance(strata),
        "partitions_population": _partitions(strata),
        "incomplete": _incomplete(strata),
        "shared_strata": [stratum.name for stratum in strata if _spans(stratum)],
        "covariance": source_covariance(strata, collections),
        "collections": [collection_metrics(strata, collection) for collection in collections],
    }


def _check(stratum: DomainStratum) -> None:
    counted = len(stratum.sample)
    if stratum.population < 1 or counted > stratum.population or stratum.incomplete_population < 0:
        raise ValueError("invalid audit stratum size")
    members: dict[CollectionId, int] = {}
    incomplete = 0
    for item in stratum.sample:
        if not item.collections:
            incomplete += 1
            continue
        for collection in set(item.collections):
            members[collection] = members.get(collection, 0) + 1
    if incomplete > stratum.incomplete_population:
        raise ValueError("invalid audit stratum size")
    populations = dict(stratum.population_by_collection)
    if any(count > populations.get(collection, 0) for collection, count in members.items()):
        raise ValueError("invalid audit stratum size")


def _population(stratum: DomainStratum, collection: CollectionId) -> int:
    return sum(count for name, count in stratum.population_by_collection if name == collection)


def _spans(stratum: DomainStratum) -> bool:
    classes = sum(1 for _, count in stratum.population_by_collection if count > 0)
    if stratum.incomplete_population:
        classes += 1
    return classes > 1


def _partitions(strata: Sequence[DomainStratum]) -> bool:
    if not strata:
        return False
    for stratum in strata:
        assigned = sum(count for _, count in stratum.population_by_collection)
        if stratum.incomplete_population or assigned != stratum.population:
            return False
        if any(len(set(item.collections)) != 1 for item in stratum.sample):
            return False
    return True


def _provenance(strata: Sequence[DomainStratum]) -> str:
    for stratum in strata:
        if stratum.incomplete_population or any(not item.collections for item in stratum.sample):
            return "incomplete"
    return "complete"


def _collection_ids(strata: Sequence[DomainStratum]) -> list[CollectionId]:
    found: set[CollectionId] = set()
    for stratum in strata:
        found.update(name for name, count in stratum.population_by_collection if count > 0)
        for item in stratum.sample:
            found.update(item.collections)
    return sorted(found, key=lambda item: (item.provider, item.collection_id))


def _incomplete(strata: Sequence[DomainStratum]) -> dict[str, Any]:
    sampled = 0
    reviewed = 0
    unknown = 0
    for stratum in strata:
        for item in stratum.sample:
            if item.collections:
                continue
            sampled += 1
            if item.observation is not None:
                reviewed += 1
            if item.observation not in _KNOWN:
                unknown += 1
    return {
        "pool_windows": sum(stratum.incomplete_population for stratum in strata),
        "sampled_windows": sampled,
        "reviewed_windows": reviewed,
        "unknown_sampled": unknown,
        "reasons": [],
    }


def _unknown(stratum: DomainStratum, collection: CollectionId) -> bool:
    return any(
        collection in item.collections and item.observation not in _KNOWN for item in stratum.sample
    )


def _reviewed(strata: Sequence[DomainStratum], collection: CollectionId) -> int:
    return sum(
        collection in item.collections and item.observation is not None
        for stratum in strata
        for item in stratum.sample
    )
