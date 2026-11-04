"""An independent structural oracle; its disagreements are errors, never policy overrides.

It reads no classifier rule. Both schemas lose their meaning keywords and have references inlined,
with a recursive target kept once under `$defs`. Then two sound rewrites run, aligned by position:

- an open object in the old schema states each property the new one adds as any JSON value, which
  accepts exactly what it did, so jsoncompat 0.5.0 compares that property instead of passing it;
- a new pattern that `_automaton` proves admits the old one is replaced by the old one, which can
  only narrow the new schema, so a compatible verdict still holds for the original.

jsoncompat then decides. A counterexample counts only after the local strict validator accepts it
under the original old schema and refuses it under the new; it is shrunk to its simplest values.
When jsoncompat finds none, `_witness` searches. It builds one seed per `oneOf` combination and
tries one position, then pairs of positions, using each node's own edges and values the new schema
introduced. A bound on validator calls keeps a compatible transition cheap. An unknown verdict with
no witness, an unconfirmed counterexample or an undecided pattern raises `Undecided`.
"""

import copy
import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import jsoncompat
from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from ss_track.schema.evolution import diff_schemas, required_bump
from ss_track.schema.strict import StrictValidator, branch_tags
from tests.schema import _automaton, _witness

type Schema = dict[str, Any]

ANY_VALUE = {"type": ["null", "boolean", "object", "array", "number", "string"]}
FORMATS = Draft202012Validator.FORMAT_CHECKER
_DROPPED = {"$id", "$schema", "$defs", "description", "title", "examples"}
_ROLE = "deserializer"


