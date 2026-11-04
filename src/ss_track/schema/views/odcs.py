"""Write ODCS 3.2 catalog views validated against the pinned upstream schema."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft201909Validator

from ss_track.core.canonical import sha256_bytes
from ss_track.core.refusal import JsonValue
from ss_track.schema.registry.contract import Contract
from ss_track.schema.registry.store import ContractSet, damaged, load_contract_set, read_schema
from ss_track.schema.views.odcs_projection import Projection, losses

ODCS_SCHEMA = "meta/standards/odcs-3.2.0.json"
ODCS_SHA256 = "edb41f33ec46e84780e99872ab2bd67f074959d2bf3e9c9fc54e61f8982b0d93"


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Generated ODCS file paths."""

    files: list[str]

    def to_record(self) -> dict[str, JsonValue]:
        return {"status": "exported", "files": list(self.files)}


def _validator(contracts: ContractSet) -> Draft201909Validator:
    path = contracts.root / ODCS_SCHEMA
    try:
        actual = sha256_bytes(path.read_bytes())
    except OSError as error:
        raise damaged("the pinned ODCS schema is unavailable") from error
    if actual != ODCS_SHA256:
        raise damaged("the pinned ODCS schema does not match its SHA-256")
    return Draft201909Validator(read_schema(path))


def _document(contracts: ContractSet, contract: Contract, projection: Projection) -> dict[str, Any]:
    frozen = contract.newest()
    if frozen is None:
        raise damaged(f"{contract.name} has no frozen version to export")
    schema = contracts.frozen_schema(contract, frozen)
    urn = contract.urn(frozen)
    catalog: dict[str, Any] = {"name": contract.name, "properties": projection.project(schema, urn)}
    if schema.get("type") == "object":
        catalog["logicalType"] = "object"
    return {
        "apiVersion": "v3.2.0",
        "kind": "DataContract",
        "id": contract.name,
        "version": frozen.version,
        "name": contract.name,
        "status": contract.status,
        "description": {"purpose": contract.description},
        "schema": [catalog],
        "customProperties": [
            {"property": "ssTrackContractUrn", "value": urn},
            {
                "property": "ssTrackSchemaRepresentation",
                "value": "Flattened schema-like paths; tagged branches are merged. This is a catalog view, not an instance validator.",
            },
            {"property": "ssTrackProjectionLosses", "value": losses(schema)},
            {"property": "ssTrackJsonSchema", "value": schema},
        ],
    }


def export_odcs(out: Path, root: Path | None = None) -> ExportResult:
    """Validate all latest contract projections, then write one JSON document per contract."""
    contracts = load_contract_set(root)
    validator = _validator(contracts)
    projection = Projection(contracts)
    generated = []
    for contract in contracts.contracts:
        document = _document(contracts, contract, projection)
        errors = sorted(
            validator.iter_errors(document), key=lambda error: list(map(str, error.path))
        )
        if errors:
            raise damaged(
                f"ODCS projection for {contract.name} failed validation: {errors[0].message}"
            )
        target = out / contract.family / f"{contract.contract_id}.json"
        generated.append(
            (target, json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
        )
    for target, payload in generated:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="ascii")
    return ExportResult([str(target) for target, _ in generated])
