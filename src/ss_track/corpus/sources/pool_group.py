"""Group selected videos before any corpus split is assigned.

The same bytes, the same evidenced source reference, and an operator's related group are one
component. A component that contains a locked or conflicting video is withheld together. Included
members that disagree on the operator split refuse the pool.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.declarations.origin import OriginMembership


@dataclass(frozen=True, slots=True)
class Selected:
    """One selected video after metadata claims have been merged with its inventory."""

    run_id: str
    path: str
    provider: str
    collection_id: str
    provider_version: str
    content_sha256: str
    local_path: str
    split: str
    upstream_split: str | None
    source_reference: str | None
    annotation_reference: str | None
    attribution: str
    terms: str
    terms_reference: str
    license_name: str | None
    license_reference: str | None
    metadata_sha256: str | None
    association: str
    block: str | None
    rights: dict[str, JsonValue]
    sensitivity: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Outcome:
    """What the pool decided for one selected video."""

    video: Selected
    status: str
    group_id: str | None


@dataclass(frozen=True, slots=True)
class StreamPlan:
    """One recording, which may carry several collection copies of the same bytes."""

    stream_id: str
    encounter_id: str
    group_id: str
    split: str
    source_sha256: str
    source_path: str
    rights: dict[str, JsonValue]
    sensitivity: dict[str, JsonValue]
    origins: tuple[OriginMembership, ...]
    members: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class GroupPlan:
    """Included streams that share one operator split."""

    group_id: str
    split: str
    streams: tuple[StreamPlan, ...]


def group_selected(
    videos: Sequence[Selected], related: Sequence[Sequence[tuple[str, str]]]
) -> tuple[tuple[Outcome, ...], tuple[GroupPlan, ...]]:
    """Return one decision per selected video and one plan per included group."""
    parents = list(range(len(videos)))
    _union_identity(parents, videos)
    _union_related(parents, videos, related)
    outcomes: list[Outcome] = []
    groups: list[GroupPlan] = []
    for members in _components(parents, videos):
        _require_same_rights(members)
        if any(item.block for item in members):
            outcomes.extend(_withheld(members))
            continue
        _require_one_split(members)
        plan = _included(members)
        groups.append(plan)
        outcomes.extend(Outcome(item, "included", plan.group_id) for item in members)
    if not groups:
        raise invalid("no selected video can be included")
    ordered = tuple(sorted(outcomes, key=lambda item: (item.video.run_id, item.video.path)))
    return ordered, tuple(sorted(groups, key=lambda item: item.group_id))


def _union_identity(parents: list[int], videos: Sequence[Selected]) -> None:
    by_hash: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for index, video in enumerate(videos):
        _join(parents, by_hash, video.content_sha256, index)
        if video.source_reference is not None:
            _join(parents, by_source, video.source_reference, index)


def _union_related(
    parents: list[int], videos: Sequence[Selected], related: Sequence[Sequence[tuple[str, str]]]
) -> None:
    index_of = {(video.run_id, video.path): index for index, video in enumerate(videos)}
    for group in related:
        anchor = index_of[group[0]]
        for member in group[1:]:
            _union(parents, anchor, index_of[member])


def _join(parents: list[int], seen: dict[str, int], key: str, index: int) -> None:
    previous = seen.get(key)
    if previous is None:
        seen[key] = index
        return
    _union(parents, previous, index)


def _union(parents: list[int], left: int, right: int) -> None:
    root = _find(parents, left)
    other = _find(parents, right)
    if root != other:
        parents[other] = root


def _find(parents: list[int], index: int) -> int:
    while parents[index] != index:
        parents[index] = parents[parents[index]]
        index = parents[index]
    return index


def _components(parents: list[int], videos: Sequence[Selected]) -> list[list[Selected]]:
    found: dict[int, list[Selected]] = {}
    for index, video in enumerate(videos):
        found.setdefault(_find(parents, index), []).append(video)
    return list(found.values())


def _require_same_rights(members: Sequence[Selected]) -> None:
    clusters: dict[str, list[Selected]] = {}
    for item in members:
        clusters.setdefault(item.content_sha256, []).append(item)
    for cluster in clusters.values():
        first = cluster[0]
        if any(
            item.rights != first.rights or item.sensitivity != first.sensitivity for item in cluster
        ):
            raise CorpusRefusal(
                RefusalCode.RIGHTS_CONFLICT,
                "recordings of the same bytes declare different rights",
                {"videos": [_place(item) for item in cluster]},
            )


def _require_one_split(members: Sequence[Selected]) -> None:
    if len({item.split for item in members}) == 1:
        return
    raise CorpusRefusal(
        RefusalCode.SPLIT_LEAKAGE,
        "related recordings declare different splits",
        {"videos": [_place(item) | {"split": item.split} for item in members]},
    )


def _place(video: Selected) -> dict[str, JsonValue]:
    return {"path": video.path, "run_id": video.run_id}


def _withheld(members: Sequence[Selected]) -> tuple[Outcome, ...]:
    return tuple(Outcome(item, _blocked_status(item), None) for item in members)


def _blocked_status(video: Selected) -> str:
    if video.block == "locked":
        return "withheld_locked"
    if video.block == "conflict":
        return "association_conflict"
    return "withheld_related"


def _included(members: Sequence[Selected]) -> GroupPlan:
    group_id = _group_id(members)
    streams = tuple(
        sorted(
            (_stream(cluster, group_id) for cluster in _clusters(members)),
            key=lambda item: item.stream_id,
        )
    )
    return GroupPlan(group_id, members[0].split, streams)


def _clusters(members: Sequence[Selected]) -> list[list[Selected]]:
    found: dict[str, list[Selected]] = {}
    for item in members:
        found.setdefault(item.content_sha256, []).append(item)
    return list(found.values())


def _stream(cluster: Sequence[Selected], group_id: str) -> StreamPlan:
    chosen = min(cluster, key=lambda item: (item.path, item.run_id))
    origins = tuple(
        sorted(cluster, key=lambda item: (item.provider, item.collection_id, item.path))
    )
    digest = chosen.content_sha256
    return StreamPlan(
        "s" + digest[:32],
        "e" + digest[:32],
        group_id,
        chosen.split,
        digest,
        f"../../{chosen.run_id}/{chosen.local_path}",
        dict(chosen.rights),
        dict(chosen.sensitivity),
        tuple(_origin(item) for item in origins),
        tuple(sorted(((item.run_id, item.path) for item in origins), key=lambda item: item)),
    )


def _origin(video: Selected) -> OriginMembership:
    return OriginMembership(
        video.provider,
        video.collection_id,
        video.provider_version,
        video.path,
        video.content_sha256,
        video.upstream_split,
        video.source_reference,
        video.annotation_reference,
        video.attribution,
        video.terms,
        video.terms_reference,
        video.license_name,
        video.license_reference,
        video.metadata_sha256,
    )


def _group_id(members: Sequence[Selected]) -> str:
    keys: list[JsonValue] = [
        {"path": item.path, "run_id": item.run_id}
        for item in sorted(members, key=lambda item: (item.run_id, item.path))
    ]
    return "g" + sha256_bytes(canonical_json({"members": keys}))[:32]
