"""Keep only values a frozen contract explicitly marks public.

An unmarked value is absent. A restricted or sensitive value hides its children, so a public mark
nested under one does not publish it. Containers stay only when a public descendant remains.
"""

from typing import Any

from referencing import Registry
from referencing.exceptions import Unresolvable

from ss_track.schema.compatibility.evolution import resolved
from ss_track.schema.validation.strict import Schema, branch_tags, union_tag

_DROP = object()
_BLOCKING = frozenset({"restricted", "sensitive"})
_PUBLIC = "public"


def project_public(value: Any, schema: Schema, registry: Registry[Any], base_uri: str) -> Any:
    """Return the public projection of one value, or an empty object when nothing qualifies."""
    try:
        projected = _project(value, schema, registry.resolver(base_uri))
    except Unresolvable:
        return {}
    return {} if projected is _DROP else projected


def _project(value: Any, schema: Schema, resolver: Any) -> Any:
    schema, resolver = resolved(schema, resolver)
    if schema.get("x-sensitivity") in _BLOCKING:
        return _DROP
    if "oneOf" in schema and isinstance(schema["oneOf"], list):
        branch = _branch(value, schema["oneOf"])
        return _DROP if branch is None else _project(value, branch, resolver)
    if isinstance(value, dict) and isinstance(schema.get("properties"), dict):
        return _object(value, schema, resolver)
    if isinstance(value, list) and "items" in schema:
        return _array(value, schema, resolver)
    if schema.get("x-sensitivity") == _PUBLIC:
        return value
    return _DROP


def _object(value: dict[str, Any], schema: Schema, resolver: Any) -> Any:
    properties = schema["properties"]
    projected: dict[str, Any] = {}
    for key, child in value.items():
        child_schema = properties.get(key)
        if not isinstance(child_schema, dict):
            continue
        found = _project(child, child_schema, resolver)
        if found is not _DROP:
            projected[key] = found
    if projected:
        return projected
    if schema.get("x-sensitivity") == _PUBLIC:
        return {}
    return _DROP


def _array(value: list[Any], schema: Schema, resolver: Any) -> Any:
    items = schema.get("items")
    public = schema.get("x-sensitivity") == _PUBLIC
    if not isinstance(items, dict):
        return value if public else _DROP
    if _scalars(value):
        return value if public else _DROP
    projected = [
        item for item in (_project(child, items, resolver) for child in value) if item is not _DROP
    ]
    if projected:
        return projected
    return [] if public else _DROP


def _scalars(value: list[Any]) -> bool:
    return all(not isinstance(item, dict | list) for item in value)


def _branch(value: Any, branches: list[Any]) -> Schema | None:
    """Return the tagged branch this value selects, or nothing when the tag is unknown."""
    if not isinstance(value, dict):
        return None
    schemas = [branch for branch in branches if isinstance(branch, dict)]
    if len(schemas) != len(branches):
        return None
    tags = [branch_tags(branch) for branch in schemas]
    tag = union_tag(tags)
    if tag is None or tag not in value:
        return None
    for branch, marks in zip(schemas, tags, strict=True):
        if marks.get(tag) == value[tag]:
            return branch
    return None
