"""The annotation contracts, and the one way a document is read or built under them.

Every annotation declaration is read under one schema major. A reader validates under the newest
frozen version of that major, and that is the version a command reports.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.annotate.declarations.digest import as_document, declaration_hash
from ss_track.core.refusal import JsonValue, RefusalCode
from ss_track.schema.registry.contract import Contract, FrozenVersion
from ss_track.schema.registry.store import damaged
from ss_track.schema.validation.enforce import (
    installed_contracts,
    read_declaration,
    require_conforming,
)

SCENARIO_PACK_CONTRACT = "declaration/scenario-pack"
LABEL_CONTRACT = "declaration/annotation-label"
SEED_CONTRACT = "declaration/annotation-seed"
MASK_CONTRACT = "declaration/annotation-mask"
REVIEW_CONTRACT = "declaration/annotation-review"
SETTLEMENT_CONTRACT = "declaration/annotation-settlement"
SCHEMA_MAJOR = 1


def read_hashed(path: Path, contract_name: str) -> tuple[dict[str, Any], str]:
    """Read one declaration under its contract and return it with its declaration hash."""
    document = read_declaration(path, contract_name, SCHEMA_MAJOR)
    return document, declaration_hash(as_document(document))


def read_version(contract_name: str) -> str:
    """Return the frozen version a reader of this contract validates under."""
    return _frozen(contract_name)[1].version


def require_built(document: Mapping[str, JsonValue], contract_name: str, label: str) -> None:
    """Refuse a document this code built when its contract does not accept it."""
    contract, frozen = _frozen(contract_name)
    require_conforming(
        document,
        installed_contracts().contracts,
        contract,
        frozen,
        code=RefusalCode.MANIFEST_INVALID,
        label=label,
    )


def _frozen(contract_name: str) -> tuple[Contract, FrozenVersion]:
    contract = installed_contracts().contracts.named(contract_name)
    frozen = contract.newest(SCHEMA_MAJOR)
    if frozen is None:
        raise damaged(f"{contract_name} has no frozen major {SCHEMA_MAJOR}")
    return contract, frozen
