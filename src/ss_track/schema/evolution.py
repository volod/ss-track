"""Explain every schema change at its JSON pointer, including resolved reference targets."""

import json
from dataclasses import dataclass
from typing import Any

from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from ss_track.refusal import JsonValue
from ss_track.schema._change_rules import MAJOR, MEANING, MINOR, RANK, keyword_class
from ss_track.schema.dialect import _tags
from ss_track.schema.store import damaged
from ss_track.schema.strict import Schema

_CHILDREN = {"properties", "$defs", "items", "prefixItems", "oneOf", "required"}
_IDENTITY = {"$id", "$schema"}


def pointer(path: str, part: str | int) -> str:
    """Append an escaped JSON pointer segment."""
    return path + "/" + str(part).replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True, slots=True)
class Change:
    """One field-level explanation; semantic changes are forbidden within a major."""

    pointer: str
    bump: str
    reason: str

    def to_record(self) -> dict[str, JsonValue]:
        return {"pointer": self.pointer, "class": self.bump, "reason": self.reason}


def required_bump(changes: list[Change]) -> str:
    """Return the smallest permitted bump, or none for equivalent schemas."""
    return max((change.bump for change in changes), key=RANK.__getitem__, default="none")


def _resolved(node: Schema, resolver: Any) -> tuple[Schema, Any]:
    seen: set[int] = set()
    annotations: Schema = {}
    while "$ref" in node:
        reference = node["$ref"]
        if id(node) in seen:
            raise damaged(f"cyclic reference alias: {reference}")
        seen.add(id(node))
        annotations = {key: value for key, value in node.items() if key != "$ref"} | annotations
        try:
            resolved = resolver.lookup(reference)
        except Unresolvable as error:
            raise damaged(f"unresolved evolution reference: {reference}") from error
        node, resolver = resolved.contents, resolved.resolver
    return node | annotations, resolver


def _scalars(old: Schema, new: Schema, path: str) -> list[Change]:
    changes = []
    for key in sorted((old.keys() | new.keys()) - _CHILDREN - _IDENTITY):
        if (
            key in old
            and key in new
            and json.dumps(old[key], sort_keys=True) == json.dumps(new[key], sort_keys=True)
        ):
            continue
        bump = keyword_class(key, old, new)
        reason = f"{key} changed"
        if key in MEANING and key in old:
            reason += "; forbidden within a major: add a property or take a major"
        changes.append(Change(pointer(path, key), bump, reason))
    required_old, required_new = set(old.get("required", [])), set(new.get("required", []))
    for name in sorted(required_old ^ required_new):
        added = name in required_new
        changes.append(
            Change(
                pointer(pointer(path, "properties"), name),
                MAJOR if added else MINOR,
                "property became required" if added else "property became optional",
            )
        )
    return changes


def _branch_maps(
    before: list[Schema], after: list[Schema]
) -> tuple[dict[str, tuple[int, Schema]], dict[str, tuple[int, Schema]]] | None:
    if not before or not after:
        return None
    tags = [_tags(branch) for branch in before + after]
    shared = set(tags[0]).intersection(*tags[1:])
    for tag in sorted(shared):
        maps = [
            {
                json.dumps(branch["properties"][tag]["const"], sort_keys=True): (i, branch)
                for i, branch in enumerate(branches)
            }
            for branches in (before, after)
        ]
        if len(maps[0]) == len(before) and len(maps[1]) == len(after):
            return maps[0], maps[1]
    return None


@dataclass
class _Walker:
    changes: list[Change]
    active: set[tuple[int, int]]

    def compare(self, old: Schema, new: Schema, path: str, left: Any, right: Any) -> None:
        # Stop recursive shape pairs, while revisiting the same definition at distinct use sites.
        pair = (id(old), id(new))
        referenced = "$ref" in old or "$ref" in new
        if referenced and pair in self.active:
            return
        if referenced:
            self.active.add(pair)
        before, left = _resolved(old, left)
        after, right = _resolved(new, right)
        self.changes += _scalars(before, after, path)
        for keyword in ("properties", "$defs"):
            self.named(before, after, path, keyword, left, right)
        self.arrays(before, after, path, left, right)
        self.branches(before, after, path, left, right)
        if referenced:
            self.active.remove(pair)

    def named(self, old: Schema, new: Schema, path: str, key: str, left: Any, right: Any) -> None:
        before, after = old.get(key, {}), new.get(key, {})
        for name in sorted(before.keys() | after.keys()):
            location = pointer(pointer(path, key), name)
            if name in before and name in after:
                self.compare(before[name], after[name], location, left, right)
            elif name not in after:
                self.changes.append(Change(location, MAJOR, f"{key} entry removed"))
            else:
                required = name in new.get("required", [])
                # An optional constraint on an open object still rejects previously legal values.
                constrained_open = key == "properties" and old.get("additionalProperties") is True
                bump = MAJOR if required or constrained_open else MINOR
                self.changes.append(Change(location, bump, f"{key} entry added"))

    def arrays(self, old: Schema, new: Schema, path: str, left: Any, right: Any) -> None:
        before, after = old.get("items"), new.get("items")
        if isinstance(before, dict) and isinstance(after, dict):
            self.compare(before, after, pointer(path, "items"), left, right)
        elif before != after:
            self.changes.append(Change(pointer(path, "items"), MAJOR, "array items changed"))
        old_items, new_items = old.get("prefixItems", []), new.get("prefixItems", [])
        for index in range(max(len(old_items), len(new_items))):
            location = pointer(pointer(path, "prefixItems"), index)
            if index < min(len(old_items), len(new_items)):
                self.compare(old_items[index], new_items[index], location, left, right)
            else:
                self.changes.append(
                    Change(location, MAJOR, "fixed tuple position added or removed")
                )

    def branches(self, old: Schema, new: Schema, path: str, left: Any, right: Any) -> None:
        before, after = old.get("oneOf", []), new.get("oneOf", [])
        if not before and not after:
            return
        paired = _branch_maps(before, after)
        if paired is None:
            self.changes.append(Change(pointer(path, "oneOf"), MAJOR, "tagged union shape changed"))
            return
        old_map, new_map = paired
        for value in sorted(old_map.keys() | new_map.keys()):
            if value in old_map and value in new_map:
                index, branch = new_map[value]
                self.compare(
                    old_map[value][1], branch, pointer(pointer(path, "oneOf"), index), left, right
                )
            else:
                added = value in new_map
                index = (new_map if added else old_map)[value][0]
                self.changes.append(
                    Change(
                        pointer(pointer(path, "oneOf"), index),
                        MINOR if added else MAJOR,
                        "tagged branch added" if added else "tagged branch removed",
                    )
                )


def diff_schemas(old: Schema, new: Schema, registry: Registry[Any] | None = None) -> list[Change]:
    """Compare two dialect-validated schemas; resolve only local, explicitly supplied resources."""
    resources = registry if registry is not None else Registry()
    left = resources.resolver_with_root(DRAFT202012.create_resource(old))
    right = resources.resolver_with_root(DRAFT202012.create_resource(new))
    walker = _Walker([], set())
    walker.compare(old, new, "", left, right)
    return sorted(walker.changes, key=lambda change: (change.pointer, change.bump, change.reason))
