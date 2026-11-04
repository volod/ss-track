"""Smallest instances of a schema, including each combination of oneOf branches."""

import copy
import math
from collections.abc import Iterator
from typing import Any

from ss_track.schema.fingerprints import walk
from tests.schema import _automaton
from tests.schema._witness_node import DATE, Schema, _key

MAX_DEPTH = 32
MAX_SEEDS = 32


class _NoExample(Exception):
    """The schema states no finite instance this builder can write."""


class _NeedChoice(Exception):
    """A oneOf was reached with no branch chosen yet."""

    def __init__(self, width: int) -> None:
        self.width = width
        super().__init__(width)


class _Builder:
    def __init__(self, root: Schema, choice: tuple[int, ...] | int) -> None:
        self.root = root
        self.choice = choice
        self.index = 0

    def build(self, node: Schema, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise _NoExample("recursion")
        if "$ref" in node:
            return self.build(self.root["$defs"][node["$ref"].rsplit("/", 1)[-1]], depth + 1)
        if "const" in node:
            return copy.deepcopy(node["const"])
        if "enum" in node:
            return copy.deepcopy(node["enum"][0])
        if "oneOf" in node:
            return self._one_of(node, depth)
        kind = _first_type(node.get("type", "null"))
        if kind == "object":
            required = sorted(node.get("required", []))
            return {name: self.build(node["properties"][name], depth + 1) for name in required}
        if kind == "array":
            return self.array(node, depth)
        return _scalar(kind, node)

    def _one_of(self, node: Schema, depth: int) -> Any:
        branches = [branch for branch in node["oneOf"] if isinstance(branch, dict)]
        if not branches:
            raise _NoExample("empty oneOf")
        return self.build(branches[self._pick(len(branches))], depth + 1)

    def array(self, node: Schema, depth: int) -> list[Any]:
        result = [self.build(item, depth + 1) for item in node.get("prefixItems", [])]
        missing = node.get("minItems", 0) - len(result)
        if missing > 0:
            if not isinstance(node.get("items"), dict):
                raise _NoExample("array needs items")
            result += [self.build(node["items"], depth + 1) for _ in range(missing)]
        return result

    def _pick(self, width: int) -> int:
        if isinstance(self.choice, int):
            return self.choice % width
        if self.index >= len(self.choice):
            raise _NeedChoice(width)
        pick = self.choice[self.index]
        self.index += 1
        if pick < 0 or pick >= width:
            raise _NoExample("choice")
        return pick


def _first_type(kinds: str | list[str]) -> str:
    if isinstance(kinds, str):
        return kinds
    return next((name for name in kinds if name != "null"), "null")


def _scalar(kind: str, node: Schema) -> Any:
    if kind == "string":
        if node.get("format") == "date":
            return DATE
        if "pattern" in node:
            return _automaton.shortest(node["pattern"], node.get("minLength", 0))
        return "a" * node.get("minLength", 0)
    if kind in ("number", "integer"):
        if "minimum" in node:
            low = node["minimum"]
        elif "exclusiveMinimum" in node:
            low = node["exclusiveMinimum"] + 1
        else:
            low = min(0, node.get("maximum", 0), node.get("exclusiveMaximum", 1) - 1)
        return math.ceil(low) if kind == "integer" else low
    return False if kind == "boolean" else None


def _try_build(root: Schema, node: Schema, none: object) -> Any:
    if not node:
        return none
    chosen: tuple[int, ...] = ()
    for _ in range(MAX_DEPTH):
        try:
            return _Builder(root, chosen).build(node)
        except _NeedChoice:
            chosen = (*chosen, 0)
        except (_NoExample, _automaton.Undecided):
            return none
    return none


def _combined_seeds(old: Schema) -> list[Any]:
    """One minimal instance per oneOf combination, schema order, capped."""
    found: list[Any] = []
    seen: set[str] = set()
    pending: list[tuple[int, ...]] = [()]
    while pending and len(found) < MAX_SEEDS:
        chosen = pending.pop()
        try:
            instance = _Builder(old, chosen).build(old)
        except _NeedChoice as need:
            _schedule(pending, chosen, need.width)
            continue
        except (_NoExample, _automaton.Undecided):
            continue
        if (key := _key(instance)) not in seen:
            seen.add(key)
            found.append(instance)
    return found


def _schedule(pending: list[tuple[int, ...]], chosen: tuple[int, ...], width: int) -> None:
    if len(chosen) >= MAX_DEPTH:
        return
    for index in range(width - 1, -1, -1):
        pending.append((*chosen, index))


def _diagonal_seeds(old: Schema) -> Iterator[Any]:
    widths = [len(node["oneOf"]) for node in walk(old) if "oneOf" in node]
    for choice in range(max(widths, default=1)):
        try:
            yield _Builder(old, choice).build(old)
        except (_NoExample, _NeedChoice, _automaton.Undecided):
            continue
