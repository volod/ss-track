"""Project the contract dialect to a flat ODCS catalog view, keeping source locations."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ss_track.refusal import JsonValue
from ss_track.schema.store import ContractSet, damaged


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _custom(name: str, value: JsonValue) -> dict[str, JsonValue]:
    return {"property": name, "value": value}


def _type(node: Mapping[str, Any]) -> str | None:
    found = node.get("type")
    if isinstance(found, list):
        types = [item for item in found if item != "null"]
        return types[0] if len(types) == 1 else None
    return found if isinstance(found, str) and found != "null" else None


@dataclass
class Property:
    """A logical property collected from one or more tagged branches."""

    name: str
    descriptions: set[str] = field(default_factory=set)
    types: set[str] = field(default_factory=set)
    untyped: bool = False
    sources: set[str] = field(default_factory=set)

    def record(self) -> dict[str, JsonValue]:
        sources: list[JsonValue] = list(sorted(self.sources))
        result: dict[str, JsonValue] = {
            "name": self.name,
            "customProperties": [_custom("ssTrackSources", sources)],
        }
        if self.descriptions:
            result["description"] = sorted(self.descriptions)[0]
        if len(self.types) == 1 and not self.untyped:
            result["logicalType"] = next(iter(self.types))
        return result


class Projection:
    """Merge tagged branches by logical path and follow installed references offline."""

    def __init__(self, contracts: ContractSet) -> None:
        self.schemas = {
            contract.urn(version): contracts.frozen_schema(contract, version)
            for contract in contracts.contracts
            for version in contract.versions
        }
        self.properties: dict[str, Property] = {}

    def resolve(self, reference: str, base: str) -> tuple[str, str, dict[str, Any]]:
        try:
            urn, fragment = reference.split("#", 1)
            urn = urn or base
            target = self.schemas[urn]
            for part in fragment.lstrip("/").split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            if not isinstance(target, dict):
                raise TypeError("reference target is not an object")
        except (KeyError, TypeError, ValueError) as error:
            raise damaged(f"cannot resolve contract reference {reference}") from error
        return urn, fragment, target

    def walk(
        self, node: Mapping[str, Any], logical: str, urn: str, pointer: str, active: frozenset[str]
    ) -> None:
        if "$ref" in node:
            next_urn, next_pointer, target = self.resolve(node["$ref"], urn)
            key = next_urn + "#" + next_pointer
            if key not in active:
                self.walk(target, logical, next_urn, next_pointer, active | {key})
        for name, child in sorted(node.get("properties", {}).items()):
            child_path = f"{logical}/properties/{_escape(name)}"
            child_pointer = f"{pointer}/properties/{_escape(name)}"
            self.add(child, child_path, urn, child_pointer)
            self.walk(child, child_path, urn, child_pointer, active)
        for index, branch in enumerate(node.get("oneOf", [])):
            self.walk(branch, logical, urn, f"{pointer}/oneOf/{index}", active)
        items = node.get("items")
        if isinstance(items, dict):
            self.walk(items, logical + "/items", urn, pointer + "/items", active)
        for index, child in enumerate(node.get("prefixItems", [])):
            self.walk(
                child,
                f"{logical}/prefixItems/{index}",
                urn,
                f"{pointer}/prefixItems/{index}",
                active,
            )

    def add(self, node: Mapping[str, Any], logical: str, urn: str, pointer: str) -> None:
        item = self.properties.setdefault(logical, Property(logical))
        item.sources.add(urn + "#" + pointer)
        if isinstance(node.get("description"), str):
            item.descriptions.add(node["description"])
        kind = _type(node)
        if kind is None and "$ref" in node:
            _, _, resolved = self.resolve(node["$ref"], urn)
            kind = _type(resolved)
        if kind is None and node.get("oneOf"):
            kinds = {_type(branch) for branch in node["oneOf"]}
            kind = kinds.pop() if len(kinds) == 1 else None
        if kind:
            item.types.add(kind)
        else:
            item.untyped = True

    def project(self, schema: dict[str, Any], urn: str) -> list[dict[str, JsonValue]]:
        self.properties.clear()
        self.walk(schema, "", urn, "", frozenset())
        for name, definition in sorted(schema.get("$defs", {}).items()):
            self.walk(
                definition, f"/$defs/{_escape(name)}", urn, f"/$defs/{_escape(name)}", frozenset()
            )
        return [self.properties[name].record() for name in sorted(self.properties)]


def _children(key: str, value: Any, path: str) -> list[tuple[str, Mapping[str, Any]]]:
    if key in ("properties", "$defs"):
        return [(f"{path}/{_escape(name)}", child) for name, child in sorted(value.items())]
    if key in ("oneOf", "prefixItems"):
        return [(f"{path}/{index}", child) for index, child in enumerate(value)]
    if key == "items" and isinstance(value, dict):
        return [(path, value)]
    return []


def losses(node: Mapping[str, Any], pointer: str = "") -> list[dict[str, JsonValue]]:
    """Inventory every source keyword conservatively, even if the view approximates it."""
    result: list[dict[str, JsonValue]] = []
    for key, value in sorted(node.items()):
        path = f"{pointer}/{_escape(key)}"
        result.append({"pointer": path, "keyword": key})
        for child_path, child in _children(key, value, path):
            result.extend(losses(child, child_path))
    return result
