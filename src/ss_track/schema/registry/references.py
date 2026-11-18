"""Reference checks of an intact contract set: every `$ref` and `x-references` must resolve.

A validator meets a bad reference only when a document uses it, so the gate resolves each one. A
record or shared contract may reference only the families a development data-root stamp pins.
"""

from typing import Any

from referencing.exceptions import Unresolvable

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.evolution import pointer_parts
from ss_track.schema.registry.contract import (
    EVENT_FAMILY,
    STAMPED_FAMILIES,
    Contract,
    urn_family,
)
from ss_track.schema.registry.fingerprints import walk
from ss_track.schema.registry.store import ContractSet


def _document_contracts(contracts: ContractSet) -> list[Contract]:
    """Return the JSON Schema contracts. Event packages are descriptor sets."""
    return [contract for contract in contracts.contracts if contract.family != EVENT_FAMILY]


def reference_findings(contracts: ContractSet) -> list[str]:
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
                findings += _stamped_reference_findings(contract, urn, reference)
    return findings + _annotation_findings(contracts)


def _stamped_reference_findings(contract: Contract, urn: str, reference: str) -> list[str]:
    """Hold a record or shared contract to references the development data-root stamp pins.

    The stamp pins record and shared contracts (spec section 17.7), so a record whose shape also
    came from another family could change while its root's stamp still matched.
    """
    family = urn_family(reference)
    if contract.family not in STAMPED_FAMILIES or family is None or family in STAMPED_FAMILIES:
        return []
    return [
        f"{urn}: $ref {reference} names a {family} contract, which the data-root stamp does not pin"
    ]


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
