"""Which disposition a major transition may declare for the major it replaces.

A `view` derives every current field from an old record by a pure function. It may never derive an
operator judgment or change an algorithm revision, so a major that adds or changes one of those
properties leaves its predecessor's records lacking facts only an operator can state: its floor is
`facts`. The floor reads property names, not values, so it is the same for a schema and for the
observed shape of a real record.
"""

from collections.abc import Iterable, Iterator
from typing import Any

from referencing import Registry
from referencing.jsonschema import DRAFT202012

from ss_track.schema.evolution import ENTRY_ADDED, ENTRY_REMOVED, Change, resolved
from ss_track.schema.store import FACTS, VIEW
from ss_track.schema.strict import Schema

# What an operator states for a record: rights, sensitivity, retention, placement and encounter.
JUDGMENT_PROPERTIES = frozenset(
    {
        "rights",
        "sensitivity",
        "scenario_rights",
        "retention",
        "retain_until",
        "derived_frames",
        "split",
        "group_id",
        "encounter_id",
    }
)
# Algorithm revisions: new pixels need new evidence, so no view may restate them.
REVISION_PROPERTIES = frozenset(
    {"decode_policy", "decode_policy_sha256", "transform", "recipe", "revision"}
)
PROTECTED_PROPERTIES = JUDGMENT_PROPERTIES | REVISION_PROPERTIES
_MAJOR = "major"
_CONTAINERS = {"properties", "$defs"}
_NOT_DERIVED = {"items", "prefixItems"}  # an added list may be derived empty, whatever it holds


def pointer_parts(pointer: str) -> list[str]:
    """Split a JSON pointer into its unescaped segments."""
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]


def named_properties(parts: Iterable[str]) -> Iterator[str]:
    """Yield the property names a schema pointer passes through."""
    previous = ""
    for part in parts:
        if previous in _CONTAINERS:
            yield part
        previous = part


def disposition_floor(
    changes: Iterable[Change], new: Schema, registry: Registry[Any] | None = None
) -> str:
    """Return the least strict disposition a major with these changes may declare."""
    resolver = (registry or Registry()).resolver_with_root(DRAFT202012.create_resource(new))
    for change in changes:
        if change.bump != _MAJOR or change.reason.endswith(ENTRY_REMOVED):
            continue
        parts = pointer_parts(change.pointer)
        names = set(named_properties(parts))
        if change.reason.endswith(ENTRY_ADDED):
            names |= set(_subtree_properties(_node_at(new, parts, resolver)))
        if names & PROTECTED_PROPERTIES:
            return FACTS
    return VIEW


def _node_at(schema: Schema, parts: list[str], resolver: Any) -> Schema | None:
    """Follow a use-site pointer through every reference it crosses, or return None."""
    node: Any = schema
    for part in parts:
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict):
            node, resolver = resolved(node, resolver)
            node = node.get(part)
        else:
            return None
    return node if isinstance(node, dict) else None


def _subtree_properties(node: Any) -> Iterator[str]:
    """Yield the property names an added node states, without entering what a list holds."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _NOT_DERIVED:
                continue
            if key == "properties" and isinstance(value, dict):
                yield from value
            yield from _subtree_properties(value)
    elif isinstance(node, list):
        for item in node:
            yield from _subtree_properties(item)
