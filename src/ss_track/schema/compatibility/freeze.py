"""Prepare and publish an immutable schema and its registry entry after all checks pass."""

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import JsonValue
from ss_track.schema.compatibility.evolution import Change, diff_schemas, required_bump
from ss_track.schema.compatibility.publishing import publish
from ss_track.schema.compatibility.versioning import bump_kind, transition_findings
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.contract import (
    DISPOSITIONS,
    INITIAL,
    MAJOR,
    contract_urn,
    version_path,
)
from ss_track.schema.registry.dialect import dialect_findings
from ss_track.schema.registry.fingerprints import meaning_fingerprint, structure_fingerprint
from ss_track.schema.registry.store import (
    DIALECT_NAME,
    META_DIRECTORY,
    REGISTRY_NAME,
    ContractSet,
    damaged,
    default_root,
    load_contract_set,
    read_schema,
    registry_document,
)

_VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
_VERSION_MARK = "0.0.0"  # stands in for the version in a URN, to match the rest exactly


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
    family, _, contract_id = name.partition("/")
    prefix = contract_urn(family, contract_id, _VERSION_MARK).removesuffix(_VERSION_MARK)
    match = re.fullmatch(re.escape(prefix) + f"({_VERSION})", identity)
    if match is None or name.count("/") != 1:
        raise damaged("candidate $id must name the requested family/id and a semantic version")
    dialect = read_schema(contracts.root / META_DIRECTORY / DIALECT_NAME)
    findings = dialect_findings(schema, dialect)
    if findings:
        raise damaged("candidate breaks the dialect: " + "; ".join(findings))
    return schema, match[1]


def diff_contract(name: str, path: Path, root: Path | None = None) -> EvolutionResult:
    """Compare a candidate with the newest frozen version; no file is changed."""
    contracts = load_contract_set(root)
    schema, version = _candidate(contracts, name, path)
    return EvolutionResult(name, version, _changes(contracts, name, schema))


def _changes(contracts: ContractSet, name: str, schema: dict[str, Any]) -> list[Change]:
    contract = contracts.find(name)
    newest = None if contract is None else contract.newest()
    if contract is None or newest is None:
        return []
    old = contracts.frozen_schema(contract, newest)
    return diff_schemas(old, schema, contracts.schema_registry())


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
    if actual == MAJOR:
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
    changes = _changes(contracts, name, schema)
    contract = contracts.find(name)
    previous = None if contract is None else contract.newest()
    actual = bump_kind(previous.version, version) if previous else INITIAL
    change = _change_log(actual, summary, migration, disposition)
    payload = path.read_bytes()
    original = (base / REGISTRY_NAME).read_bytes()
    registry = registry_document(original)
    _register(registry, name, _entry(payload, schema, version, change), owner, schema)
    written = yaml.safe_dump(registry, sort_keys=False, allow_unicode=False).encode("ascii")
    relative = version_path(name, version)
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
        candidate = next(item for item in updated.versions if item.version == version)
        if not findings and previous is not None:
            findings += transition_findings(staged, updated, previous, candidate)
        if findings:
            raise damaged("freeze refused: " + "; ".join(findings))
    publish(base, relative, payload, written, original)
    return EvolutionResult(name, version, changes, "frozen")
