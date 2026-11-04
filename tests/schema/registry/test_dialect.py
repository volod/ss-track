"""What a contract may say. Every refusal is tried at the root and nested, where it would hide."""

import copy
import json
from typing import Any

import pytest

from ss_track.schema.registry.dialect import dialect_findings
from tests.schema.conftest import CONTRACTS, contract_schema
from tests.schema.registry._dialect_cases import (
    CLOSED,
    DIALECT,
    ENCODED,
    NAME,
    OPEN,
    tagged_branch,
    with_property,
)

_REF = "urn:ss-track:contract:shared:types:1.0.0#/$defs/sha256"


def _nested_in_item(node: dict[str, Any]) -> dict[str, Any]:
    items = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"value": node},
    }
    array = {"type": "array", "description": "A list.", "items": items}
    return contract_schema(ENCODED, "test", "1.0.0", properties={"values": array})


def _nested_in_definition(node: dict[str, Any]) -> dict[str, Any]:
    return contract_schema(
        ENCODED,
        "test",
        "1.0.0",
        properties={"value": {"$ref": "#/$defs/held", "description": "Held."}},
        **{"$defs": {"held": node}},
    )


def _nested_in_branch(node: dict[str, Any]) -> dict[str, Any]:
    union = {
        "oneOf": [tagged_branch("a", value=node), tagged_branch("b")],
        "description": "A union.",
    }
    return contract_schema(ENCODED, "test", "1.0.0", properties={"value": union})


_POSITIONS = [with_property, _nested_in_item, _nested_in_definition, _nested_in_branch]
_REFUSED = {
    "object with no additionalProperties": OPEN,
    "object with additionalProperties true": {**OPEN, "additionalProperties": True},
    "map of a schema": {**OPEN, "additionalProperties": {"type": "string"}},
    "nullable open object": {**OPEN, "type": ["object", "null"]},
    "if": {"type": "string", "description": "A.", "if": {"type": "string"}},
    "then": {"type": "string", "description": "A.", "then": {"type": "string"}},
    "else": {"type": "string", "description": "A.", "else": {"type": "string"}},
    "not": {"type": "string", "description": "A.", "not": {"const": "x"}},
    "anyOf": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "A."},
    "allOf": {"allOf": [{"type": "string"}], "description": "A."},
    "patternProperties": {**CLOSED, "patternProperties": {"^a$": {"type": "string"}}},
    "dependentSchemas": {**CLOSED, "dependentSchemas": {"a": {"type": "string"}}},
    "unknown keyword": {"type": "string", "description": "A.", "sizeLimit": 3},
    "misspelled annotation": {"type": "number", "description": "A.", "x-units": "m"},
    "unknown sensitivity": {"type": "string", "description": "A.", "x-sensitivity": "secret"},
    "bad reference annotation": {"type": "string", "description": "A.", "x-references": "corpus"},
    "no type": {"description": "A."},
    "const with no type": {"const": 1, "description": "A."},
    "enum with no type": {"enum": [1], "description": "A."},
    "array with no items": {"type": "array", "description": "A."},
    "items off an array": {"type": "string", "description": "A.", "items": {"type": "string"}},
    "properties off an object": {"type": "string", "description": "A.", "properties": {}},
    "union of three types": {"type": ["string", "integer", "null"], "description": "A."},
    "union of two types": {"type": ["string", "integer"], "description": "A."},
    "null first": {"type": ["null", "string"], "description": "A."},
    "versionless reference": {
        "$ref": "urn:ss-track:contract:shared:types#/$defs/sha256",
        "description": "A.",
    },
    "reference with no definition": {
        "$ref": "urn:ss-track:contract:shared:types:1.0.0",
        "description": "A.",
    },
    "remote reference": {"$ref": "https://example.org/a.json", "description": "A."},
    "reference with a constraint": {"$ref": _REF, "description": "A.", "maxLength": 3},
    "unanchored pattern": {"type": "string", "description": "A.", "pattern": "[a-z]+"},
    "pattern anchored at one end": {"type": "string", "description": "A.", "pattern": "^[a-z]+"},
    "class meaning differs by language": {
        "type": "string",
        "description": "A.",
        "pattern": "^\\d+$",
    },
    "unparsable pattern": {"type": "string", "description": "A.", "pattern": "^[a$"},
    **{
        f"pattern with {name}": {"type": "string", "description": "A.", "pattern": pattern}
        for name, pattern in {
            "any character": "^.+$",
            "negated class": "^[^a]+$",
            "lookahead": "^(?=a)a+$",
            "backreference": "^(a)\\1$",
            "top-level alternation": "^a|b$",
            "non-ASCII text": "^\u00e9+$",
        }.items()
    },
    "format no local check enforces": {
        "type": "string",
        "description": "A.",
        "format": "date-time",
    },
    "undescribed": {"type": "string"},
    "empty description": {"type": "string", "description": ""},
    "union of bare types": {
        "oneOf": [{"type": "string"}, {"type": "integer"}],
        "description": "A.",
    },
    "union of objects with no const": {
        "oneOf": [
            {**CLOSED, "properties": {"a": NAME}, "required": ["a"]},
            {**CLOSED, "properties": {"b": NAME}, "required": ["b"]},
        ],
        "description": "A.",
    },
    "one branch": {"oneOf": [tagged_branch("a")], "description": "A."},
    "union with a sibling constraint": {
        "oneOf": [tagged_branch("a"), tagged_branch("b")],
        "description": "A.",
        "minLength": 1,
    },
    "union of references": {
        "oneOf": [{"$ref": _REF}, {"$ref": _REF}],
        "description": "A.",
    },
}
_DESCRIBED_BY_ITS_REFERRER = {"undescribed", "empty description"}


