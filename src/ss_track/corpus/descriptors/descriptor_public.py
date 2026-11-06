"""Public descriptor rows for non-locked streams, limited to frozen public fields."""

from typing import Any

from ss_track.corpus.descriptors.descriptor_rows import frame_rows
from ss_track.corpus.records.kinds import (
    CORPUS_MANIFEST,
    FRAME_BUNDLE,
    SOURCE_MANIFEST,
    RecordFormat,
)
from ss_track.schema.registry.store import ContractSet, damaged
from ss_track.schema.views.disclosure import project_public

LOCKED = "locked"
SPLITS = ("development", "calibration", LOCKED)  # the corpus contract's `split` values, card order


def public_tables(
    corpus: dict[str, Any], records: dict[str, list[dict[str, Any]]], contracts: ContractSet
) -> dict[str, list[dict[str, Any]]]:
    """Drop locked sequences and every value the current contracts do not mark public."""
    locked = {stream["stream_id"] for stream in corpus["streams"] if stream["split"] == LOCKED}
    registry = contracts.schema_registry()
    corpus_urn, corpus_schema = _schema(contracts, CORPUS_MANIFEST)
    source_urn, source_schema = _schema(contracts, SOURCE_MANIFEST)
    bundle_urn, bundle_schema = _schema(contracts, FRAME_BUNDLE)
    scenario = project_public(
        corpus["scenario_rights"],
        corpus_schema["properties"]["scenario_rights"],
        registry,
        corpus_urn,
    )
    stream_schema = corpus_schema["properties"]["streams"]["items"]
    streams = []
    for row in records["streams"]:
        if row["stream"]["stream_id"] in locked:
            continue
        streams.append(
            _stream(row, stream_schema, source_schema, scenario, registry, corpus_urn, source_urn)
        )
    bundles: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
    for bundle in records["bundles"]:
        if _locked_bundle(bundle, locked):
            continue
        projected = project_public(bundle, bundle_schema, registry, bundle_urn)
        if not isinstance(projected, dict):
            continue
        bundles.append(projected)
        frames.extend(frame_rows(projected))
    return {"streams": streams, "bundles": bundles, "frames": frames}


def _schema(contracts: ContractSet, record_format: RecordFormat) -> tuple[str, dict[str, Any]]:
    """Return the newest version of a format's contract, whose marks decide what is public."""
    contract = contracts.records_by_kind().get(record_format.kind)
    version = None if contract is None else contract.newest()
    if contract is None or version is None:
        raise damaged(f"no frozen contract states {record_format.kind}")
    return contract.urn(version), contracts.frozen_schema(contract, version)


def _stream(
    row: dict[str, Any],
    stream_schema: dict[str, Any],
    source_schema: dict[str, Any],
    scenario: Any,
    registry: Any,
    corpus_urn: str,
    source_urn: str,
) -> dict[str, Any]:
    projected = {
        "stream": project_public(row["stream"], stream_schema, registry, corpus_urn),
        "source": project_public(row["source"], source_schema, registry, source_urn),
    }
    if scenario:
        projected["scenario_rights"] = scenario
    return {key: value for key, value in projected.items() if value}


def _locked_bundle(bundle: dict[str, Any], locked: set[str]) -> bool:
    if bundle["stream_id"] in locked:
        return True
    generated = bundle.get("generated")
    if not isinstance(generated, dict):
        return False
    return generated.get("split") == LOCKED or generated.get("parent_stream_id") in locked
