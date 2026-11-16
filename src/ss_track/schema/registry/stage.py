"""The registry stage of spec section 17.7: what a contract set may hold before and after release.

In the development stage each contract has one version, `1.0.0`, edited in place and re-pinned, so
the set holds no version history, no historic major and no disposition. In the released stage every
frozen version is immutable and the history gate compares it with Git. A released set never
returns to development. Nothing here reads Git: `schema.compatibility.history` compares stages.
"""

from pathlib import Path

from ss_track.schema.registry.contract import BASELINE_VERSION, DEVELOPMENT, INITIAL, RELEASED
from ss_track.schema.registry.store import REGISTRY_NAME, ContractSet, registry_document

STAGE_FIELD = "stage"


def stage_findings(contracts: ContractSet) -> list[str]:
    """Name each contract that breaks the rules of the set's stage."""
    if contracts.stage != DEVELOPMENT:
        return []
    findings = []
    for contract in contracts.contracts:
        versions = [frozen.version for frozen in contract.versions]
        if contract.versions and versions != [BASELINE_VERSION]:
            findings.append(
                f"{contract.name}: the development stage holds one version, {BASELINE_VERSION}; "
                f"found {', '.join(versions)}. Edit {BASELINE_VERSION} in place and re-pin it"
            )
        if any(frozen.change.get("class") != INITIAL for frozen in contract.versions):
            findings.append(f"{contract.name}: a development version's change class is initial")
        if contract.retired_majors:
            findings.append(f"{contract.name}: the development stage holds no retired major")
    return findings


def stage_of(root: Path) -> str:
    """Return the stage a registry states; one written before stages existed is development.

    This reads only the stage, so the history gate can compare a revision whose registry predates
    the field without validating the rest of it under today's meta-schema.
    """
    stage = registry_document((root / REGISTRY_NAME).read_bytes()).get(STAGE_FIELD, DEVELOPMENT)
    return RELEASED if stage == RELEASED else DEVELOPMENT


def regression_finding(previous: str, current: str, revision: str) -> list[str]:
    """Refuse a set that returns to development after a revision it descends from was released."""
    if previous == RELEASED and current == DEVELOPMENT:
        return [f"the contract set was released at {revision} and cannot return to development"]
    return []
