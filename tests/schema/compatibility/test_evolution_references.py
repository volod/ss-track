"""References, recursive shapes and scalar identity keep the same evolution rules."""

import copy
from typing import Any

import pytest
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.evolution import diff_schemas, required_bump
from tests.schema.compatibility._oracle import require_oracle_agreement
from tests.schema.compatibility.test_evolution import NUMBER, TEXT, obj


def test_external_ref_target_is_compared_at_the_use_site() -> None:
    old_type = {"$id": "urn:types:1", "$defs": {"value": NUMBER | {"x-unit": "m"}}}
    new_type = {"$id": "urn:types:2", "$defs": {"value": NUMBER | {"x-unit": "s"}}}
    registry = Registry().with_resources(
        [(schema["$id"], DRAFT202012.create_resource(schema)) for schema in (old_type, new_type)]
    )
    old = obj({"value": {"$ref": "urn:types:1#/$defs/value"}})
    new = obj({"value": {"$ref": "urn:types:2#/$defs/value"}})
    changes = diff_schemas(old, new, registry)
    assert required_bump(changes) == "major"
    assert changes[0].pointer == "/properties/value/x-unit"


def test_equal_reference_targets_and_inline_shapes_are_equivalent() -> None:
    old = obj({"value": {"$ref": "#/$defs/value"}}) | {"$defs": {"value": TEXT}}
    new = copy.deepcopy(old)
    new["properties"]["value"] = TEXT
    assert diff_schemas(old, new) == []


def test_recursive_shapes_terminate_and_still_compare_fields() -> None:
    node = obj({"value": TEXT, "next": {"$ref": "#/$defs/node"}})
    old = obj({"head": {"$ref": "#/$defs/node"}}) | {"$defs": {"node": node}}
    new = copy.deepcopy(old)
    new["$defs"]["node"]["properties"]["value"] = NUMBER
    changes = diff_schemas(old, new)
    assert required_bump(changes) == "major"
    assert any(change.pointer == "/properties/head/properties/value/type" for change in changes)
    assert require_oracle_agreement(old, new).witness == {"head": {"value": ""}}
    widened = copy.deepcopy(old)
    widened["$defs"]["node"]["properties"]["note"] = TEXT
    assert required_bump(diff_schemas(old, widened)) == "minor"
    assert require_oracle_agreement(old, widened).compatible
    deeper = copy.deepcopy(old)
    deeper["$defs"]["node"]["properties"]["value"] = TEXT | {"pattern": "^[ab]+$"}
    assert require_oracle_agreement(old, deeper).witness == {"head": {"value": ""}}


@pytest.mark.parametrize("target", ["missing", "cycle"])
def test_dangling_and_unproductive_cyclic_aliases_refuse(target: str) -> None:
    schema = obj({"value": {"$ref": f"#/$defs/{target}"}})
    schema["$defs"] = {"cycle": {"$ref": "#/$defs/cycle"}}
    with pytest.raises(CorpusRefusal):
        diff_schemas(schema, schema)


def test_enum_boolean_and_integer_are_different_values() -> None:
    assert required_bump(diff_schemas({"enum": [True]}, {"enum": [1]})) == "major"


@pytest.mark.parametrize(
    ("old", "new", "bump"),
    [
        (obj({"value": TEXT}, ["value"]), obj({"value": TEXT}), "minor"),
        (TEXT | {"format": "date"}, TEXT, "minor"),
        (TEXT, TEXT | {"format": "date"}, "major"),
        (obj({}), obj({}) | {"additionalProperties": True}, "minor"),
        (NUMBER | {"x-unit": "m"}, NUMBER, "major"),
    ],
)
def test_remaining_keyword_rules(old: dict[str, Any], new: dict[str, Any], bump: str) -> None:
    assert required_bump(diff_schemas(old, new)) == bump


def test_repeated_local_fragment_in_distinct_resources_is_not_an_alias_cycle() -> None:
    first = {
        "$id": "urn:first",
        "$defs": {
            "entry": {"$ref": "#/$defs/value"},
            "value": {"$ref": "urn:second#/$defs/entry"},
        },
    }
    second = {
        "$id": "urn:second",
        "$defs": {
            "entry": {"$ref": "#/$defs/value"},
            "value": TEXT,
        },
    }
    registry = Registry().with_resources(
        [(schema["$id"], DRAFT202012.create_resource(schema)) for schema in (first, second)]
    )
    before = obj({"value": {"$ref": "urn:first#/$defs/entry"}})
    after = obj({"value": TEXT | {"description": "Updated."}})
    assert required_bump(diff_schemas(before, after, registry)) == "patch"
