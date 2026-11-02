"""`ss-track contracts`: list the contract set, and check one file against it deeply."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.canonical import SEAL_FIELD, seal_of
from ss_track.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema.store import (
    DECLARATION_FAMILY,
    KIND_FIELD,
    RECORD_FAMILY,
    SHARED_FAMILY,
    VERSION_FIELD,
    Contract,
    ContractSet,
    FrozenVersion,
    load_contract_set,
    version_key,
)
from ss_track.schema.strict import VIOLATION_LIMIT, violations

STATUS_LISTED = "listed"
STATUS_VALID = "valid"


def _version_record(contract: Contract, frozen: FrozenVersion) -> dict[str, JsonValue]:
    return {
        "version": frozen.version,
        "urn": contract.urn(frozen),
        "file_sha256": frozen.file_sha256,
        "structure": frozen.structure,
        "meaning": frozen.meaning,
        "change": dict(frozen.change),
    }


def _contract_record(contract: Contract) -> dict[str, JsonValue]:
    versions: list[JsonValue] = [_version_record(contract, item) for item in contract.versions]
    return {
        "contract": contract.name,
        "family": contract.family,
        "id": contract.contract_id,
        "owner": contract.owner,
        "status": contract.status,
        "description": contract.description,
        "reason": contract.reason,
        "versions": versions,
    }


@dataclass(frozen=True, slots=True)
class ContractList:
    """Every contract this tool carries."""

    root: Path
    contracts: tuple[Contract, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        listed: list[JsonValue] = [_contract_record(item) for item in self.contracts]
        return {"status": STATUS_LISTED, "root": str(self.root), "contracts": listed}


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """One file that conforms to one frozen version."""

    path: Path
    contract: str
    version: str
    urn: str
    seal_checked: bool

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": STATUS_VALID,
            "path": str(self.path),
            "contract": self.contract,
            "version": self.version,
            "urn": self.urn,
            "seal_checked": self.seal_checked,
        }


def list_contracts(root: Path | None = None) -> ContractList:
    """Return the registry as it stands."""
    contracts = load_contract_set(root)
    return ContractList(contracts.root, contracts.contracts)


def _refuse_repeats(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Keep every key, because another language's reader may keep a different one of two."""
    document = dict(pairs)
    if len(document) != len(pairs):
        raise ValueError("a key is repeated")
    return document


def _refuse_constant(name: str) -> None:
    raise ValueError(f"{name} is not JSON")


def _read_document(path: Path) -> object:
    """Parse one JSON file, more strictly than `json.loads` alone: this is the deep check."""
    try:
        return json.loads(
            path.read_bytes(), object_pairs_hook=_refuse_repeats, parse_constant=_refuse_constant
        )
    except (ValueError, RecursionError) as error:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID, f"{path.name} is not valid JSON: {error}"
        ) from error


def _kind_of(contracts: ContractSet, contract: Contract) -> object:
    """Return the `kind` a format stamps, which only its newest version needs to state."""
    if not contract.versions:
        return None
    schema = contracts.frozen_schema(contract, contract.versions[-1])
    return schema.get("properties", {}).get(KIND_FIELD, {}).get("const")


def _contract_of(contracts: ContractSet, document: object) -> Contract:
    """Find the contract of a document that names its own format."""
    kind = document.get(KIND_FIELD) if isinstance(document, dict) else None
    if kind is None:
        raise CorpusRefusal(
            RefusalCode.CONTRACT_UNKNOWN, f"no {KIND_FIELD} in this file: name it with --contract"
        )
    for contract in contracts.contracts:
        if _kind_of(contracts, contract) == kind:
            return contract
    raise CorpusRefusal(
        RefusalCode.CONTRACT_UNKNOWN, f"no contract states kind {kind}", {KIND_FIELD: kind}
    )


def _unknown_version(contract: Contract, version: str | None) -> CorpusRefusal:
    known: list[JsonValue] = [frozen.version for frozen in contract.versions]
    wanted = f"version {version}" if version else "frozen version"
    return CorpusRefusal(
        RefusalCode.CONTRACT_UNKNOWN,
        f"{contract.name} has no {wanted}",
        {"contract": contract.name, "versions": known, "reason": contract.reason},
    )


def _version_of(contract: Contract, document: object, requested: str | None) -> FrozenVersion:
    """Choose an exact version, or the newest of the major the file stamps, or simply the newest."""
    if contract.family == SHARED_FAMILY:
        raise CorpusRefusal(
            RefusalCode.CONTRACT_UNKNOWN,
            f"{contract.name} states value types and no document",
            {"contract": contract.name},
        )
    if requested is not None:
        for frozen in contract.versions:
            if frozen.version == requested:
                return frozen
        raise _unknown_version(contract, requested)
    stamped = document.get(VERSION_FIELD) if isinstance(document, dict) else None
    matching = [frozen for frozen in contract.versions if frozen.major == stamped]
    candidates = matching or list(contract.versions)
    if not candidates:
        raise _unknown_version(contract, None)
    return max(candidates, key=lambda frozen: version_key(frozen.version))


def _invalid_code(contract: Contract) -> RefusalCode:
    """A declaration that breaks its contract is `MANIFEST_INVALID`, as a reader reports it."""
    if contract.family == DECLARATION_FAMILY:
        return RefusalCode.MANIFEST_INVALID
    return RefusalCode.RECORD_INVALID


def _require_seal(path: Path, document: Mapping[str, JsonValue]) -> None:
    """Refuse a record whose content moved: structure alone would call it valid."""
    if document[SEAL_FIELD] != seal_of(document):
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "record content does not match its seal",
            {"record": path.name},
        )


def validate_file(
    path: Path,
    *,
    contract_name: str | None = None,
    version: str | None = None,
    root: Path | None = None,
) -> ValidationResult:
    """Check every field of one file under one frozen version, and a record's seal."""
    contracts = load_contract_set(root)
    document = _read_document(path)
    contract = (
        contracts.named(contract_name) if contract_name else _contract_of(contracts, document)
    )
    frozen = _version_of(contract, document, version)
    schema = contracts.frozen_schema(contract, frozen)
    found = violations(document, schema, contracts.schema_registry())
    if found:
        listed: list[JsonValue] = [item.to_record() for item in found]
        raise CorpusRefusal(
            _invalid_code(contract),
            f"{path.name} breaks {contract.urn(frozen)}: {found[0].pointer} {found[0].message}",
            {"urn": contract.urn(frozen), "violations": listed, "limit": VIOLATION_LIMIT},
        )
    sealed = contract.family == RECORD_FAMILY
    if sealed and isinstance(document, dict):
        _require_seal(path, document)
    return ValidationResult(path, contract.name, frozen.version, contract.urn(frozen), sealed)