class Undecided(Exception):
    """The oracle cannot decide this pair; a disagreement would be a guess."""


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether every old value is new-valid, the confirmed witness if not, and the proofs used."""

    compatible: bool
    witness: Any = None
    proofs: tuple[str, ...] = ()


def _target(node: Schema, resolver: Any) -> tuple[Schema, Any, str]:
    """Follow a chain of references to the schema it names and the last reference text."""
    seen: set[int] = set()
    reference = ""
    while "$ref" in node:
        if id(node) in seen:
            raise Undecided(f"cyclic reference alias: {node['$ref']}")
        seen.add(id(node))
        reference = node["$ref"]
        found = resolver.lookup(reference)
        node, resolver = found.contents, found.resolver
    return node, resolver, reference


class _Expander:
    """Inline references, keeping a target reached again inside itself once under `$defs`."""

    def __init__(self) -> None:
        self.hoisted: dict[str, Schema] = {}
        self.names: dict[int, str] = {}
        self.active: set[int] = set()

    def local(self, key: int, reference: str) -> Schema:
        if key not in self.names:
            base = reference.rsplit("/", 1)[-1]
            taken = base in self.names.values()
            self.names[key] = f"{base}-{len(self.names)}" if taken else base
        return {"$ref": "#/$defs/" + self.names[key]}

    def expand(self, node: Schema, resolver: Any) -> Schema:
        if "$ref" not in node:
            return self.plain(node, resolver)
        found, scope, reference = _target(node, resolver)
        key = id(found)
        if key in self.active:
            return self.local(key, reference)
        self.active.add(key)
        result = self.plain(found, scope)
        self.active.discard(key)
        if key not in self.names:
            return result
        self.hoisted[self.names[key]] = result
        return self.local(key, reference)

    def plain(self, node: Schema, resolver: Any) -> Schema:
        result = {
            key: copy.deepcopy(value)
            for key, value in node.items()
            if key not in _DROPPED and not key.startswith("x-")
        }
        if "properties" in result:
            named = node["properties"].items()
            result["properties"] = {key: self.expand(value, resolver) for key, value in named}
        if isinstance(result.get("items"), dict):
            result["items"] = self.expand(node["items"], resolver)
        for keyword in ("prefixItems", "oneOf"):
            if keyword in result:
                result[keyword] = [self.expand(item, resolver) for item in node[keyword]]
        return result


def _expanded(schema: Schema, registry: Registry[Any]) -> Schema:
    expander = _Expander()
    resolver = registry.resolver_with_root(DRAFT202012.create_resource(schema))
    root = expander.expand(schema, resolver)
    return root | {"$defs": expander.hoisted} if expander.hoisted else root


def _pairs(old: Schema, new: Schema) -> Iterator[tuple[Schema, Schema]]:
    """Yield the schemas at the same position in both trees, outermost first."""
    yield old, new
    for keyword in ("properties", "$defs"):
        before, after = old.get(keyword, {}), new.get(keyword, {})
        for key in sorted(before.keys() & after.keys()):
            yield from _pairs(before[key], after[key])
    if isinstance(old.get("items"), dict) and isinstance(new.get("items"), dict):
        yield from _pairs(old["items"], new["items"])
    for before, after in zip(old.get("prefixItems", []), new.get("prefixItems", []), strict=False):
        yield from _pairs(before, after)
    tagged = {_tag(branch): branch for branch in old.get("oneOf", [])}
    for branch in new.get("oneOf", []):
        if _tag(branch) in tagged:
            yield from _pairs(tagged[_tag(branch)], branch)


def _tag(branch: Schema) -> str:
    return json.dumps(branch_tags(branch), sort_keys=True)


def _declare_open(old: Schema, new: Schema) -> None:
    """State each property the new schema adds as any value, which an open object already took."""
    if old.get("additionalProperties") is not True:
        return
    stated = old.setdefault("properties", {})
    for key in new.get("properties", {}).keys() - stated.keys():
        stated[key] = copy.deepcopy(ANY_VALUE)


def _narrow_pattern(old: Schema, new: Schema, proofs: list[str], strings: list[str]) -> None:
    """Give the new schema the old pattern when the automaton proves the new one admits it."""
    if "pattern" not in old or "pattern" not in new or old["pattern"] == new["pattern"]:
        return
    try:
        inclusion = _automaton.inclusion(old["pattern"], new["pattern"])
    except _automaton.Undecided as error:
        raise Undecided(f"pattern {old['pattern']} to {new['pattern']}: {error}") from error
    if inclusion.witness is not None:
        strings.append(inclusion.witness)
    if inclusion.holds:
        proofs.append(f"{old['pattern']} within {new['pattern']}")
        new["pattern"] = old["pattern"]


def _rewritten(old: Schema, new: Schema) -> tuple[Schema, Schema, tuple[str, ...], list[str]]:
    """Return the rewritten pair, the pattern proofs used and the strings that broke one."""
    old, new = copy.deepcopy(old), copy.deepcopy(new)
    proofs: list[str] = []
    strings: list[str] = []
    for before, after in _pairs(old, new):
        _declare_open(before, after)
        _narrow_pattern(before, after, proofs, strings)
    return old, new, tuple(proofs), strings


def verdict(old: Schema, new: Schema, registry: Registry[Any] | None = None) -> Verdict:
    """Decide whether every value `old` accepts is accepted by `new`, or raise `Undecided`."""
    resources = registry if registry is not None else Registry()
    expanded = _expanded(old, resources), _expanded(new, resources)
    before, after, proofs, strings = _rewritten(*expanded)
    found = jsoncompat.analyze_compat(json.dumps(before), json.dumps(after), _ROLE)
    accepts, refuses = (
        StrictValidator(schema, registry=resources, format_checker=FORMATS) for schema in (old, new)
    )

    def holds(value: Any) -> bool:
        return accepts.is_valid(value) and not refuses.is_valid(value)

    if found["status"] == "incompatible":
        witness = found["counterexample"]
        if not holds(witness):
            raise Undecided(f"counterexample not confirmed: {found['counterexample_json']}")
    else:
        names = _witness.property_names(list(expanded))
        values = _witness.boundary_values(list(expanded), strings)
        witness = _witness.search(expanded[0], names, values, holds)
    if witness is not _witness.NONE:
        return Verdict(False, _witness.shrunk(witness, holds), proofs)
    if found["status"] == "compatible":
        return Verdict(True, proofs=proofs)
    raise Undecided(found["reason"])


def require_oracle_agreement(
    old: Schema, new: Schema, registry: Registry[Any] | None = None
) -> Verdict:
    """Fail unless the classifier's backward verdict on the stripped pair is the oracle's."""
    resources = registry if registry is not None else Registry()
    expected = (
        required_bump(diff_schemas(_expanded(old, resources), _expanded(new, resources))) != "major"
    )
    found = verdict(old, new, resources)
    assert found.compatible == expected, (
        f"oracle disagreement: classifier backward={expected}, oracle={found.compatible}, "
        f"witness={json.dumps(found.witness)}, proofs={list(found.proofs)}"
    )
    return found
