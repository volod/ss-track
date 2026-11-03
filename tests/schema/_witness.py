"""Find and shrink counterexamples deterministically; only the strict validator confirms one.

A seed is the smallest instance the old schema states: required properties only, the first enum
value, a bound's own edge. Every position of every seed then takes each boundary value either
schema names: its constants, its numeric bounds and their neighbors, strings at its length bounds,
and the strings `_automaton` found inside one pattern and outside another. Each object position
also takes every property name either schema states, with each of those values.
"""

import copy
import json
import math
from collections.abc import Callable, Iterator
from typing import Any

from ss_track.schema.fingerprints import walk
from tests.schema import _automaton

type Schema = dict[str, Any]
type Holds = Callable[[Any], bool]

NONE = object()
SIMPLEST: tuple[Any, ...] = (0, "", False, None, [], {})
DATE = "2000-01-01"
MAX_DEPTH = 32
_BOUNDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
_LENGTHS = ("minLength", "maxLength")
_STEPS = (-1, -0.5, 0, 0.5, 1)


class _NoExample(Exception):
    """The schema states no finite instance this builder can write."""


def paths(value: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
    """Yield every position in a JSON value, outermost first."""
    yield path
    if isinstance(value, dict):
        items: Iterator[tuple[Any, Any]] = iter(value.items())
    else:
        items = enumerate(value) if isinstance(value, list) else iter(())
    for key, item in items:
        yield from paths(item, (*path, key))


def at(document: Any, path: tuple[Any, ...]) -> Any:
    for key in path:
        document = document[key]
    return document


def replaced(document: Any, path: tuple[Any, ...], value: Any) -> Any:
    """Return a copy of `document` with `value` at `path`."""
    if not path:
        return value
    result = copy.copy(document)
    result[path[0]] = replaced(document[path[0]], path[1:], value)
    return result


class _Builder:
    def __init__(self, root: Schema, choice: int) -> None:
        self.root, self.choice = root, choice

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
            branches = node["oneOf"]
            return self.build(branches[self.choice % len(branches)], depth + 1)
        kind = _first_type(node.get("type", "null"))
        if kind == "object":
            required = sorted(node.get("required", []))
            return {name: self.build(node["properties"][name], depth + 1) for name in required}
        if kind == "array":
            return self.array(node, depth)
        return _scalar(kind, node)

    def array(self, node: Schema, depth: int) -> list[Any]:
        result = [self.build(item, depth + 1) for item in node.get("prefixItems", [])]
        missing = node.get("minItems", 0) - len(result)
        if missing > 0:
            if not isinstance(node.get("items"), dict):
                raise _NoExample("array needs items")
            result += [self.build(node["items"], depth + 1) for _ in range(missing)]
        return result


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


def boundary_values(schemas: list[Schema], strings: list[str]) -> list[Any]:
    """Return every edge value the schemas name, simplest first and without repeats."""
    unique: dict[str, Any] = {}
    edges = (edge for schema in schemas for node in walk(schema) for edge in _edges(node))
    for value in (*SIMPLEST, DATE, *strings, *edges):
        unique.setdefault(json.dumps(value, sort_keys=True), value)
    return list(unique.values())


def _seeds(old: Schema) -> Iterator[Any]:
    widths = [len(node["oneOf"]) for node in walk(old) if "oneOf" in node]
    for choice in range(max(widths, default=1)):
        try:
            yield _Builder(old, choice).build(old)
        except (_NoExample, _automaton.Undecided):
            continue


def property_names(schemas: list[Schema]) -> list[str]:
    """Return every property name the schemas state, for insertion into open objects."""
    return sorted(
        {name for schema in schemas for node in walk(schema) for name in node.get("properties", {})}
    )


def _variants(seed: Any, names: list[str], values: list[Any]) -> Iterator[Any]:
    for path in paths(seed):
        current = at(seed, path)
        for value in values:
            yield replaced(seed, path, value)
        if isinstance(current, dict):
            for name in names:
                if name not in current:
                    yield from (replaced(seed, path, current | {name: value}) for value in values)


def search(old: Schema, names: list[str], values: list[Any], holds: Holds) -> Any:
    """Return a confirmed witness varied from the old schema's seeds, or `NONE`."""
    for seed in _seeds(old):
        for trial in _variants(seed, names, values):
            if holds(trial):
                return trial
    return NONE


def _simpler(value: Any) -> Iterator[Any]:
    yield from SIMPLEST
    if isinstance(value, str | list):
        for index in range(len(value)):
            yield value[:index] + value[index + 1 :]
    if isinstance(value, dict):
        yield from value.values()
        for key in value:
            yield {name: item for name, item in value.items() if name != key}
    if isinstance(value, list):
        yield from value


def _size(value: Any) -> int:
    return len(json.dumps(value))


def _smaller(document: Any, holds: Holds) -> Any:
    for path in paths(document):
        current = at(document, path)
        for candidate in _simpler(current):
            if _size(candidate) < _size(current):
                trial = replaced(document, path, candidate)
                if holds(trial):
                    return trial
    return NONE


def shrunk(document: Any, holds: Holds) -> Any:
    """Shrink a witness until no single value can become simpler, so it names one fact."""
    while (smaller := _smaller(document, holds)) is not NONE:
        document = smaller
    return document
