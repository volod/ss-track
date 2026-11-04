"""Breaks that need two coordinated values, missed when only one position changes."""

from typing import Any

import pytest

from ss_track.schema.strict import StrictValidator
from tests.schema import _oracle, _witness
from tests.schema.test_evolution import obj

NUMBER = {"type": "number", "minimum": 0, "maximum": 1}


def _sibling(minimum: int | None = None) -> dict[str, Any]:
    count: dict[str, Any] = {"type": "number"}
    if minimum is not None:
        count = count | {"minimum": minimum}
    return obj({"unit": {"const": "px"}, "count": count}) | {
        "dependentRequired": {"count": ["unit"]}
    }


def _pair(forbid: bool) -> dict[str, Any]:
    schema = obj({"x": NUMBER, "y": NUMBER}, ["x", "y"])
    if not forbid:
        return schema
    return schema | {
        "not": {
            "required": ["x", "y"],
            "properties": {"x": {"const": 1}, "y": {"const": 1}},
        }
    }


def _nested(minimum: int | None = None) -> dict[str, Any]:
    number: dict[str, Any] = {"type": "number"}
    if minimum is not None:
        number = number | {"minimum": minimum}
    return obj({"ready": {"const": True}, "item": obj({"n": number}, ["n"])}) | {
        "dependentRequired": {"item": ["ready"]}
    }


def _array(forbid: bool) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "array",
        "items": NUMBER,
        "minItems": 2,
        "maxItems": 2,
    }
    if not forbid:
        return schema
    return schema | {"not": {"const": [1, 1]}}


def _branch(tag: str, field: str, schema: dict[str, Any]) -> dict[str, Any]:
    return obj({"tag": {"const": tag}, field: schema}, ["tag", field])


def _union(forbid: bool) -> dict[str, Any]:
    arm = {
        "oneOf": [
            _branch("a", "n", {"type": "number"}),
            _branch("b", "s", {"type": "string"}),
        ]
    }
    schema = obj({"left": arm, "right": arm}, ["left", "right"])
    if not forbid:
        return schema
    mismatch: dict[str, Any] = {
        "type": "object",
        "required": ["left", "right"],
        "properties": {
            "left": {"properties": {"tag": {"const": "a"}}, "required": ["tag"]},
            "right": {"properties": {"tag": {"const": "b"}}, "required": ["tag"]},
        },
    }
    swapped = {
        "type": "object",
        "required": ["left", "right"],
        "properties": {
            "left": {"properties": {"tag": {"const": "b"}}, "required": ["tag"]},
            "right": {"properties": {"tag": {"const": "a"}}, "required": ["tag"]},
        },
    }
    return schema | {"not": {"anyOf": [mismatch, swapped]}}


def _across(forbid: bool) -> dict[str, Any]:
    arm = obj({"n": NUMBER}, ["n"])
    schema = obj({"left": arm, "right": arm}, ["left", "right"])
    if not forbid:
        return schema
    return schema | {"not": {"const": {"left": {"n": 1}, "right": {"n": 1}}}}


CASES = [
    ("optional sibling", _sibling(), _sibling(1), {"count": 0, "unit": "px"}),
    ("two fields", _pair(False), _pair(True), {"x": 1, "y": 1}),
    ("nested sibling", _nested(), _nested(1), {"item": {"n": 0}, "ready": True}),
    ("array pair", _array(False), _array(True), [1, 1]),
    (
        "oneOf combination",
        _union(False),
        _union(True),
        {"left": {"n": 0, "tag": "a"}, "right": {"s": "", "tag": "b"}},
    ),
    (
        "across objects",
        _across(False),
        _across(True),
        {"left": {"n": 1}, "right": {"n": 1}},
    ),
]


def _prepared(
    old: dict[str, Any], new: dict[str, Any]
) -> tuple[list[str], list[Any], _witness.Holds]:
    accepts, refuses = StrictValidator(old), StrictValidator(new)

    def holds(value: Any) -> bool:
        return accepts.is_valid(value) and not refuses.is_valid(value)

    names = _witness.property_names([old, new])
    values = _witness.boundary_values([old, new], [])
    return names, values, holds


@pytest.mark.parametrize(
    ("old", "new", "witness"),
    [case[1:] for case in CASES],
    ids=[str(case[0]) for case in CASES],
)
def test_one_position_misses_the_break_and_a_false_compatible_verdict_is_refuted(
    old: dict[str, Any], new: dict[str, Any], witness: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    names, values, holds = _prepared(old, new)
    assert _witness.search_one_position(old, names, values, holds) is _witness.NONE
    monkeypatch.setattr(
        _oracle.jsoncompat, "analyze_compat", lambda *_args: {"status": "compatible"}
    )
    assert _oracle.verdict(old, new).witness == witness
    assert holds(witness)


def test_search_stops_within_the_trial_bound() -> None:
    calls = 0

    def holds(_value: Any) -> bool:
        nonlocal calls
        calls += 1
        return False

    props = {f"p{index}": {"type": "string"} for index in range(40)}
    schema = {"type": "object", "properties": props, "additionalProperties": False, "required": []}
    values = ["a", "b", "c", "d", "e", "f", "g", "h"]
    assert _witness.search(schema, list(props), values, holds) is _witness.NONE
    assert calls <= _witness.MAX_TRIALS + _witness.PAIR_BUDGET
    assert calls > _witness.PAIR_BUDGET
