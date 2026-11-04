"""ODCS exports preserve source coverage while declaring the view's losses."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft201909Validator

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.schema.registry.contract import Contract
from ss_track.schema.registry.store import ContractSet, load_contract_set
from ss_track.schema.views.odcs import ODCS_SCHEMA, ODCS_SHA256, export_odcs
from ss_track.schema.views.odcs_projection import Projection


def _properties(node: dict[str, Any], pointer: str = "") -> set[str]:
    """Independently enumerate every source-schema property occurrence."""
    result = set()
    for keyword in ("properties", "$defs"):
        for name, child in node.get(keyword, {}).items():
            escaped = name.replace("~", "~0").replace("/", "~1")
            path = f"{pointer}/{keyword}/{escaped}"
            if keyword == "properties":
                result.add(path)
            result.update(_properties(child, path))
    for keyword in ("oneOf", "prefixItems"):
        for index, child in enumerate(node.get(keyword, [])):
            result.update(_properties(child, f"{pointer}/{keyword}/{index}"))
    if isinstance(node.get("items"), dict):
        result.update(_properties(node["items"], pointer + "/items"))
    return result


def _keywords(node: dict[str, Any], pointer: str = "") -> set[str]:
    """Enumerate schema keyword locations independently of the projector."""
    found = {f"{pointer}/{key.replace('~', '~0').replace('/', '~1')}" for key in node}
    for name, child in node.get("properties", {}).items():
        escaped = name.replace("~", "~0").replace("/", "~1")
        found |= _keywords(child, f"{pointer}/properties/{escaped}")
    for name, child in node.get("$defs", {}).items():
        escaped = name.replace("~", "~0").replace("/", "~1")
        found |= _keywords(child, f"{pointer}/$defs/{escaped}")
    for index, branch in enumerate(node.get("oneOf", [])):
        found |= _keywords(branch, f"{pointer}/oneOf/{index}")
    for index, item in enumerate(node.get("prefixItems", [])):
        found |= _keywords(item, f"{pointer}/prefixItems/{index}")
    if isinstance(node.get("items"), dict):
        found |= _keywords(node["items"], f"{pointer}/items")
    return found


def _custom(document: dict[str, Any], name: str) -> Any:
    return next(item["value"] for item in document["customProperties"] if item["property"] == name)


def test_all_contracts_validate_cover_source_properties_and_are_deterministic(
    tmp_path: Path,
) -> None:
    import hashlib

    contracts = load_contract_set()
    standard = contracts.root / ODCS_SCHEMA
    expected = "edb41f33ec46e84780e99872ab2bd67f074959d2bf3e9c9fc54e61f8982b0d93"
    assert expected == ODCS_SHA256
    assert hashlib.sha256(standard.read_bytes()).hexdigest() == expected
    validator = Draft201909Validator(json.loads(standard.read_bytes()))
    validator.check_schema(validator.schema)
    out = tmp_path / "odcs"
    result = export_odcs(out)
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*.json")}
    assert export_odcs(out) == result
    assert before == {p.relative_to(out): p.read_bytes() for p in out.rglob("*.json")}
    assert len(before) == len(contracts.contracts)
    for contract in contracts.contracts:
        _check_contract_view(out, contracts, contract, validator)


def _check_contract_view(
    out: Path, contracts: ContractSet, contract: Contract, validator: Draft201909Validator
) -> None:
    latest = contract.newest()
    assert latest is not None
    source = contracts.frozen_schema(contract, latest)
    document = json.loads((out / contract.family / f"{contract.contract_id}.json").read_bytes())
    assert not list(validator.iter_errors(document))
    assert (document["id"], document["version"]) == (contract.name, latest.version)
    if contract.family == "shared":
        assert "logicalType" not in document["schema"][0]
    assert _custom(document, "ssTrackContractUrn") == contract.urn(latest)
    assert _custom(document, "ssTrackJsonSchema") == source
    sources = {
        item
        for prop in document["schema"][0]["properties"]
        for custom in prop["customProperties"]
        if custom["property"] == "ssTrackSources"
        for item in custom["value"]
    }
    assert {contract.urn(latest) + "#" + path for path in _properties(source)} <= sources
    declared = {entry["pointer"] for entry in _custom(document, "ssTrackProjectionLosses")}
    assert declared == _keywords(source)


def test_tagged_union_merges_branch_fields_and_preserves_conflicting_types() -> None:
    contracts = load_contract_set()
    projection = Projection(contracts)
    union = {
        "type": "object",
        "properties": {
            "payload": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "tag": {"type": "string", "const": "a"},
                            "only_a": {"type": "integer"},
                            "common": {"type": "string"},
                        },
                    },
                    {
                        "type": "object",
                        "properties": {
                            "tag": {"type": "string", "const": "b"},
                            "only_b": {"type": "boolean"},
                            "common": {"type": "integer"},
                        },
                    },
                ]
            }
        },
    }
    fields = {
        item["name"]: item
        for item in projection.project(
            union, contracts.contracts[0].urn(contracts.contracts[0].versions[0])
        )
    }
    assert {
        "/properties/payload/properties/only_a",
        "/properties/payload/properties/only_b",
        "/properties/payload/properties/common",
        "/properties/payload/properties/tag",
    } <= fields.keys()
    assert "logicalType" not in fields["/properties/payload/properties/common"]
    assert len(fields["/properties/payload/properties/common"]["customProperties"][0]["value"]) == 2


@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_changed_standard_refuses_before_writing(tmp_path: Path, missing: bool) -> None:
    root = tmp_path / "contracts"
    shutil.copytree(load_contract_set().root, root)
    schema = root / ODCS_SCHEMA
    if missing:
        schema.unlink()
    else:
        schema.write_bytes(schema.read_bytes() + b" ")
    out = tmp_path / "output"
    with pytest.raises(CorpusRefusal) as caught:
        export_odcs(out, root)
    assert caught.value.code == RefusalCode.CONTRACT_SET_INVALID
    assert not out.exists()


def test_cli_export_and_existing_docs_emit_valid_command_results(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    caplog.set_level(logging.INFO)
    assert main(["contracts", "export", "--format", "odcs", "--out", str(tmp_path / "odcs")]) == 0
    result = json.loads(caplog.records[-1].getMessage())
    assert result["status"] == "exported"
    assert len(result["files"]) == len(load_contract_set().contracts)
    assert main(["contracts", "docs", "--out", str(tmp_path / "docs")]) == 0
    assert json.loads(caplog.records[-1].getMessage())["status"] == "written"


def test_recursive_references_terminate_and_dangling_references_refuse() -> None:
    contracts = load_contract_set()
    projection = Projection(contracts)
    urn = "urn:ss-track:contract:shared:recursive:1.0.0"
    recursive = {
        "$defs": {
            "node": {
                "type": "object",
                "properties": {"value": {"type": "integer"}, "next": {"$ref": "#/$defs/node"}},
            }
        },
        "$ref": "#/$defs/node",
    }
    projection.schemas[urn] = recursive
    fields = projection.project(recursive, urn)
    assert {"/properties/value", "/properties/next", "/$defs/node/properties/value"} <= {
        field["name"] for field in fields
    }
    assert len(fields) < 20
    with pytest.raises(CorpusRefusal) as caught:
        projection.project({"$ref": "#/$defs/missing"}, urn)
    assert caught.value.code == RefusalCode.CONTRACT_SET_INVALID


def test_property_names_do_not_collide_with_array_and_definition_paths() -> None:
    contracts = load_contract_set()
    projection = Projection(contracts)
    urn = contracts.contracts[0].urn(contracts.contracts[0].versions[0])
    schema = {
        "type": "object",
        "properties": {
            "[]": {"type": "string"},
            "@defs": {"type": "integer"},
            "array": {
                "type": "array",
                "items": {"type": "object", "properties": {"value": {"type": "integer"}}},
            },
        },
        "$defs": {"value": {"type": "object", "properties": {"child": {"type": "integer"}}}},
    }
    fields = {item["name"] for item in projection.project(schema, urn)}
    assert {
        "/properties/[]",
        "/properties/@defs",
        "/properties/array/items/properties/value",
        "/$defs/value/properties/child",
    } <= fields


def test_external_reference_expands_properties_with_the_original_source_pointer() -> None:
    contracts = load_contract_set()
    projection = Projection(contracts)
    origin = contracts.contracts[0].urn(contracts.contracts[0].versions[0])
    external = "urn:ss-track:contract:shared:example:1.0.0"
    projection.schemas[external] = {
        "$defs": {"node": {"type": "object", "properties": {"value": {"type": "string"}}}}
    }
    schema = {"type": "object", "properties": {"child": {"$ref": external + "#/$defs/node"}}}
    fields = {item["name"]: item for item in projection.project(schema, origin)}
    sources = fields["/properties/child/properties/value"]["customProperties"][0]["value"]
    assert sources == [external + "#/$defs/node/properties/value"]
