"""The contract set: its registry, its frozen files and their identity.

Root `contracts/` ships inside the wheel as the package `ss_track.contract_files`, so one lookup
serves a checkout and an installed tool. `META_DIRECTORY` holds what defines the set itself.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from ss_track.canonical import sha256_bytes
from ss_track.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema.strict import Schema, violations
from ss_track.strict_json import finite_float, reject_constant, unique_object
from ss_track.strict_yaml import UniqueKeyLoader

CONTRACT_FILES_PACKAGE = "ss_track.contract_files"
REGISTRY_NAME = "registry.yaml"
META_DIRECTORY = "meta"
DIALECT_NAME = "dialect.json"
REGISTRY_SCHEMA_NAME = "registry.json"
KIND_FIELD = "kind"
VERSION_FIELD = "schema_version"
RECORD_FAMILY = "record"
DECLARATION_FAMILY = "declaration"
SHARED_FAMILY = "shared"
_URN_PREFIX = "urn:ss-track:contract"


def default_root() -> Path:
    """Return the contract set that shipped with this tool."""
    return Path(str(files(CONTRACT_FILES_PACKAGE)))


def contract_urn(family: str, contract_id: str, version: str) -> str:
    """Return the stable identity of one frozen version."""
    return f"{_URN_PREFIX}:{family}:{contract_id}:{version}"


def version_key(version: str) -> tuple[int, ...]:
    """Return a version as numbers, because `10.0.0` sorts after `9.0.0`."""
    return tuple(int(part) for part in version.split("."))


def damaged(message: str) -> CorpusRefusal:
    """Build the refusal for a contract set that cannot be trusted."""
    return CorpusRefusal(RefusalCode.CONTRACT_SET_INVALID, message)


@dataclass(frozen=True, slots=True)
class FrozenVersion:
    """One immutable version as the registry pins it."""

    version: str
    file_sha256: str
    structure: str
    meaning: str
    change: Mapping[str, JsonValue]

    @property
    def major(self) -> int:
        return version_key(self.version)[0]


@dataclass(frozen=True, slots=True)
class Contract:
    """One registry entry: a format and every frozen version of it, oldest first."""

    family: str
    contract_id: str
    owner: str
    status: str
    description: str
    reason: str | None
    versions: tuple[FrozenVersion, ...]
    retired_majors: tuple[Mapping[str, JsonValue], ...] = ()

    @property
    def name(self) -> str:
        return f"{self.family}/{self.contract_id}"

    def urn(self, frozen: FrozenVersion) -> str:
        return contract_urn(self.family, self.contract_id, frozen.version)

    def relative_path(self, frozen: FrozenVersion) -> Path:
        return Path(self.family, self.contract_id, f"{frozen.version}.json")

    def newest(self, major: int | None = None) -> FrozenVersion | None:
        """Return the newest frozen version, of one major when given, which reads all its minors."""
        found = [item for item in self.versions if major is None or item.major == major]
        return max(found, key=lambda item: version_key(item.version), default=None)

    def migration_from(self, major: int) -> str | None:
        """Return the change log's migration for a holder of a record of an earlier major.

        A retired major states its own. Otherwise it is the first major transition after it, which
        the gate requires to carry migration text.
        """
        for entry in self.retired_majors:
            if entry["major"] == major:
                return str(entry["migration"])
        for frozen in self.versions:
            if frozen.major > major and frozen.change["class"] == "major":
                return str(frozen.change["migration"])
        return None


def _frozen(entry: Mapping[str, Any]) -> FrozenVersion:
    fingerprints = entry["fingerprints"]
    return FrozenVersion(
        entry["version"],
        entry["file_sha256"],
        fingerprints["structure"],
        fingerprints["meaning"],
        entry["change"],
    )


def _contract(entry: Mapping[str, Any]) -> Contract:
    return Contract(
        entry["family"],
        entry["id"],
        entry["owner"],
        entry["status"],
        entry["description"],
        entry.get("reason"),
        tuple(_frozen(version) for version in entry["versions"]),
        tuple(entry.get("retired_majors", ())),
    )


def read_schema(path: Path) -> Schema:
    """Read one schema file of the set, whose damage is the set's and not the caller's."""
    try:
        schema = json.loads(
            path.read_bytes(),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
        if not isinstance(schema, dict):
            raise ValueError("a schema must be a JSON object")
    except (OSError, ValueError, RecursionError) as error:
        raise damaged(f"cannot read contract file {path.name}: {error}") from error
    return schema


def registry_document(payload: bytes) -> dict[str, Any]:
    """Parse registry bytes for a freeze; the staged contract-set check validates their shape."""
    try:
        document = yaml.load(payload.decode("utf-8"), Loader=UniqueKeyLoader)
        if not isinstance(document, dict):
            raise ValueError("registry must be a mapping")
    except (ValueError, yaml.YAMLError) as error:
        raise damaged(f"cannot read {REGISTRY_NAME}: {error}") from error
    return document


def _read_registry(root: Path) -> object:
    path = root / REGISTRY_NAME
    try:
        return registry_document(path.read_bytes())
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise damaged(f"cannot read {REGISTRY_NAME}: {error}") from error


@dataclass(frozen=True, slots=True)
class ContractSet:
    """Every contract under one root."""

    root: Path
    contracts: tuple[Contract, ...]

    def named(self, name: str) -> Contract:
        """Return one contract by `<family>/<id>`, refusing a name the registry lacks."""
        for contract in self.contracts:
            if contract.name == name:
                return contract
        known: list[JsonValue] = [contract.name for contract in self.contracts]
        raise CorpusRefusal(
            RefusalCode.CONTRACT_UNKNOWN, f"no contract named {name}", {"contracts": known}
        )

    def frozen_schema(self, contract: Contract, frozen: FrozenVersion) -> Schema:
        """Read one frozen version, refusing a file that is not the one the registry pinned."""
        path = self.root / contract.relative_path(frozen)
        try:
            found = sha256_bytes(path.read_bytes())
        except OSError as error:
            raise damaged(f"cannot read {contract.urn(frozen)}: {error}") from error
        if found != frozen.file_sha256:
            raise damaged(f"{contract.urn(frozen)} is not the file the registry pinned")
        return read_schema(path)

    def kind_of(self, contract: Contract) -> object:
        """Return the `kind` a format stamps, which only its newest version needs to state."""
        newest = contract.newest()
        if newest is None:
            return None
        return (
            self.frozen_schema(contract, newest)
            .get("properties", {})
            .get(KIND_FIELD, {})
            .get("const")
        )

    def schema_registry(self) -> Registry[Any]:
        """Return every frozen version for `$ref` resolution, by URN and never from a network."""
        resources = [
            (
                contract.urn(frozen),
                Resource.from_contents(
                    self.frozen_schema(contract, frozen), default_specification=DRAFT202012
                ),
            )
            for contract in self.contracts
            for frozen in contract.versions
        ]
        return Registry().with_resources(resources)


def load_contract_set(root: Path | None = None) -> ContractSet:
    """Read a registry and refuse one that its own schema refuses."""
    base = default_root() if root is None else root
    registry = _read_registry(base)
    meta = read_schema(base / META_DIRECTORY / REGISTRY_SCHEMA_NAME)
    found = violations(registry, meta, Registry())
    if found:
        first = found[0]
        raise damaged(f"{REGISTRY_NAME}{first.pointer}: {first.message}")
    assert isinstance(registry, dict)  # the schema above requires a mapping
    return ContractSet(base, tuple(_contract(entry) for entry in registry["contracts"]))
