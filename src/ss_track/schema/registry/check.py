"""The Git-free set checks used by `make lint-contracts` and candidate freezing.

It compares each frozen file with what the registry pinned, so it cannot see a file edited together
with its registry entry. Comparing with the history is the job of the evolution gate.
"""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from referencing.exceptions import Unresolvable

from ss_track.core.canonical import SEAL_FIELD, sha256_bytes
from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.evolution import pointer_parts
from ss_track.schema.registry.contract import (
    DECLARATION_FAMILY,
    EVENT_FAMILY,
    KIND_FIELD,
    RECORD_FAMILY,
    VERSION_FIELD,
    Contract,
    FrozenVersion,
    version_key,
)
from ss_track.schema.registry.dialect import dialect_findings
from ss_track.schema.registry.fingerprints import meaning_fingerprint, structure_fingerprint, walk
from ss_track.schema.registry.stage import stage_findings
from ss_track.schema.registry.store import (
    DIALECT_NAME,
    META_DIRECTORY,
    ContractSet,
    damaged,
    default_root,
    load_contract_set,
    read_schema,
)
from ss_track.schema.validation.strict import Schema

_FILE_GLOBS = ("*.json", "*.binpb")

_LOG = logging.getLogger(__name__)


def _registry_findings(contracts: ContractSet) -> list[str]:
    """Hold the registry to one order, so it has one reading and a repeat cannot hide."""
    findings = []
    keys = [(contract.family, contract.contract_id) for contract in contracts.contracts]
    if keys != sorted(set(keys)):
        findings.append("registry contracts are repeated or out of family and id order")
    for contract in contracts.contracts:
        versions = [version_key(frozen.version) for frozen in contract.versions]
        if versions != sorted(set(versions)):
            findings.append(f"{contract.name}: versions are repeated or out of order")
        retired = [int(str(entry["major"])) for entry in contract.retired_majors]
        if retired != sorted(set(retired)):
            findings.append(f"{contract.name}: retired majors are repeated or out of order")
        if any(frozen.major in retired for frozen in contract.versions):
            findings.append(f"{contract.name}: a retired major without a contract has a version")
    return findings


def _stray_findings(contracts: ContractSet) -> list[str]:
    """Name a file the registry does not list, which no gate would otherwise see."""
    listed = {
        contracts.root / contract.relative_path(frozen)
        for contract in contracts.contracts
        for frozen in contract.versions
    }
    meta = contracts.root / META_DIRECTORY
    found = {
        path
        for pattern in _FILE_GLOBS
        for path in contracts.root.rglob(pattern)
        if meta not in path.parents
    }
    return [
        f"{path.relative_to(contracts.root)}: not listed in the registry"
        for path in sorted(found - listed)
    ]


def _identity_findings(contract: Contract, frozen: FrozenVersion, schema: Schema) -> list[str]:
    expected = contract.urn(frozen)
    found = schema.get("$id")
    return [] if found == expected else [f"$id is {found}, expected {expected}"]


def _stamp_findings(contract: Contract, frozen: FrozenVersion, schema: Schema) -> list[str]:
    """Hold a format's stamps to the rule that `schema_version` is the contract's major."""
    if contract.family not in (RECORD_FAMILY, DECLARATION_FAMILY):
        return []
    properties = schema.get("properties", {})
    findings = []
    stamped = properties.get(VERSION_FIELD, {})
    if stamped.get("const") != frozen.major or stamped.get("type") != "integer":
        findings.append(f"{VERSION_FIELD} must be the integer const {frozen.major}")
    if contract.family == RECORD_FAMILY:
        if "const" not in properties.get(KIND_FIELD, {}):
            findings.append(f"a record must state its {KIND_FIELD} as a const")
        if SEAL_FIELD not in schema.get("required", ()):
            findings.append(f"a record must require {SEAL_FIELD}")
    return findings


def _fingerprint_findings(frozen: FrozenVersion, schema: Schema) -> list[str]:
    computed = {
        "structure": (frozen.structure, structure_fingerprint(schema)),
        "meaning": (frozen.meaning, meaning_fingerprint(schema)),
    }
    return [
        f"{name} fingerprint is stale: registry {pinned}, file {found}"
        for name, (pinned, found) in computed.items()
        if pinned != found
    ]


def _version_findings(
    contracts: ContractSet,
    contract: Contract,
    frozen: FrozenVersion,
    dialect: Schema,
    known_urns: set[str],
) -> list[str]:
    """Check one frozen file against the registry and the dialect."""
    path = contracts.root / contract.relative_path(frozen)
    try:
        payload = path.read_bytes()
    except OSError as error:
        return [f"cannot read the file: {error}"]
    edited = sha256_bytes(payload) != frozen.file_sha256
    if contract.family == EVENT_FAMILY:
        from ss_track.contract.image import event_version_findings

        findings = (
            [f"frozen file was edited: registry {frozen.file_sha256}, file {sha256_bytes(payload)}"]
            if edited
            else []
        )
        return findings + event_version_findings(
            payload, contract.urn(frozen), frozen.structure, frozen.meaning, known_urns
        )
    try:
        schema = read_schema(path)
    except CorpusRefusal as error:
        return [f"cannot read the file: {error}"]
    findings = []
    if edited:
        findings.append(
            f"frozen file was edited: registry {frozen.file_sha256}, file {sha256_bytes(payload)}"
        )
    findings += _identity_findings(contract, frozen, schema)
    findings += dialect_findings(schema, dialect)
    findings += _stamp_findings(contract, frozen, schema)
    return findings + _fingerprint_findings(frozen, schema)


