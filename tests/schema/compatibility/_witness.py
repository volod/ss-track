"""Find and shrink counterexamples deterministically; only the strict validator confirms one.

A seed is the smallest instance the old schema states: required properties only, the first enum
value, a bound's own edge. `search` builds one seed for each combination of `oneOf` branches it
walks, then tries one position and then pairs of positions. A position takes an edge of its own
node, or a value the new schema introduced, or a property the object allows. The search stops
after a fixed number of validator calls.

`_witness_build` writes the seeds, `_witness_node` decides which values a node can accept,
`_witness_bind` finds the node a value sits under, and `_witness_shrink` simplifies a witness.
"""

from collections.abc import Iterable, Iterator
from itertools import combinations
from typing import Any

from ss_track.schema.registry.fingerprints import walk
from tests.schema.compatibility._witness_bind import bind_path, missing_names, property_schema
from tests.schema.compatibility._witness_build import combined_seeds, try_build
from tests.schema.compatibility._witness_document import NONE, Holds, at, paths, replaced
from tests.schema.compatibility._witness_node import (
    DATE,
    SCALARS,
    SIMPLEST,
    Path,
    Schema,
    json_equal,
    json_key,
    local_edges,
    locally_rejected,
    node_edges,
    novel_values,
    replacement_values,
    value_kind,
)

MAX_TRIALS = 4096
# Real transitions spend this whole budget on documents that stay valid. The coordinated
# table is found within the first few calls, so the cap stays small.
PAIR_BUDGET = 32
PAIR_VALUES = 6


def boundary_values(schemas: list[Schema], strings: list[str]) -> list[Any]:
    """Return every edge value the schemas name, simplest first and without repeats."""
    unique: dict[str, Any] = {}
    edges = (edge for schema in schemas for node in walk(schema) for edge in node_edges(node))
    for value in (*SIMPLEST, DATE, *strings, *edges):
        unique.setdefault(json_key(value), value)
    return list(unique.values())


def property_names(schemas: list[Schema]) -> list[str]:
    """Return every property name the schemas state, for insertion into open objects."""
    return sorted(
        {name for schema in schemas for node in walk(schema) for name in node.get("properties", {})}
    )


def _candidates(root: Schema, prop: Schema, values: list[Any], novel: list[Any]) -> list[Any]:
    if not prop:
        sequence: Iterable[Any] = values
    else:
        built = try_build(root, prop, NONE)
        sequence = local_edges(prop) if built is NONE else (built, *local_edges(prop))
        sequence = (*sequence, *novel)
    unique: dict[str, Any] = {}
    for value in sequence:
        if not locally_rejected(prop, value):
            unique.setdefault(json_key(value), value)
    return list(unique.values())


def _one_change(seed: Any, names: list[str], values: list[Any]) -> Iterator[Any]:
    for path in paths(seed):
        current = at(seed, path)
        for value in values:
            yield replaced(seed, path, value)
        if isinstance(current, dict):
            for name in names:
                if name not in current:
                    yield from (replaced(seed, path, current | {name: value}) for value in values)


def _singles(
    root: Schema, seed: Any, names: list[str], values: list[Any], novel: list[Any]
) -> Iterator[Any]:
    indexed = bind_path(root, seed)
    for path in paths(seed):
        current = at(seed, path)
        node = indexed.get(path, {})
        for value in replacement_values(node, values, novel):
            if not json_equal(value, current):
                yield replaced(seed, path, value)
        if isinstance(current, dict):
            yield from _insertions(root, seed, path, current, node, names, values, novel)


def _insertions(
    root: Schema,
    seed: Any,
    path: Path,
    current: dict[str, Any],
    node: Schema,
    names: list[str],
    values: list[Any],
    novel: list[Any],
) -> Iterator[Any]:
    for name in missing_names(node, current, names):
        for value in _candidates(root, property_schema(node, name), values, novel):
            yield replaced(seed, path, current | {name: value})


