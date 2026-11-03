"""Render frozen contract dictionaries and their annotated lineage."""

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.refusal import JsonValue
from ss_track.schema.store import Contract, ContractSet, load_contract_set


def fields(node: Mapping[str, Any], path: str = "") -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Walk schema positions, preserving distinct branches and definition paths."""
    if not path and ("enum" in node or "x-references" in node):
        yield "#", node
    for keyword in ("properties", "$defs"):
        for name, child in sorted(node.get(keyword, {}).items()):
            pointer = f"{path}/{keyword}/{name.replace('~', '~0').replace('/', '~1')}"
            if keyword == "properties" or "enum" in child or "x-references" in child:
                yield pointer, child
            yield from fields(child, pointer)
    yield from _other_fields(node, path)


def _other_fields(node: Mapping[str, Any], path: str) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for keyword in ("oneOf", "prefixItems"):
        for index, child in enumerate(node.get(keyword, [])):
            pointer = f"{path}/{keyword}/{index}"
            if "enum" in child or "x-references" in child:
                yield pointer, child
            yield from fields(child, pointer)
    if isinstance(node.get("items"), dict):
        child = node["items"]
        if "enum" in child or "x-references" in child:
            yield f"{path}/items", child
        yield from fields(child, f"{path}/items")


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


@dataclass(frozen=True, slots=True)
class DocsResult:
    """Paths written by the reference generator."""

    files: list[str]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the command result."""
        return {"status": "written", "files": list(self.files)}


def _render_contract(
    contracts: ContractSet, contract: Contract, out: Path, edges: set[tuple[str, str, str]]
) -> str:
    first: dict[str, str] = {}
    versions = []
    for frozen in contract.versions:
        schema = contracts.frozen_schema(contract, frozen)
        rows = list(fields(schema))
        for path, node in rows:
            first.setdefault(path, frozen.version)
            if "x-references" in node:
                edges.add((contract.name, path, node["x-references"]))
        versions.append((frozen.version, rows))
    lines = [f"# {contract.name}", "", contract.description, ""]
    for version, rows in versions:
        lines += [
            f"## {version}",
            "",
            "| Field (JSON pointer) | First version | Description | Enum |",
            "| --- | --- | --- | --- |",
        ]
        for path, node in rows:
            enum = json.dumps(node.get("enum", []), ensure_ascii=True, sort_keys=True)
            lines.append(
                f"| `{_cell(path)}` | {first[path]} | {_cell(node.get('description', ''))} | {_cell(enum)} |"
            )
        lines.append("")
    target = out / contract.family / f"{contract.contract_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(target)


def render_docs(out: Path, root: Path | None = None) -> DocsResult:
    """Write deterministic per-contract dictionaries and a lineage graph."""
    contracts = load_contract_set(root)
    out.mkdir(parents=True, exist_ok=True)
    edges: set[tuple[str, str, str]] = set()
    written = []
    for contract in contracts.contracts:
        written.append(_render_contract(contracts, contract, out, edges))
    graph = [
        "# Contract lineage",
        "",
        "| Source contract | Field | Target |",
        "| --- | --- | --- |",
    ]
    graph += [
        f"| `{_cell(source)}` | `{_cell(path)}` | `{_cell(target)}` |"
        for source, path, target in sorted(edges)
    ]
    (out / "lineage.md").write_text("\n".join(graph) + "\n", encoding="utf-8")
    return DocsResult([*written, str(out / "lineage.md")])