def _document_contracts(contracts: ContractSet) -> list[Contract]:
    """Return the JSON Schema contracts. Event packages are descriptor sets."""
    return [contract for contract in contracts.contracts if contract.family != EVENT_FAMILY]


def _reference_findings(contracts: ContractSet) -> list[str]:
    """Resolve every `$ref` of intact files, because a validator meets a bad one only when used."""
    registry = contracts.schema_registry()
    findings = []
    for contract in _document_contracts(contracts):
        for frozen in contract.versions:
            urn = contract.urn(frozen)
            resolver = registry.resolver(urn)
            nodes = walk(contracts.frozen_schema(contract, frozen))
            for reference in (node["$ref"] for node in nodes if "$ref" in node):
                try:
                    resolver.lookup(reference)
                except Unresolvable:
                    findings.append(f"{urn}: $ref {reference} resolves to nothing")
    return findings + _annotation_findings(contracts)


def _annotation_resolves(contracts: ContractSet, reference: str) -> bool:
    try:
        name, pointer = reference.split("#", 1)
        contract = contracts.named(name)
        newest = contract.newest()
        if newest is None:
            return False
        target: Any = contracts.frozen_schema(contract, newest)
        for key in pointer_parts(pointer):
            target = target[int(key)] if isinstance(target, list) else target[key]
        return True
    except (CorpusRefusal, ValueError, IndexError, KeyError, TypeError):
        return False


def _annotation_findings(contracts: ContractSet) -> list[str]:
    findings = []
    for contract in _document_contracts(contracts):
        for frozen in contract.versions:
            for node in walk(contracts.frozen_schema(contract, frozen)):
                reference = node.get("x-references")
                if reference is None:
                    continue
                if not _annotation_resolves(contracts, reference):
                    findings.append(
                        f"{contract.urn(frozen)}: x-references {reference} resolves to nothing"
                    )
    return findings


def runtime_findings(contracts: ContractSet) -> list[str]:
    """Check installed pins and stage without the build gate's expensive dialect audit."""
    findings = (
        _registry_findings(contracts) + _stray_findings(contracts) + stage_findings(contracts)
    )
    known_urns = {
        contract.urn(frozen)
        for contract in contracts.contracts
        if contract.family == EVENT_FAMILY
        for frozen in contract.versions
    }
    for contract in contracts.contracts:
        for frozen in contract.versions:
            label = f"{contract.name} {frozen.version}"
            findings.extend(
                f"{label}: {item}"
                for item in _runtime_version_findings(contracts, contract, frozen, known_urns)
            )
    return findings


def _runtime_version_findings(
    contracts: ContractSet, contract: Contract, frozen: FrozenVersion, known_urns: set[str]
) -> list[str]:
    try:
        if contract.family == EVENT_FAMILY:
            return _version_findings(contracts, contract, frozen, {}, known_urns)
        schema = contracts.frozen_schema(contract, frozen)
        return _identity_findings(contract, frozen, schema) + _fingerprint_findings(frozen, schema)
    except CorpusRefusal as error:
        return [error.message]


def require_runtime_pins(contracts: ContractSet) -> None:
    """Refuse an installed set with stale files, fingerprints or stage rules."""
    findings = runtime_findings(contracts)
    if findings:
        raise damaged("installed contract set is invalid: " + "; ".join(findings))


def load_checked_contract_set(root: Path | None = None) -> ContractSet:
    """Load a contract set for runtime consumers after verifying its pins."""
    contracts = load_contract_set(root)
    require_runtime_pins(contracts)
    return contracts


def check_contract_set(root: Path) -> list[str]:
    """Return every finding over one contract set."""
    try:
        contracts = load_contract_set(root)
        dialect = read_schema(root / META_DIRECTORY / DIALECT_NAME)
    except CorpusRefusal as refusal:
        return [refusal.message]
    findings = _registry_findings(contracts) + _stray_findings(contracts)
    findings += stage_findings(contracts)
    known_urns = {
        contract.urn(frozen)
        for contract in contracts.contracts
        if contract.family == EVENT_FAMILY
        for frozen in contract.versions
    }
    for contract in contracts.contracts:
        for frozen in contract.versions:
            label = f"{contract.name} {frozen.version}"
            found = _version_findings(contracts, contract, frozen, dialect, known_urns)
            findings += [f"{label}: {finding}" for finding in found]
    return findings or _reference_findings(contracts)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the contract gate."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="check a contract set against its registry")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    findings = check_contract_set(args.root.resolve() if args.root else default_root())
    for finding in findings:
        _LOG.error("ERROR: %s", finding)
    _LOG.info("[contracts] %d finding(s)", len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