def _pair_trials(
    root: Schema, seed: Any, names: list[str], values: list[Any], novel: list[Any]
) -> Iterator[Any]:
    yield from _insertion_pairs(root, seed, names, values, novel)
    indexed = bind_path(root, seed)
    scalars = [path for path in paths(seed) if value_kind(at(seed, path)) in SCALARS]
    yield from _replacement_pairs(seed, indexed, scalars, values, novel, cross=False)
    yield from _replacement_pairs(seed, indexed, scalars, values, novel, cross=True)


def _insertion_pairs(
    root: Schema, seed: Any, names: list[str], values: list[Any], novel: list[Any]
) -> Iterator[Any]:
    indexed = bind_path(root, seed)
    for path in paths(seed):
        current = at(seed, path)
        if not isinstance(current, dict):
            continue
        node = indexed.get(path, {})
        missing = missing_names(node, current, names)
        options = {
            name: _candidates(root, property_schema(node, name), values, novel)[:PAIR_VALUES]
            for name in missing
        }
        for left, right in combinations(missing, 2):
            for first in options[left]:
                for second in options[right]:
                    yield replaced(seed, path, current | {left: first, right: second})


def _replacement_pairs(
    seed: Any,
    indexed: dict[Path, Schema],
    scalars: list[Path],
    values: list[Any],
    novel: list[Any],
    *,
    cross: bool,
) -> Iterator[Any]:
    for left, right in _scalar_pairs(scalars, cross=cross):
        left_values = _changing(indexed.get(left, {}), at(seed, left), values, novel)
        right_values = _changing(indexed.get(right, {}), at(seed, right), values, novel)
        for first in left_values:
            for second in right_values:
                yield replaced(replaced(seed, left, first), right, second)


def _scalar_pairs(scalars: list[Path], *, cross: bool) -> Iterator[tuple[Path, Path]]:
    if cross:
        yield from (
            (left, right) for left, right in combinations(scalars, 2) if left[:-1] != right[:-1]
        )
        return
    grouped: dict[Path, list[Path]] = {}
    for path in scalars:
        grouped.setdefault(path[:-1], []).append(path)
    for group in grouped.values():
        yield from combinations(group, 2)


def _changing(node: Schema, current: Any, values: list[Any], novel: list[Any]) -> list[Any]:
    found = [
        value for value in replacement_values(node, values, novel) if not json_equal(value, current)
    ]
    return found[:PAIR_VALUES]


class _Budget:
    def __init__(self, holds: Holds, limit: int) -> None:
        self._holds = holds
        self.limit = limit
        self.used = 0
        self.seen: set[str] = set()

    def exhausted(self) -> bool:
        return self.used >= self.limit

    def accepts(self, value: Any) -> bool:
        if self.exhausted():
            return False
        key = json_key(value)
        if key in self.seen:
            return False
        self.seen.add(key)
        self.used += 1
        return self._holds(value)


def _first(budget: _Budget, groups: Iterable[Iterable[Any]]) -> Any:
    for group in groups:
        for trial in group:
            if budget.exhausted():
                return NONE
            if budget.accepts(trial):
                return trial
    return NONE


def search(old: Schema, names: list[str], values: list[Any], holds: Holds) -> Any:
    """Return a confirmed witness, or `NONE` once the trial bounds are spent."""
    budget = _Budget(holds, MAX_TRIALS)
    seeds = combined_seeds(old)
    novel = novel_values(old, values)
    found = _first(budget, [seeds])
    if found is not NONE:
        return found
    found = _first(budget, (_singles(old, seed, names, values, novel) for seed in seeds))
    if found is not NONE or budget.exhausted():
        return found if found is not NONE else NONE
    pairs = _Budget(holds, PAIR_BUDGET)
    pairs.seen = budget.seen
    return _first(pairs, (_pair_trials(old, seed, names, values, novel) for seed in seeds))
