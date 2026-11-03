"""Runtime enforcement: installed contracts check declarations on read and records before sealing.

A sealed read does not come here. A seal proves a record has not changed since it was validated, so
reading one checks its seal, kind and major and walks no field. Rules across fields or files stay in
the code that reads a format, stated in its contract's `x-rules`.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from referencing import Registry

from ss_track.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.schema._documents import _read_document
from ss_track.schema.store import (
    RECORD_FAMILY,
    SHARED_FAMILY,
    VERSION_FIELD,
    Contract,
    ContractSet,
    FrozenVersion,
    damaged,
    load_contract_set,
)
from ss_track.schema.strict import VIOLATION_LIMIT, Violation, violations

SHARED_TYPES = "shared/types"
_STAMP_POINTER = f"/{VERSION_FIELD}"


@dataclass(frozen=True, slots=True)
class _Installed:
    """The contract set this tool shipped with, read once per process."""

    contracts: ContractSet
    registry: Registry[Any]
    records: Mapping[object, Contract]


@cache
def _installed() -> _Installed:
    contracts = load_contract_set()
    records = {
        contracts.kind_of(contract): contract
        for contract in contracts.contracts
        if contract.family == RECORD_FAMILY
    }
    return _Installed(contracts, contracts.schema_registry(), records)


def require_conforming(
    document: object,
    contracts: ContractSet,
    contract: Contract,
    frozen: FrozenVersion,
    *,
    code: RefusalCode,
    label: str,
    registry: Registry[Any] | None = None,
) -> None:
    """Refuse a document that breaks one frozen version, naming a wrong major first."""
    found = violations(
        document, contracts.frozen_schema(contract, frozen), registry or contracts.schema_registry()
    )
    if not found:
        return
    first = _first(found)
    listed: list[JsonValue] = [item.to_record() for item in found]
    urn = contract.urn(frozen)
    where = f"{first.pointer} " if first.pointer else ""
    raise CorpusRefusal(
        code,
        f"{label} breaks {urn}: {where}{first.message}",
        {"urn": urn, "violations": listed, "limit": VIOLATION_LIMIT},
    )


def _first(found: list[Violation]) -> Violation:
    """A document of another major breaks much else, and its stamp is what an operator must see."""
    return next((item for item in found if item.pointer == _STAMP_POINTER), found[0])


def read_declaration(path: Path, contract_name: str, major: int) -> dict[str, Any]:
    """Parse operator YAML strictly and validate it in full under the major its reader reads."""
    try:
        document = _read_document(path, declaration=True)
    except OSError as error:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID, f"cannot read {path.name}: {error}"
        ) from error
    installed = _installed()
    contract = installed.contracts.named(contract_name)
    frozen = contract.newest(major)
    if frozen is None:
        raise damaged(f"{contract.name} has no frozen version of major {major}")
    require_conforming(
        document,
        installed.contracts,
        contract,
        frozen,
        code=RefusalCode.MANIFEST_INVALID,
        label=path.name,
        registry=installed.registry,
    )
    assert isinstance(document, dict)  # every declaration contract states an object
    return document


def require_record(record: Mapping[str, JsonValue]) -> None:
    """Refuse a record that breaks its contract before it is sealed: that is a writer defect."""
    try:  # the written form: tuples become lists and a NaN cannot pass unnoticed
        document = json.loads(json.dumps(record, allow_nan=False))
    except ValueError as error:
        raise CorpusRefusal(RefusalCode.RECORD_INVALID, f"record is not JSON: {error}") from error
    installed = _installed()
    kind = document.get("kind")
    contract = installed.records.get(kind)
    if contract is None:
        raise CorpusRefusal(RefusalCode.RECORD_INVALID, f"no contract states kind {kind}")
    major = document.get(VERSION_FIELD)
    frozen = contract.newest(major) if type(major) is int else None
    if frozen is None:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID, f"{contract.name} has no frozen version of major {major}"
        )
    require_conforming(
        document,
        installed.contracts,
        contract,
        frozen,
        code=RefusalCode.RECORD_INVALID,
        label=str(kind),
        registry=installed.registry,
    )


def older_remedy(kind: str, major: int) -> str | None:
    """Return the migration the change log states for a record of an earlier major, if any."""
    contract = _installed().records.get(kind)
    return None if contract is None else contract.migration_from(major)


def is_shared_type(type_name: str, value: object) -> bool:
    """Say whether a value is one of the shared value types, as every contract states it."""
    installed = _installed()
    contract = installed.contracts.named(SHARED_TYPES)
    frozen = contract.newest()
    if contract.family != SHARED_FAMILY or frozen is None:
        raise damaged(f"{SHARED_TYPES} states no value types")
    schema = {"$ref": f"{contract.urn(frozen)}#/$defs/{type_name}"}
    return not violations(value, schema, installed.registry)
