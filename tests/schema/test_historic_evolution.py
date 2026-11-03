"""Real historic records witness breaking shapes, without treating samples as full contracts."""

import json
from typing import Any

import pytest
from referencing import Registry

from ss_track.schema.evolution import diff_schemas, required_bump
from ss_track.schema.strict import violations
from tests.corpus._historic import kept_record


def observed_shape(value: Any) -> dict[str, Any]:
    """Project observed keys and types only; omit values so changing a seal or stamp proves nothing."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {key: observed_shape(child) for key, child in value.items()},
            "required": sorted(value),
            "additionalProperties": False,
        }
    if isinstance(value, list):
        return {"type": "array", "items": observed_shape(value[0]) if value else {}}
    types = {str: "string", int: "integer", float: "number", bool: "boolean", type(None): "null"}
    return {"type": types[type(value)]}


@pytest.mark.parametrize(
    ("before", "after", "changed"),
    [
        ("corpus-schema-1-294535c", "corpus-schema-2-78db68c", "/properties/sequences"),
        ("bundle-schema-1-294535c", "bundle-schema-2-78db68c", "/properties/sequence_id"),
        ("corpus-schema-2-78db68c", "corpus-schema-3-d6b704d", "/properties/generated_cases"),
        ("bundle-schema-2-78db68c", "bundle-schema-3-d6b704d", "/properties/generated"),
        (
            "source-schema-1-d6b704d",
            "source-schema-2-129a350",
            "/properties/rights/properties/retain_until",
        ),
    ],
)
def test_all_five_real_bumps_are_major(before: str, after: str, changed: str) -> None:
    old, new = [observed_shape(json.loads(kept_record(name + ".json"))) for name in (before, after)]
    changes = diff_schemas(old, new)
    assert required_bump(changes) == "major"
    assert any(item.pointer == changed and item.bump == "major" for item in changes)
    assert not any(item.pointer.endswith(("schema_version", "manifest_sha256")) for item in changes)


def test_source_terms_added_without_a_bump_fail_the_previous_shape() -> None:
    old = json.loads(kept_record("corpus-schema-3-d6b704d.json"))
    new = json.loads(kept_record("corpus-schema-3-129a350.json"))
    assert old["schema_version"] == new["schema_version"] == 3
    found = violations(new, observed_shape(old), Registry())
    assert any(
        item.pointer == "/streams/0/rights" and item.keyword == "additionalProperties"
        for item in found
    )
    changes = diff_schemas(observed_shape(old), observed_shape(new))
    assert any(
        "/properties/rights/properties/retain_until" in item.pointer and item.bump == "major"
        for item in changes
    )
