"""Prepare and publish an immutable schema and its registry entry after all checks pass."""

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ss_track.canonical import sha256_bytes
from ss_track.refusal import JsonValue
from ss_track.schema._publishing import publish
from ss_track.schema.check import check_contract_set
from ss_track.schema.dialect import dialect_findings
from ss_track.schema.evolution import Change, diff_schemas, required_bump
from ss_track.schema.fingerprints import meaning_fingerprint, structure_fingerprint
from ss_track.schema.store import (
    REGISTRY_NAME,
    ContractSet,
    damaged,
    default_root,
    load_contract_set,
    read_schema,
    registry_document,
)
from ss_track.schema.versioning import DISPOSITIONS, bump_kind, transition_findings

_VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"


@dataclass(frozen=True)
class EvolutionResult:
    """One explained candidate, optionally frozen into a writable contract set."""

    contract: str
    version: str
    changes: list[Change]
    status: str = "diffed"

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "status": self.status,
            "contract": self.contract,
            "version": self.version,
            "required_bump": required_bump(self.changes),
            "changes": [change.to_record() for change in self.changes],
        }


def _candidate(contracts: ContractSet, name: str, path: Path) -> tuple[dict[str, Any], str]:
    schema = read_schema(path)
    identity = str(schema.get("$id", ""))
    match = re.fullmatch(
        r"urn:ss-track:contract:" + re.escape(name.replace("/", ":")) + rf":({_VERSION})", identity
    )
    if match is None or name.count("/") != 1:
        raise damaged("candidate $id must name the requested family/id and a semantic version")
    findings = dialect_findings(schema, read_schema(contracts.root / "meta" / "dialect.json"))
    if findings:
        raise damaged("candidate breaks the dialect: " + "; ".join(findings))
    return schema, match[1]


def diff_contract(name: str, path: Path, root: Path | None = None) -> EvolutionResult:
    """Compare a candidate with the newest frozen version; no file is changed."""
    contracts = load_contract_set(root)
    schema, version = _candidate(contracts, name, path)
    contract = next((item for item in contracts.contracts if item.name == name), None)
    changes = []
    if contract is not None and contract.versions:
        changes = diff_schemas(
            contracts.frozen_schema(contract, contract.versions[-1]),
            schema,
            contracts.schema_registry(),
        )
    return EvolutionResult(name, version, changes)


def _entry(
    payload: bytes, schema: dict[str, Any], version: str, change: dict[str, str]
) -> dict[str, Any]:
    return {
        "version": version,
        "file_sha256": sha256_bytes(payload),
        "fingerprints": {
            "structure": structure_fingerprint(schema),
            "meaning": meaning_fingerprint(schema),
        },
        "change": change,
    }


def _register(
    registry: dict[str, Any],
    name: str,
    entry: dict[str, Any],
    owner: str | None,
    schema: dict[str, Any],
) -> None:
    family, identifier = name.split("/")
    contract = next(
        (
            item
            for item in registry["contracts"]
            if (item["family"], item["id"]) == (family, identifier)
        ),
        None,
    )
    if contract is None:
        if not owner:
            raise damaged("an initial freeze requires --owner")
        contract = {
            "family": family,
            "id": identifier,
            "owner": owner,
            "status": "active",
            "description": schema["description"],
            "versions": [],
        }
        registry["contracts"].append(contract)
    if any(item["version"] == entry["version"] for item in contract["versions"]):
        raise damaged("a frozen version cannot be replaced")
    contract["versions"].append(entry)
    contract["status"] = "active"
    contract.pop("reason", None)
    registry["contracts"].sort(key=lambda item: (item["family"], item["id"]))


def _change_log(
    actual: str, summary: str, migration: str | None, disposition: str | None
) -> dict[str, str]:
    if not summary.strip():
        raise damaged("freeze requires a nonblank summary")
    change = {"class": actual, "summary": summary}
    if actual == "major":
        if not migration or not migration.strip() or disposition not in DISPOSITIONS:
            raise damaged(
                "a major requires migration text and a disposition: view, facts or retired"
            )
        change |= {"migration": migration, "disposition": disposition}
    elif migration is not None or disposition is not None:
        raise damaged("migration and disposition apply only to a major transition")
    return change


def freeze_contract(
    name: str,
    path: Path,
    *,
    summary: str,
    migration: str | None = None,
    disposition: str | None = None,
    owner: str | None = None,
    root: Path | None = None,
) -> EvolutionResult:
    """Validate a staged set in isolation before writing schema bytes and the generated pins."""
    base = default_root() if root is None else root
    contracts = load_contract_set(base)
    schema, version = _candidate(contracts, name, path)
    result = diff_contract(name, path, base)
    contract = next((item for item in contracts.contracts if item.name == name), None)
    previous = contract.versions[-1] if contract and contract.versions else None
    actual = bump_kind(previous.version, version) if previous else "initial"
    change = _change_log(actual, summary, migration, disposition)
    payload = path.read_bytes()
    original = (base / REGISTRY_NAME).read_bytes()
    registry = registry_document(original)
    _register(registry, name, _entry(payload, schema, version, change), owner, schema)
    written = yaml.safe_dump(registry, sort_keys=False, allow_unicode=False).encode("ascii")
    relative = Path(*name.split("/"), f"{version}.json")
    with tempfile.TemporaryDirectory(prefix=".freeze-", dir=base.parent) as scratch:
        stage = Path(scratch) / "contracts"
        shutil.copytree(base, stage, ignore=shutil.ignore_patterns("__pycache__"))
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        (stage / REGISTRY_NAME).write_bytes(written)
        findings = check_contract_set(stage)
        staged = load_contract_set(stage)
        updated = staged.named(name)
        if not findings and previous is not None:
            findings += transition_findings(staged, updated, previous, updated.versions[-1])
        if findings:
            raise damaged("freeze refused: " + "; ".join(findings))
    publish(base, relative, payload, written, original)
    return EvolutionResult(name, version, result.changes, "frozen")
