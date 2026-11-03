"""What a contract may say: the dialect meta-schema, and the contextual rules it cannot state."""

from collections.abc import Mapping
from typing import Any

from referencing import Registry

from ss_track.schema._patterns import parse
from ss_track.schema.fingerprints import walk
from ss_track.schema.strict import Schema, branch_tags, union_tag, violations

_UNION = "oneOf"


def union_findings(schema: Mapping[str, Any]) -> list[str]:
    """Name each union with no shared tag, which needs two branches at once to see."""
    unions = (node[_UNION] for node in walk(schema) if _UNION in node)
    return [
        f"oneOf with branches {[sorted(branch_tags(branch)) for branch in union]} has no shared tag"
        for union in unions
        if union_tag([branch_tags(branch) for branch in union]) is None
    ]


def dialect_findings(schema: Schema, dialect: Schema) -> list[str]:
    """Return every way one contract leaves the dialect."""
    refused = [
        f"{item.pointer}: {item.message}" for item in violations(schema, dialect, Registry())
    ]
    return refused or union_findings(schema) + _extension_findings(schema) + pattern_findings(
        schema
    )


def pattern_findings(schema: Mapping[str, Any]) -> list[str]:
    """Name each pattern outside the syntax every engine reads alike and the proof can compare.

    `.` and a negated class match line terminators and astral characters differently in Python's
    `re` and ECMA-262, so a value could pass here and fail elsewhere; lookaround, backreferences,
    non-ASCII text and top-level alternation are refused for the same reason or because no change
    to them can be classified.
    """
    return [
        f"pattern {node['pattern']!r} uses syntax outside ASCII literals, escapes, positive "
        "classes, groups, alternation and quantifiers anchored at both ends"
        for node in walk(schema)
        if isinstance(node.get("pattern"), str) and parse(node["pattern"]) is None
    ]


def _extension_findings(schema: Schema) -> list[str]:
    """Keep extensions confined to fixed tuples and command-result details."""
    details = schema.get("properties", {}).get("details")
    is_result = str(schema.get("$id", "")).startswith("urn:ss-track:contract:result:command:")
    findings = []
    for node in walk(schema):
        if node.get("additionalProperties") is True and not (is_result and node is details):
            findings.append("additionalProperties true is allowed only in command-result details")
        if "prefixItems" in node:
            size = len(node["prefixItems"])
            if node.get("minItems") != size or node.get("maxItems") != size:
                findings.append("prefixItems requires minItems and maxItems equal to tuple length")
    return findings
