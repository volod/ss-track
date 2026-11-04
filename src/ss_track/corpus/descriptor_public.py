"""Public descriptor rows for non-locked streams, limited to frozen public fields."""

from typing import Any

from ss_track.corpus.frames import frame_name
from ss_track.schema.disclosure import project_public
from ss_track.schema.store import ContractSet, damaged, load_contract_set

_CORPUS = "record/corpus-manifest"
_SOURCE = "record/source-manifest"
_BUNDLE = "record/frame-bundle"
_LOCKED = "locked"


def public_tables(
    corpus: dict[str, Any], records: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Drop locked sequences and every value the current contracts do not mark public."""
    locked = {stream["stream_id"] for stream in corpus["streams"] if stream["split"] == _LOCKED}
    contracts = load_contract_set()
    registry = contracts.schema_registry()
    corpus_urn, corpus_schema = _schema(contracts, _CORPUS)
    source_urn, source_schema = _schema(contracts, _SOURCE)
    bundle_urn, bundle_schema = _schema(contracts, _BUNDLE)
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
    bundles = []
    frames = []
    for bundle in records["bundles"]:
        if _locked_bundle(bundle, locked):
            continue
        projected = project_public(bundle, bundle_schema, registry, bundle_urn)
        if not isinstance(projected, dict):
            continue
        bundles.append(projected)
        frames.extend(_frames(projected))
    return {"streams": streams, "bundles": bundles, "frames": frames}


def _schema(contracts: ContractSet, name: str) -> tuple[str, dict[str, Any]]:
    contract = contracts.named(name)
    version = contract.newest()
    if version is None:
        raise damaged(f"{name} has no frozen version")
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
    return generated.get("split") == _LOCKED or generated.get("parent_stream_id") in locked


def _frames(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    identity = bundle.get("identity")
    if not isinstance(identity, dict):
        return []
    rows = []
    for entry in identity.get("frames", []):
        if isinstance(entry, dict):
            row = _frame(bundle, identity, entry)
            if row:
                rows.append(row)
    return rows


def _frame(
    bundle: dict[str, Any], identity: dict[str, Any], entry: dict[str, Any]
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    if "stream_id" in bundle:
        row["stream_id"] = bundle["stream_id"]
    if "frame_index" in entry:
        row["frame_index"] = entry["frame_index"]
        row["content_frame_index"] = entry.get("content_frame_index", entry["frame_index"])
    for key in ("pts", "sha256"):
        if key in entry:
            row[key] = entry[key]
    for key in ("width", "height", "pixel_format", "bytes_per_frame", "time_base"):
        if key in identity:
            row[key] = identity[key]
    if {"stream_id", "frame_index", "pixel_format"} <= row.keys():
        row["path"] = (
            f"../../frames/{row['stream_id']}/{frame_name(row['frame_index'], row['pixel_format'])}"
        )
    if "generated" in bundle:
        row["generated"] = bundle["generated"] is not None
    return row
