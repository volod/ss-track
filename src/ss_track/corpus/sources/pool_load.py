"""Read a pool declaration and the acquisitions it selects."""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import Fields, invalid
from ss_track.corpus.sources.pool_acquisition import (
    AcquisitionFacts,
    InventoryVideo,
    load_acquisition,
    require_terms,
)
from ss_track.schema.validation.enforce import read_declaration

POOL_CONTRACT = "declaration/corpus-pool"


@dataclass(frozen=True, slots=True)
class LoadedVideo:
    """One selected video and the inventory facts the pool may copy."""

    path: str
    split: str
    upstream_split: str | None
    source_reference: str | None
    annotation_reference: str | None
    attribution: str
    terms: str
    terms_reference: str
    content_sha256: str
    local_path: str


@dataclass(frozen=True, slots=True)
class LoadedCollection:
    """One acquisition and the videos the declaration selects from it."""

    run_id: str
    provider: str
    collection_id: str
    provider_version: str
    rights: dict[str, JsonValue]
    sensitivity: dict[str, JsonValue]
    videos: tuple[LoadedVideo, ...]
    acquired_sources: dict[str, str | None]
    metadata: tuple[tuple[str, Path, str], ...]
    name_rules: dict[str, tuple[str, str]]


@dataclass(frozen=True, slots=True)
class LoadedPool:
    """A validated pool declaration and the acquisitions it names."""

    corpus_id: str
    run_id: str
    scenario_rights: dict[str, JsonValue]
    declaration_sha256: str
    collections: tuple[LoadedCollection, ...]
    related: tuple[tuple[tuple[str, str], ...], ...]


def load_pool(path: Path, data_root: Path) -> LoadedPool:
    """Validate a pool declaration and every acquisition it selects."""
    raw = read_declaration(path, POOL_CONTRACT, 1)
    fields = Fields(raw, "pool")
    collections = tuple(
        _collection(Fields(item, f"pool.collections[{index}]"), data_root)
        for index, item in enumerate(fields.items("collections"))
    )
    runs = [item.run_id for item in collections]
    if len(set(runs)) != len(runs):
        raise invalid("a pool repeats an acquisition run")
    return LoadedPool(
        _ascii(fields, "corpus_id"),
        _ascii(fields, "run_id"),
        _scenario(fields.child("scenario_rights")),
        sha256_bytes(canonical_json(cast(dict[str, JsonValue], raw))),
        collections,
        _related(fields, collections),
    )


def _collection(fields: Fields, data_root: Path) -> LoadedCollection:
    run_id = _ascii(fields, "run_id")
    facts = load_acquisition(run_id, data_root)
    videos = tuple(_video(item, facts) for item in _video_fields(fields))
    paths = [video.path for video in videos]
    if len(set(paths)) != len(paths):
        raise invalid("a collection repeats a video path")
    return LoadedCollection(
        run_id,
        facts.provider,
        facts.collection_id,
        facts.provider_version,
        _rights(fields.child("rights")),
        _sensitivity(fields.child("sensitivity")),
        videos,
        _sources(facts),
        facts.metadata,
        _name_rules(fields, facts),
    )


def _name_rules(fields: Fields, facts: AcquisitionFacts) -> dict[str, tuple[str, str]]:
    """Return each CSV file's operator rule as its name prefix and video path prefix."""
    acquired = {path for path, _local, _digest in facts.metadata}
    rules: dict[str, tuple[str, str]] = {}
    for index, raw in enumerate(fields.optional_items("metadata_names")):
        rule = Fields(raw, f"{fields.where}.metadata_names[{index}]")
        file = _ascii(rule, "file")
        if file not in acquired or not file.lower().endswith(".csv"):
            raise invalid("a metadata_names rule must name an acquired CSV metadata file")
        if file in rules:
            raise invalid("a metadata_names rule repeats a metadata file")
        prefixes = (rule.string("name_prefix"), rule.string("path_prefix"))
        if any(".." in prefix.split("/") for prefix in prefixes):
            raise invalid("a metadata_names prefix must not name a parent directory")
        rules[file] = prefixes
    return rules


def _sources(facts: AcquisitionFacts) -> dict[str, str | None]:
    return {
        path: facts.inventory[path].source_reference if path in facts.inventory else None
        for path in facts.videos
    }


def _video_fields(fields: Fields) -> tuple[Fields, ...]:
    return tuple(
        Fields(item, f"{fields.where}.videos[{index}]")
        for index, item in enumerate(fields.items("videos"))
    )


def _video(fields: Fields, facts: AcquisitionFacts) -> LoadedVideo:
    path = _ascii(fields, "path")
    acquired = facts.videos.get(path)
    inventory = facts.inventory.get(path)
    if acquired is None or inventory is None:
        raise invalid("a selected video is not in the acquisition")
    require_terms(inventory)
    return _loaded(fields, path, acquired.sha256, acquired.local_path, inventory)


def _loaded(
    fields: Fields, path: str, digest: str, local_path: str, inventory: InventoryVideo
) -> LoadedVideo:
    assert inventory.attribution is not None
    assert inventory.terms is not None
    assert inventory.terms_reference is not None
    return LoadedVideo(
        path,
        _ascii(fields, "split"),
        inventory.upstream_split,
        inventory.source_reference,
        inventory.annotation_reference,
        inventory.attribution,
        inventory.terms,
        inventory.terms_reference,
        digest,
        local_path,
    )


def _related(
    fields: Fields, collections: tuple[LoadedCollection, ...]
) -> tuple[tuple[tuple[str, str], ...], ...]:
    selected = {(item.run_id, video.path) for item in collections for video in item.videos}
    groups = []
    for index, raw in enumerate(fields.optional_items("related")):
        if not isinstance(raw, list):
            raise TypeError("pool.related is not a list: its contract and reader disagree")
        members = tuple(
            _member(item, f"pool.related[{index}][{at}]") for at, item in enumerate(raw)
        )
        if len(set(members)) != len(members) or any(member not in selected for member in members):
            raise invalid("a related group must name distinct selected videos")
        groups.append(members)
    return tuple(groups)


def _member(raw: object, where: str) -> tuple[str, str]:
    fields = Fields(raw, where)
    return _ascii(fields, "run_id"), _ascii(fields, "path")


def _scenario(fields: Fields) -> dict[str, JsonValue]:
    return {
        "max_sensitivity": _ascii(fields, "max_sensitivity"),
        "sharing": _ascii(fields, "sharing"),
    }


def _rights(fields: Fields) -> dict[str, JsonValue]:
    recorded: dict[str, JsonValue] = {
        "basis": _ascii(fields, "basis"),
        "derived_frames": fields.boolean("derived_frames"),
        "holder": _ascii(fields, "holder"),
        "retain_until": fields.nullable_date("retain_until"),
        "retention": _ascii(fields, "retention"),
        "sharing": _ascii(fields, "sharing"),
    }
    if isinstance(recorded["retain_until"], str) and not recorded["retain_until"].isascii():
        raise invalid(f"{fields.where}.retain_until must be ASCII")
    return recorded


def _sensitivity(fields: Fields) -> dict[str, JsonValue]:
    recorded: dict[str, JsonValue] = {"level": _ascii(fields, "level")}
    if fields.has("notes"):
        recorded["notes"] = _ascii(fields, "notes")
    return recorded


def _ascii(fields: Fields, key: str) -> str:
    value = fields.text(key)
    if not value.isascii():
        raise invalid(f"{fields.where}.{key} must be ASCII")
    return value