@pytest.mark.parametrize(
    ("position", "name"),
    [
        (position, name)
        for position in _POSITIONS
        for name in _REFUSED
        if not (position is _nested_in_definition and name in _DESCRIBED_BY_ITS_REFERRER)
    ],
)
def test_the_dialect_refuses_each_construct_everywhere(position: Any, name: str) -> None:
    assert dialect_findings(position(copy.deepcopy(_REFUSED[name])), DIALECT)


def test_a_definition_takes_its_description_from_each_property_that_refers_to_it() -> None:
    schema = _nested_in_definition({"type": "string"})

    assert dialect_findings(schema, DIALECT) == []


@pytest.mark.parametrize("position", _POSITIONS)
@pytest.mark.parametrize(
    "node",
    [
        pytest.param({"type": "string", "description": "A."}, id="plain"),
        pytest.param({"type": ["string", "null"], "description": "A."}, id="nullable"),
        pytest.param({**CLOSED, "type": ["object", "null"]}, id="nullable closed object"),
        pytest.param({"$ref": _REF, "description": "A."}, id="exact reference"),
        pytest.param({"type": "integer", "const": 1, "description": "A."}, id="const"),
        pytest.param({"type": "string", "enum": ["a", "b"], "description": "A."}, id="enum"),
        pytest.param(
            {"type": "string", "description": "A.", "pattern": "^[a-z]+$", "maxLength": 9},
            id="bounded",
        ),
        pytest.param(
            {
                "type": "number",
                "description": "A.",
                "minimum": 0,
                "x-unit": "m",
                "x-quantity": "range",
                "x-frame": "image",
                "x-clock": "capture",
                "x-vocabulary": "ffmpeg:AVColorSpace",
                "x-sensitivity": "restricted",
                "x-references": "record/frame-bundle#/properties/stream_id",
            },
            id="annotated",
        ),
        pytest.param({"type": "string", "description": "A.", "format": "date"}, id="date"),
        pytest.param(
            {"type": "string", "description": "A.", "pattern": "^[a-z0-9._-]+(\\.[0-9]+)?$"},
            id="literal dot in a class or escaped",
        ),
        pytest.param(
            {"oneOf": [tagged_branch("a"), tagged_branch("b")], "description": "A union."},
            id="tagged union",
        ),
    ],
)
def test_the_dialect_accepts_what_section_17_lists(position: Any, node: dict[str, Any]) -> None:
    assert dialect_findings(position(copy.deepcopy(node)), DIALECT) == []


def test_a_root_must_state_a_document() -> None:
    schema = contract_schema(ENCODED, "test", "1.0.0")
    del schema["type"]

    assert dialect_findings(schema, DIALECT)


def test_shared_types_state_definitions_and_no_document() -> None:
    types = json.loads((CONTRACTS / "shared" / "types" / "1.0.0.json").read_text(encoding="utf-8"))
    assert dialect_findings(types, DIALECT) == []

    assert dialect_findings(types | {"type": "object"}, DIALECT)
    assert dialect_findings({k: v for k, v in types.items() if k != "$defs"}, DIALECT)


@pytest.mark.parametrize("missing", ["$schema", "$id", "title", "description"])
def test_a_contract_states_its_identity(missing: str) -> None:
    schema = contract_schema(ENCODED, "test", "1.0.0")
    del schema[missing]

    assert dialect_findings(schema, DIALECT)


def test_an_identity_names_an_exact_version() -> None:
    schema = contract_schema(ENCODED, "test", "1.0.0")

    assert dialect_findings(schema | {"$id": "urn:ss-track:contract:record:test"}, DIALECT)
    assert dialect_findings(schema | {"$id": "urn:ss-track:contract:record:test:1.0"}, DIALECT)
    assert dialect_findings(schema | {"$id": "urn:ss-track:contract:record:test:01.0.0"}, DIALECT)
