"""The section 17.3 table, repeated at nested paths and within tagged branches."""

import copy
import json
from typing import Any

import pytest

from ss_track.schema.compatibility.evolution import diff_schemas, required_bump
from tests.schema.compatibility._oracle import require_oracle_agreement, verdict


def obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
        "required": required or [],
    }


TEXT = {"type": "string", "description": "Text."}
NUMBER = {"type": "number", "description": "Number."}
# before, after, required bump, backward structural compatibility (the oracle cannot see meaning).
CASES = [
    (TEXT, TEXT | {"description": "Reworded."}, "patch", True),
    (TEXT, TEXT | {"title": "Title"}, "patch", True),
    (TEXT, TEXT | {"examples": ["example"]}, "patch", True),
    (obj({}), obj({"added": TEXT}), "minor", True),
    (obj({}), obj({"added": TEXT}, ["added"]), "major", False),
    (obj({"kept": TEXT}), obj({}), "major", False),
    (obj({"old": TEXT}), obj({"new": TEXT}), "major", False),
    (TEXT | {"enum": ["a"]}, TEXT | {"enum": ["a", "b"]}, "minor", True),
    (TEXT | {"enum": ["a", "b"]}, TEXT | {"enum": ["a"]}, "major", False),
    (NUMBER | {"minimum": 2}, NUMBER | {"minimum": 1}, "minor", True),
    (NUMBER | {"minimum": 1}, NUMBER | {"minimum": 2}, "major", False),
    (TEXT | {"pattern": "^[ab]+$"}, TEXT, "minor", True),
    (TEXT | {"pattern": "^[abc]+$"}, TEXT | {"pattern": "^[ab]+$"}, "major", False),
    ({"type": "integer"}, NUMBER, "minor", True),
    (NUMBER, {"type": "integer"}, "major", False),
    (TEXT, NUMBER, "major", False),
    (TEXT, {"type": ["string", "number"]}, "minor", True),
    ({"type": ["string", "number"]}, {"type": ["string", "number", "null"]}, "minor", True),
    ({"type": ["string", "number", "null"]}, TEXT, "major", False),
    (NUMBER, NUMBER | {"x-unit": "m"}, "minor", True),
    (TEXT | {"x-sensitivity": "public"}, TEXT | {"x-sensitivity": "restricted"}, "minor", True),
    (TEXT | {"x-sensitivity": "sensitive"}, TEXT | {"x-sensitivity": "public"}, "major", True),
    (TEXT | {"x-vocabulary": "enum-v1"}, TEXT | {"x-vocabulary": "enum-v2"}, "major", True),
    *[
        (NUMBER | {key: "old"}, NUMBER | {key: "new"}, "major", True)
        for key in ("x-unit", "x-clock", "x-frame", "x-quantity")
    ],
]


def _wrapped(value: dict[str, Any], branch: bool) -> dict[str, Any]:
    nested = obj({"payload": value}, ["payload"])
    if branch:
        nested["properties"]["tag"] = {"type": "string", "const": "a"}
        nested["required"].append("tag")
        nested = {"oneOf": [nested, obj({"tag": {"type": "string", "const": "b"}}, ["tag"])]}
    return obj({"nested": nested}, ["nested"])


@pytest.mark.parametrize("branch", [False, True])
@pytest.mark.parametrize(("old", "new", "bump", "compatible"), CASES)
def test_rule_table_and_independent_oracle(
    old: dict[str, Any], new: dict[str, Any], bump: str, compatible: bool, branch: bool
) -> None:
    before, after = _wrapped(old, branch), _wrapped(new, branch)
    changes = diff_schemas(before, after)
    assert required_bump(changes) == bump
    prefix = "/properties/nested" + ("/oneOf/0" if branch else "") + "/properties/payload"
    assert changes and all(change.pointer.startswith(prefix) for change in changes)
    assert verdict(before, after).compatible is compatible


