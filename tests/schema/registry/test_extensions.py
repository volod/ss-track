"""Tuple and open-detail extensions stay bounded and fingerprinted."""

import copy
import json
from typing import Any

import pytest

from ss_track.schema.registry.dialect import dialect_findings
from ss_track.schema.registry.fingerprints import meaning_fingerprint, structure_fingerprint, walk
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations
from tests.schema.conftest import CONTRACTS, contract_schema

DIALECT = json.loads((CONTRACTS / "meta/dialect.json").read_text())


def tuple_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "description": "A fixed pair.",
        "prefixItems": [
            {"type": "integer", "description": "Index.", "x-unit": "1"},
            {"type": "string", "description": "Value."},
        ],
        "items": False,
        "minItems": 2,
        "maxItems": 2,
    }


def test_tuple_walk_and_both_fingerprints_reach_positions() -> None:
    before = contract_schema("record", "tuple", "1.0.0", properties={"pair": tuple_schema()})
    assert not dialect_findings(before, DIALECT)
    assert any(node.get("description") == "Index." for node in walk(before))
    after = copy.deepcopy(before)
    position = after["properties"]["pair"]["prefixItems"][0]
    position["minimum"] = 1
    assert structure_fingerprint(before) != structure_fingerprint(after)
    assert meaning_fingerprint(before) == meaning_fingerprint(after)
    position.pop("minimum")
    position["x-unit"] = "s"
    assert structure_fingerprint(before) == structure_fingerprint(after)
    assert meaning_fingerprint(before) != meaning_fingerprint(after)


@pytest.mark.parametrize("field,value", [("minItems", 1), ("maxItems", 3), ("items", True)])
def test_tuple_bounds_cannot_drift(field: str, value: object) -> None:
    pair = tuple_schema() | {field: value}
    schema = contract_schema("record", "tuple", "1.0.0", properties={"pair": pair})
    assert dialect_findings(schema, DIALECT)


def test_nested_tuple_keyword_and_union_tags_are_checked() -> None:
    pair = tuple_schema()
    pair["prefixItems"][0]["if"] = {"type": "string"}
    schema = contract_schema("record", "tuple", "1.0.0", properties={"pair": pair})
    assert dialect_findings(schema, DIALECT)
    branch = {
        "type": "object",
        "properties": {"tag": {"type": "string", "const": "a", "description": "Tag."}},
        "required": ["tag"],
        "additionalProperties": False,
    }
    pair["prefixItems"][0] = {"oneOf": [branch, branch]}
    assert any("no shared tag" in finding for finding in dialect_findings(schema, DIALECT))


def test_only_command_result_details_can_be_open() -> None:
    details = {
        "type": "object",
        "description": "Context.",
        "properties": {},
        "additionalProperties": True,
    }
    schema = contract_schema("result", "command", "1.0.0", properties={"details": details})
    assert not dialect_findings(schema, DIALECT)
    assert dialect_findings(schema | {"$id": "urn:ss-track:contract:record:command:1.0.0"}, DIALECT)
    assert dialect_findings(schema | {"properties": {"other": details}}, DIALECT)
    closed = copy.deepcopy(schema)
    closed["properties"]["details"]["additionalProperties"] = False
    assert structure_fingerprint(schema) != structure_fingerprint(closed)
    assert meaning_fingerprint(schema) == meaning_fingerprint(closed)


@pytest.mark.parametrize("frame", [[0, None], [0, None, "a" * 64, "extra"], ["a" * 64, None, 0]])
def test_staged_hash_tuple_positions_are_enforced(frame: list[object]) -> None:
    contracts = load_contract_set()
    contract = contracts.named("record/staged-hashes")
    schema = contracts.frozen_schema(contract, contract.versions[-1])
    tuple_node = schema["properties"]["bundles"]["items"]["properties"]["frames"]["items"]
    assert violations(frame, tuple_node, contracts.schema_registry())
    assert not violations([0, None, "a" * 64], tuple_node, contracts.schema_registry())


@pytest.mark.parametrize("types", [["string", "number"], ["string", "number", "null"]])
def test_capture_scalar_union_is_narrow_and_fingerprinted(types: list[str]) -> None:
    node = {"type": types, "description": "Descriptive capture fact.", "x-unit": "1"}
    schema = contract_schema("record", "capture", "1.0.0", properties={"fact": node})
    assert not dialect_findings(schema, DIALECT)
    registry = load_contract_set().schema_registry()
    for accepted in ("manual", "", 3, 0.5):
        assert not violations(accepted, node, registry)
    assert bool(violations(None, node, registry)) == ("null" not in types)
    for refused in (True, [], {}):
        assert violations(refused, node, registry)
    narrow = copy.deepcopy(schema)
    narrow["properties"]["fact"]["type"] = "string"
    assert structure_fingerprint(schema) != structure_fingerprint(narrow)
    assert meaning_fingerprint(schema) == meaning_fingerprint(narrow)
