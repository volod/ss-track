"""Which values an old schema node can accept, and where a value sits in that schema.

The search uses this instead of validating every string named anywhere in the document. A value the
node itself rejects can never be a witness, so it is not worth a validator call.
"""

import json
from collections.abc import Iterator
from typing import Any

from ss_track.schema.fingerprints import walk
from tests.schema import _automaton

type Schema = dict[str, Any]
type Path = tuple[Any, ...]

SIMPLEST: tuple[Any, ...] = (0, "", False, None, [], {})
DATE = "2000-01-01"
_BOUNDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
_LENGTHS = ("minLength", "maxLength")
_STEPS = (-1, -0.5, 0, 0.5, 1)
SCALARS = ("null", "boolean", "number", "string")


def _key(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _json_equal(left: Any, right: Any) -> bool:
    return _key(left) == _key(right)


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object" if isinstance(value, dict) else ""


def _type_names(node: Schema) -> set[str]:
    raw = node.get("type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    return set()


def _allowed_kinds(node: Schema) -> set[str] | None:
    """Kinds this node can accept, or none when a local reading would be a guess."""
    if "oneOf" in node:
        return _union_kinds(node["oneOf"])
    if "const" in node:
        return {_kind(node["const"])}
    if isinstance(node.get("enum"), list):
        return {_kind(item) for item in node["enum"]}
    names = _type_names(node)
    if not names:
        return None
    if "integer" in names:
        return names | {"number"}
    return names


def _union_kinds(branches: list[Any]) -> set[str] | None:
    kinds: set[str] = set()
    for branch in branches:
        if not isinstance(branch, dict):
            return None
        found = _allowed_kinds(branch)
        if found is None:
            return None
        kinds |= found
    return kinds or None


def _locally_rejected(node: Schema, value: Any) -> bool:
    """True only when the old node itself cannot accept `value`."""
    if not node:
        return False
    return _failed_scalar(node, value) or _outside_range(node, value)


def _failed_scalar(node: Schema, value: Any) -> bool:
    if "const" in node and not _json_equal(value, node["const"]):
        return True
    enum = node.get("enum")
    if isinstance(enum, list) and not any(_json_equal(value, item) for item in enum):
        return True
    allowed = _allowed_kinds(node)
    if allowed is not None and _kind(value) not in allowed:
        return True
    return "integer" in _type_names(node) and type(value) is not int


def _outside_range(node: Schema, value: Any) -> bool:
    if _kind(value) == "number":
        return _outside_number(node, value)
    if isinstance(value, str):
        return _outside_length(node, value)
    return False


def _outside_number(node: Schema, value: int | float) -> bool:
    if "minimum" in node and value < node["minimum"]:
        return True
    if "maximum" in node and value > node["maximum"]:
        return True
    if "exclusiveMinimum" in node and value <= node["exclusiveMinimum"]:
        return True
    return "exclusiveMaximum" in node and value >= node["exclusiveMaximum"]


def _outside_length(node: Schema, value: str) -> bool:
    if "minLength" in node and len(value) < node["minLength"]:
        return True
    return "maxLength" in node and len(value) > node["maxLength"]


def _edges(node: Schema) -> Iterator[Any]:
    if "const" in node:
        yield node["const"]
    yield from node.get("enum", [])
    for key in _BOUNDS:
        if key in node:
            yield from (node[key] + step for step in _STEPS)
    for key in _LENGTHS:
        if key in node:
            yield from ("a" * max(node[key] + step, 0) for step in (-1, 0, 1))
    if "pattern" in node:
        try:
            yield _automaton.shortest(node["pattern"])
        except _automaton.Undecided:
            return


def _local_edges(node: Schema) -> Iterator[Any]:
    yield from _edges(node)
    if node.get("format") == "date":
        yield DATE


def _novel(old: Schema, values: list[Any]) -> list[Any]:
    """Values the new schema or a pattern proof names, skipping edges the old schema already has.

    Trying every old string in every old field validates hundreds of unchanged documents. A break
    uses another edge of the same node, or a value the new schema introduced.
    """
    known = {_key(value) for value in (*SIMPLEST, DATE)}
    for node in walk(old):
        for edge in _edges(node):
            known.add(_key(edge))
    return [value for value in values if _key(value) not in known]


def _replacement_values(node: Schema, values: list[Any], novel: list[Any]) -> list[Any]:
    if not node:
        return values
    unique: dict[str, Any] = {}
    for value in (*_local_edges(node), *novel):
        if not _locally_rejected(node, value):
            unique.setdefault(_key(value), value)
    return list(unique.values())


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
        if name not in value or not _json_equal(value[name], prop["const"]):
            return False
        matched = True
    return matched


def _branch_for(node: Schema, value: Any) -> Schema:
    branches = [branch for branch in node.get("oneOf", []) if isinstance(branch, dict)]
    for branch in branches:
        if _consts_fit(branch, value):
            return branch
    for branch in branches:
        allowed = _allowed_kinds(branch)
        if allowed is None or _kind(value) in allowed:
            return branch
    return branches[0] if branches else node


def _bind(root: Schema, instance: Any) -> dict[Path, Schema]:
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


def _missing_names(node: Schema, obj: dict[str, Any], names: list[str]) -> list[str]:
    extra = node.get("additionalProperties")
    if extra is True or isinstance(extra, dict):
        return [name for name in names if name not in obj]
    props = node.get("properties", {})
    return [name for name in sorted(props) if name not in obj and isinstance(props[name], dict)]


def _prop_schema(node: Schema, name: str) -> Schema:
    props = node.get("properties", {})
    if isinstance(props.get(name), dict):
        return props[name]
    extra = _extra_schema(node.get("additionalProperties"))
    return extra or {}
