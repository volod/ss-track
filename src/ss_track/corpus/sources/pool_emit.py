"""Write the recording declarations, corpus declaration and pool record for one selection."""

from dataclasses import dataclass
from typing import cast

from ss_track.core.refusal import JsonValue, RefusalCode
from ss_track.corpus.declarations.declaration import (
    CORPUS_CONTRACT,
    CORPUS_SCHEMA_VERSION,
    RECORDING_CONTRACT,
    RECORDING_SCHEMA_VERSION,
)
from ss_track.corpus.records.kinds import CORPUS_POOL
from ss_track.corpus.records.sealing import seal
from ss_track.corpus.review.export import declaration_bytes
from ss_track.corpus.sources.metadata_claims import Unresolved
from ss_track.corpus.sources.pool_group import GroupPlan, Outcome, StreamPlan
from ss_track.corpus.sources.pool_load import LoadedPool
from ss_track.schema.validation.enforce import installed_contracts, require_conforming

_STATUSES = ("association_conflict", "included", "withheld_locked", "withheld_related")


@dataclass(frozen=True, slots=True)
class PoolDocuments:
    """The bytes a pool publishes, with the sealed record still unwritten."""

    corpus: bytes
    recordings: tuple[tuple[str, bytes], ...]
    record: dict[str, JsonValue]


def emit(
    pool: LoadedPool,
    outcomes: tuple[Outcome, ...],
    groups: tuple[GroupPlan, ...],
    unresolved: list[Unresolved],
) -> PoolDocuments:
    """Validate every declaration and seal the pool record, writing nothing."""
    recordings = tuple(
        (stream.stream_id, _recording_bytes(stream)) for group in groups for stream in group.streams
    )
    corpus = _corpus_bytes(pool, groups)
    body = _body(pool, outcomes, groups, unresolved)
    return PoolDocuments(corpus, recordings, seal(body))


def _recording_bytes(stream: StreamPlan) -> bytes:
    document: dict[str, JsonValue] = {
        "schema_version": RECORDING_SCHEMA_VERSION,
        "source": {"path": stream.source_path, "sha256": stream.source_sha256},
        "rights": dict(stream.rights),
        "sensitivity": dict(stream.sensitivity),
        "origin": [item.to_record() for item in stream.origins],
    }
    _require(document, RECORDING_CONTRACT, RECORDING_SCHEMA_VERSION, "recording declaration")
    return declaration_bytes(document)


def _corpus_bytes(pool: LoadedPool, groups: tuple[GroupPlan, ...]) -> bytes:
    document: dict[str, JsonValue] = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "corpus_id": pool.corpus_id,
        "scenario_rights": dict(pool.scenario_rights),
        "groups": [_corpus_group(group) for group in groups],
    }
    _require(document, CORPUS_CONTRACT, CORPUS_SCHEMA_VERSION, "corpus declaration")
    return declaration_bytes(document)


def _corpus_group(group: GroupPlan) -> dict[str, JsonValue]:
    return {
        "group_id": group.group_id,
        "split": group.split,
        "encounters": [
            {
                "encounter_id": stream.encounter_id,
                "streams": [{"source_sha256": stream.source_sha256, "stream_id": stream.stream_id}],
            }
            for stream in group.streams
        ],
    }


def _body(
    pool: LoadedPool,
    outcomes: tuple[Outcome, ...],
    groups: tuple[GroupPlan, ...],
    unresolved: list[Unresolved],
) -> dict[str, JsonValue]:
    recorded: dict[str, JsonValue] = {
        **CORPUS_POOL.stamp(),
        "corpus_id": pool.corpus_id,
        "run_id": pool.run_id,
        "declaration_sha256": pool.declaration_sha256,
        "scenario_rights": dict(pool.scenario_rights),
        "videos": [_video(outcome) for outcome in outcomes],
        "groups": [_group(group) for group in groups],
        "unresolved": cast(
            list[JsonValue],
            [
                item.to_record()
                for item in sorted(unresolved, key=lambda item: (item.kind, item.path, item.detail))
            ],
        ),
        "accounting": cast(list[JsonValue], _accounting(outcomes)),
    }
    return recorded


def _video(outcome: Outcome) -> dict[str, JsonValue]:
    video = outcome.video
    return {
        "annotation_reference": video.annotation_reference,
        "association": video.association,
        "attribution": video.attribution,
        "collection_id": video.collection_id,
        "content_sha256": video.content_sha256,
        "group_id": outcome.group_id,
        "license": video.license_name,
        "license_reference": video.license_reference,
        "metadata_sha256": video.metadata_sha256,
        "path": video.path,
        "provider": video.provider,
        "provider_version": video.provider_version,
        "run_id": video.run_id,
        "source_reference": video.source_reference,
        "split": video.split,
        "status": outcome.status,
        "terms": video.terms,
        "terms_reference": video.terms_reference,
        "upstream_split": video.upstream_split,
    }


def _group(group: GroupPlan) -> dict[str, JsonValue]:
    return {
        "group_id": group.group_id,
        "split": group.split,
        "streams": [
            {
                "encounter_id": stream.encounter_id,
                "members": [{"path": path, "run_id": run_id} for run_id, path in stream.members],
                "source_sha256": stream.source_sha256,
                "stream_id": stream.stream_id,
            }
            for stream in group.streams
        ],
    }


def _accounting(outcomes: tuple[Outcome, ...]) -> list[dict[str, JsonValue]]:
    rows: dict[tuple[str, str], dict[str, JsonValue]] = {}
    for outcome in outcomes:
        video = outcome.video
        row = rows.setdefault(
            (video.provider, video.collection_id), _counts(video.provider, video.collection_id)
        )
        row[outcome.status] = cast(int, row[outcome.status]) + 1
        if video.association == "missing":
            row["missing_metadata"] = cast(int, row["missing_metadata"]) + 1
    return [rows[key] for key in sorted(rows)]


def _counts(provider: str, collection_id: str) -> dict[str, JsonValue]:
    return {
        "provider": provider,
        "collection_id": collection_id,
        "missing_metadata": 0,
        **{status: 0 for status in _STATUSES},
    }


def _require(document: dict[str, JsonValue], name: str, major: int, label: str) -> None:
    installed = installed_contracts()
    contract = installed.contracts.named(name)
    frozen = contract.newest(major)
    assert frozen is not None
    require_conforming(
        document,
        installed.contracts,
        contract,
        frozen,
        code=RefusalCode.MANIFEST_INVALID,
        label=label,
        registry=installed.registry,
    )
