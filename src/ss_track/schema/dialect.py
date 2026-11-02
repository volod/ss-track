"""What a contract may say: the dialect meta-schema, and the one rule it cannot state."""

from collections.abc import Mapping
from typing import Any

from referencing import Registry

from ss_track.schema.fingerprints import walk
from ss_track.schema.strict import Schema, violations

_UNION = "oneOf"


def _tags(branch: Mapping[str, Any]) -> dict[str, object]:
    """Return the properties that identify one branch: required, with one fixed value."""
    required = branch.get("required", ())
    properties = branch.get("properties", {})
    return {
        name: child["const"]
        for name, child in properties.items()
        if name in required and "const" in child
    }


def _union_tag(branches: list[dict[str, object]]) -> str | None:
    """Return a property that tells every branch from every other, if one exists."""
    shared = set(branches[0]).intersection(*branches[1:])
    for name in sorted(shared):
        values = [branch[name] for branch in branches]
        if all(values.count(value) == 1 for value in values):
            return name
    return None


def union_findings(schema: Mapping[str, Any]) -> list[str]:
    """Name each union with no shared tag, which needs two branches at once to see."""
    unions = (node[_UNION] for node in walk(schema) if _UNION in node)
    return [
        f"oneOf with branches {[sorted(_tags(branch)) for branch in union]} has no shared tag"
        for union in unions
        if _union_tag([_tags(branch) for branch in union]) is None
    ]


def dialect_findings(schema: Schema, dialect: Schema) -> list[str]:
    """Return every way one contract leaves the dialect."""
    refused = [
        f"{item.pointer}: {item.message}" for item in violations(schema, dialect, Registry())
    ]
    return refused or union_findings(schema)
