"""Independent structural checks; oracle disagreements are errors, never policy overrides."""

import copy
import json
from typing import Any

import jsoncompat
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from ss_track.schema.evolution import _resolved, diff_schemas, required_bump
from ss_track.schema.fingerprints import subschemas


def _expanded(schema: dict[str, Any], registry: Registry[Any]) -> dict[str, Any]:
    def expand(node: dict[str, Any], resolver: Any) -> dict[str, Any]:
        resolved, scope = _resolved(node, resolver)
        result = copy.deepcopy(resolved)
        for child in subschemas(result):
            changed = expand(dict(child), scope)
            child.clear()
            child.update(changed)
        for key in list(result):
            if key.startswith("x-") or key in {
                "$id",
                "$schema",
                "$defs",
                "description",
                "title",
                "examples",
            }:
                del result[key]
        return result

    return expand(schema, registry.resolver_with_root(DRAFT202012.create_resource(schema)))


def require_oracle_agreement(
    old: dict[str, Any], new: dict[str, Any], registry: Registry[Any] | None = None
) -> None:
    resources = registry if registry is not None else Registry()
    before, after = _expanded(old, resources), _expanded(new, resources)
    expected = required_bump(diff_schemas(before, after)) != "major"
    found = jsoncompat.check_compat(json.dumps(before), json.dumps(after), "deserializer")
    assert found == expected, (
        f"jsoncompat disagreement: classifier backward={expected}, oracle={found}"
    )
