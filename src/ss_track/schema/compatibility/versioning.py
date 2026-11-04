"""Version and change-log policy shared by freeze and the history gate."""

from ss_track.schema.compatibility.change_rules import NO_BUMP, RANK
from ss_track.schema.compatibility.dispositions import disposition_floor
from ss_track.schema.compatibility.evolution import diff_schemas, required_bump
from ss_track.schema.registry.contract import (
    DISPOSITIONS,
    MAJOR,
    MINOR,
    PATCH,
    Contract,
    FrozenVersion,
    version_key,
)
from ss_track.schema.registry.store import ContractSet


def bump_kind(before: str, after: str) -> str:
    """Name the changed semantic-version component, refusing non-increasing versions."""
    old, new = version_key(before), version_key(after)
    if new <= old:
        return NO_BUMP
    if new[0] != old[0]:
        return MAJOR if new[1:] == (0, 0) else NO_BUMP
    if new[1] != old[1]:
        return MINOR if new[2] == 0 else NO_BUMP
    return PATCH


def transition_findings(
    contracts: ContractSet, contract: Contract, previous: FrozenVersion, current: FrozenVersion
) -> list[str]:
    """Check a new version against its predecessor and all earlier minors of its major."""
    registry = contracts.schema_registry()
    new = contracts.frozen_schema(contract, current)
    changes = diff_schemas(contracts.frozen_schema(contract, previous), new, registry)
    required = required_bump(changes)
    actual = bump_kind(previous.version, current.version)
    findings = []
    if actual == NO_BUMP or RANK[actual] < RANK[required]:
        findings.append(f"version bump {actual} is too small or invalid; requires {required}")
    if current.change["class"] != actual:
        findings.append(f"change class must be {actual}")
    if actual == MAJOR:
        if not str(current.change.get("migration", "")).strip():
            findings.append("a major requires migration text")
        disposition = current.change.get("disposition")
        if disposition not in DISPOSITIONS:
            findings.append(
                "a major requires the predecessor's disposition: view, facts or retired"
            )
        elif DISPOSITIONS.index(str(disposition)) < DISPOSITIONS.index(
            floor := disposition_floor(changes, new, registry)
        ):
            findings.append(
                "this major changes an operator judgment or an algorithm revision, "
                f"so its disposition is {floor}"
            )
    return findings + _transitive_findings(contracts, contract, current)


def _transitive_findings(
    contracts: ContractSet, contract: Contract, current: FrozenVersion
) -> list[str]:
    registry = contracts.schema_registry()
    new = contracts.frozen_schema(contract, current)
    findings = []
    for frozen in contract.versions:
        if frozen == current or frozen.major != current.major:
            continue
        if version_key(frozen.version) >= version_key(current.version):
            continue
        old = contracts.frozen_schema(contract, frozen)
        if required_bump(diff_schemas(old, new, registry)) == MAJOR:
            findings.append(f"not backward compatible with {frozen.version}")
    return findings
