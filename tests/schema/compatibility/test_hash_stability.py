"""Closed previous contracts and retained producer output guard unchanged-feature writes."""

import copy
from typing import Any

import pytest
from referencing import Registry

from ss_track.core.canonical import canonical_json
from ss_track.schema.validation.strict import violations
from tests._sealing import self_sealed
from tests.schema.compatibility.test_evolution import obj


def require_stable_output(
    previous: dict[str, Any],
    output: dict[str, Any],
    schema: dict[str, Any],
    registry: Registry[Any],
) -> None:
    assert not violations(output, schema, registry), (
        "writer no longer validates against previous minor"
    )
    assert canonical_json(previous) == canonical_json(output), (
        "writer changed existing bytes or seal"
    )


@pytest.mark.parametrize("value", [None, "default"])
def test_unused_new_field_fails_even_when_latest_minor_accepts_it(value: Any) -> None:
    before = self_sealed({"kind": "test", "schema_version": 1})
    schema = obj(
        {
            "kind": {"type": "string"},
            "schema_version": {"type": "integer"},
            "manifest_sha256": {"type": "string"},
        }
    )
    latest = copy.deepcopy(schema)
    latest["properties"]["new"] = {"type": ["string", "null"]}
    after = self_sealed(before | {"new": value})
    assert not violations(after, latest, Registry())
    with pytest.raises(AssertionError, match="previous minor"):
        require_stable_output(before, after, schema, Registry())


def test_unannounced_key_and_changed_existing_value_fail() -> None:
    schema = obj({"name": {"type": "string"}})
    with pytest.raises(AssertionError, match="previous minor"):
        require_stable_output({"name": "a"}, {"name": "a", "unannounced": 1}, schema, Registry())
    with pytest.raises(AssertionError, match="existing bytes"):
        require_stable_output({"name": "a"}, {"name": "b"}, schema, Registry())