@pytest.mark.parametrize(
    "key",
    [
        "minimum",
        "exclusiveMinimum",
        "maximum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    ],
)
def test_every_bound_direction_and_removal(key: str) -> None:
    old = {"type": "number", key: 2}
    relaxing = 1 if key in {"minimum", "exclusiveMinimum", "minLength", "minItems"} else 3
    assert required_bump(diff_schemas(old, old | {key: relaxing})) == "minor"
    assert required_bump(diff_schemas(old | {key: relaxing}, old)) == "major"
    assert required_bump(diff_schemas(old, {"type": "number"})) == "minor"


@pytest.mark.parametrize("container", ["items", "prefixItems", "$ref"])
def test_containers_walk_semantics_and_escape_pointers(container: str) -> None:
    old = obj({"a/b~c": NUMBER | {"x-unit": "m"}})
    if container == "items":
        old = {"type": "array", "items": old}
    elif container == "prefixItems":
        old = {"type": "array", "prefixItems": [old], "items": False, "minItems": 1, "maxItems": 1}
    else:
        old = obj({"use": {"$ref": "#/$defs/target"}}) | {"$defs": {"target": old}}
    new = json.loads(json.dumps(old).replace('"x-unit": "m"', '"x-unit": "s"'))
    changes = diff_schemas(old, new)
    assert required_bump(changes) == "major"
    assert all("a~1b~0c/x-unit" in item.pointer for item in changes)
    if container == "$ref":
        assert any("/properties/use/" in item.pointer for item in changes)


def test_tag_reordering_is_no_change_but_addition_and_removal_are_classified() -> None:
    old = _wrapped(TEXT, True)
    new = copy.deepcopy(old)
    branches = new["properties"]["nested"]["oneOf"]
    branches.reverse()
    assert diff_schemas(old, new) == []
    branches.append(obj({"tag": {"type": "string", "const": "c"}}, ["tag"]))
    assert required_bump(diff_schemas(old, new)) == "minor"
    assert required_bump(diff_schemas(new, old)) == "major"


def test_optional_constraint_inside_open_details_is_breaking() -> None:
    old = obj({"details": obj({}) | {"additionalProperties": True}}, ["details"])
    new = obj({"details": obj({"value": TEXT}) | {"additionalProperties": True}}, ["details"])
    assert required_bump(diff_schemas(old, new)) == "major"
    assert require_oracle_agreement(old, new).witness == {"details": {"value": 0}}


def test_structural_pattern_proofs_cover_groups_and_optional_parts() -> None:
    for old, new in (("^(ab)+$", "^(ab|cd)+$"), ("^[0-9]+/[1-9][0-9]*$", "^-?[0-9]+/[1-9][0-9]*$")):
        before, after = TEXT | {"pattern": old}, TEXT | {"pattern": new}
        assert required_bump(diff_schemas(before, after)) == "minor"
        assert require_oracle_agreement(before, after).proofs == (f"{old} within {new}",)


def test_reshaped_pattern_inclusion_is_a_minor_and_the_oracle_agrees() -> None:
    old, new = TEXT | {"pattern": "^(ab)*$"}, TEXT | {"pattern": "^a*(ba)*b*$"}
    assert required_bump(diff_schemas(old, new)) == "minor"
    assert require_oracle_agreement(old, new).proofs == ("^(ab)*$ within ^a*(ba)*b*$",)


def test_reshaped_pattern_break_stays_major_and_the_oracle_agrees() -> None:
    old, new = TEXT | {"pattern": "^(ab)*$"}, TEXT | {"pattern": "^(ba)*$"}
    assert required_bump(diff_schemas(old, new)) == "major"
    witness = require_oracle_agreement(old, new).witness
    assert isinstance(witness, str) and witness.replace("ab", "") == "" and len(witness) >= 2


def test_const_boolean_is_not_the_integer_one() -> None:
    assert required_bump(diff_schemas({"const": True}, {"const": 1})) == "major"


def test_pattern_relaxation_is_proven_by_classifier_and_oracle() -> None:
    old, new = TEXT | {"pattern": "^[ab]+$"}, TEXT | {"pattern": "^[abc]+$"}
    assert required_bump(diff_schemas(old, new)) == "minor"
    assert require_oracle_agreement(old, new).proofs == ("^[ab]+$ within ^[abc]+$",)
    assert require_oracle_agreement(new, old).witness == "c"


def test_every_real_transition_agrees_with_the_oracle() -> None:
    from ss_track.schema.registry.store import load_contract_set

    contracts = load_contract_set()
    registry = contracts.schema_registry()
    for contract in contracts.contracts:
        for old, new in zip(contract.versions, contract.versions[1:], strict=False):
            require_oracle_agreement(
                contracts.frozen_schema(contract, old),
                contracts.frozen_schema(contract, new),
                registry,
            )
