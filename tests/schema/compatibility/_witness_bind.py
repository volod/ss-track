"""Where a value sits in an old schema: the node that states it, through references and branches.

A tagged branch is chosen by its `const` values, so a value is checked against the node that would
accept it. `_witness_node` decides which values that node can accept.
"""

from typing import Any

from tests.schema.compatibility._witness_node import (
    Path,
    Schema,
    allowed_kinds,
    json_equal,
    value_kind,
)


def _resolve(root: Schema, node: Schema) -> Schema:
    seen: set[int] = set()
    while "$ref" in node:
        if id(node) in seen:
            return node
        seen.add(id(node))
        name = str(node["$ref"]).rsplit("/", 1)[-1]
        target = root.get("$defs", {}).get(name)
        if not isinstance(target, dict):
            return node
        node = target
    return node


def _consts_fit(branch: Schema, value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    props = branch.get("properties", {})
    matched = False
    for name in branch.get("required", []):
        prop = props.get(name)
        if not isinstance(prop, dict) or "const" not in prop:
            continue
        if name not in value or not json_equal(value[name], prop["const"]):
            return False
        matched = True
    return matched


def _branch_for(node: Schema, value: Any) -> Schema:
    branches = [branch for branch in node.get("oneOf", []) if isinstance(branch, dict)]
    for branch in branches:
        if _consts_fit(branch, value):
            return branch
    for branch in branches:
        allowed = allowed_kinds(branch)
        if allowed is None or value_kind(value) in allowed:
            return branch
    return branches[0] if branches else node


def bind_path(root: Schema, instance: Any) -> dict[Path, Schema]:
    found: dict[Path, Schema] = {}
    _bind_into(root, root, instance, (), found)
    return found


def _bind_into(
    root: Schema, node: Schema, value: Any, path: Path, found: dict[Path, Schema]
) -> None:
    node = _resolve(root, node)
    found[path] = node
    chosen = _resolve(root, _branch_for(node, value)) if "oneOf" in node else node
    if isinstance(value, dict):
        _bind_object(root, chosen, value, path, found)
    elif isinstance(value, list):
        _bind_list(root, chosen, value, path, found)


def _bind_object(
    root: Schema, node: Schema, value: dict[str, Any], path: Path, found: dict[Path, Schema]
) -> None:
    props = node.get("properties", {})
    extra = node.get("additionalProperties")
    for key, item in value.items():
        child = props.get(key)
        if not isinstance(child, dict):
            child = _extra_schema(extra)
        if isinstance(child, dict):
            _bind_into(root, child, item, (*path, key), found)


def _extra_schema(extra: Any) -> Schema | None:
    if extra is True:
        return {}
    return extra if isinstance(extra, dict) else None


def _bind_list(
    root: Schema, node: Schema, value: list[Any], path: Path, found: dict[Path, Schema]
) -> None:
    for index, item in enumerate(value):
        child = _item_schema(node, index)
        if isinstance(child, dict):
            _bind_into(root, child, item, (*path, index), found)


def _item_schema(node: Schema, index: int) -> Schema | None:
    prefix = node.get("prefixItems", [])
    if index < len(prefix) and isinstance(prefix[index], dict):
        return prefix[index]
    items = node.get("items")
    return items if isinstance(items, dict) else None


def missing_names(node: Schema, obj: dict[str, Any], names: list[str]) -> list[str]:
    extra = node.get("additionalProperties")
    if extra is True or isinstance(extra, dict):
        return [name for name in names if name not in obj]
    props = node.get("properties", {})
    return [name for name in sorted(props) if name not in obj and isinstance(props[name], dict)]


def property_schema(node: Schema, name: str) -> Schema:
    props = node.get("properties", {})
    if isinstance(props.get(name), dict):
        return props[name]
    extra = _extra_schema(node.get("additionalProperties"))
    return extra or {}
