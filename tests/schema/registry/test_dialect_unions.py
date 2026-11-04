"""A union in the dialect: one required tag on every branch, with values that tell them apart."""

from typing import Any

import pytest
from referencing import Registry

from ss_track.schema.registry.dialect import dialect_findings
from ss_track.schema.validation.strict import violations
from tests.schema.registry._dialect_cases import CLOSED, DIALECT, NAME, tagged_branch, with_property


@pytest.mark.parametrize(
    "branches",
    [
        pytest.param([tagged_branch("a"), tagged_branch("a")], id="one value twice"),
        pytest.param(
            [{**tagged_branch("a"), "required": []}, {**tagged_branch("b"), "required": []}],
            id="tag not required",
        ),
    ],
)
def test_a_union_needs_one_required_tag_that_separates_every_branch(
    branches: list[dict[str, Any]],
) -> None:
    schema = with_property({"oneOf": branches, "description": "A union."})

    assert any("no shared tag" in item for item in dialect_findings(schema, DIALECT))


@pytest.mark.parametrize(
    "branches",
    [
        pytest.param([{"type": "string"}, {"type": "integer"}], id="bare types"),
        pytest.param(
            [
                {**CLOSED, "properties": {"a": NAME}, "required": ["a"]},
                {**CLOSED, "properties": {"b": NAME}, "required": ["b"]},
            ],
            id="objects with no const",
        ),
    ],
)
def test_the_meta_schema_alone_refuses_a_union_with_no_tag_in_a_branch(
    branches: list[dict[str, Any]],
) -> None:
    schema = with_property({"oneOf": branches, "description": "A union."})

    assert violations(schema, DIALECT, Registry())


def test_any_shared_tag_will_do_when_another_const_repeats() -> None:
    fixed = {"type": "string", "const": "same", "description": "Repeats."}
    union = {
        "oneOf": [tagged_branch("a", fixed=fixed), tagged_branch("b", fixed=fixed)],
        "description": "A.",
    }

    assert dialect_findings(with_property(union), DIALECT) == []


def test_tags_on_different_properties_are_not_a_shared_tag() -> None:
    first = tagged_branch("a")
    second = {
        "type": "object",
        "additionalProperties": False,
        "required": ["shape"],
        "properties": {"shape": {"type": "string", "const": "b", "description": "A tag."}},
    }
    schema = with_property({"oneOf": [first, second], "description": "A union."})

    assert any("no shared tag" in item for item in dialect_findings(schema, DIALECT))
