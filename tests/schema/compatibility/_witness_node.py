"""Which values an old schema node can accept, and where a value sits in that schema.

The search uses this instead of validating every string named anywhere in the document. A value the
node itself rejects can never be a witness, so it is not worth a validator call.
"""

import json
from collections.abc import Iterator
from typing import Any

from ss_track.schema.registry.fingerprints import walk
from tests.schema.compatibility import _automaton

type Schema = dict[str, Any]
type Path = tuple[Any, ...]

SIMPLEST: tuple[Any, ...] = (0, "", False, None, [], {})
DATE = "2000-01-01"
_BOUNDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
_LENGTHS = ("minLength", "maxLength")
_STEPS = (-1, -0.5, 0, 0.5, 1)
SCALARS = ("null", "boolean", "number", "string")


def json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def json_equal(left: Any, right: Any) -> bool:
    return json_key(left) == json_key(right)


def value_kind(value: Any) -> str:
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


def allowed_kinds(node: Schema) -> set[str] | None:
    """Kinds this node can accept, or none when a local reading would be a guess."""
    if "oneOf" in node:
        return _union_kinds(node["oneOf"])
    if "const" in node:
        return {value_kind(node["const"])}
    if isinstance(node.get("enum"), list):
        return {value_kind(item) for item in node["enum"]}
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
        found = allowed_kinds(branch)
        if found is None:
            return None
        kinds |= found
    return kinds or None


def locally_rejected(node: Schema, value: Any) -> bool:
    """True only when the old node itself cannot accept `value`."""
    if not node:
        return False
    return _failed_scalar(node, value) or _outside_range(node, value)


def _failed_scalar(node: Schema, value: Any) -> bool:
    if "const" in node and not json_equal(value, node["const"]):
        return True
    enum = node.get("enum")
    if isinstance(enum, list) and not any(json_equal(value, item) for item in enum):
        return True
    allowed = allowed_kinds(node)
    if allowed is not None and value_kind(value) not in allowed:
        return True
    return "integer" in _type_names(node) and type(value) is not int


def _outside_range(node: Schema, value: Any) -> bool:
    if value_kind(value) == "number":
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


def node_edges(node: Schema) -> Iterator[Any]:
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


def local_edges(node: Schema) -> Iterator[Any]:
    yield from node_edges(node)
    if node.get("format") == "date":
        yield DATE


def novel_values(old: Schema, values: list[Any]) -> list[Any]:
    """Values the new schema or a pattern proof names, skipping edges the old schema already has.

    Trying every old string in every old field validates hundreds of unchanged documents. A break
    uses another edge of the same node, or a value the new schema introduced.
    """
    known = {json_key(value) for value in (*SIMPLEST, DATE)}
    for node in walk(old):
        for edge in node_edges(node):
            known.add(json_key(edge))
    return [value for value in values if json_key(value) not in known]


def replacement_values(node: Schema, values: list[Any], novel: list[Any]) -> list[Any]:
    if not node:
        return values
    unique: dict[str, Any] = {}
    for value in (*local_edges(node), *novel):
        if not locally_rejected(node, value):
            unique.setdefault(json_key(value), value)
    return list(unique.values())
