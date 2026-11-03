"""Version and change-log policy shared by freeze and the history gate."""

from ss_track.schema._change_rules import RANK
from ss_track.schema.dispositions import disposition_floor
from ss_track.schema.evolution import diff_schemas, required_bump
from ss_track.schema.store import DISPOSITIONS, Contract, ContractSet, FrozenVersion, version_key


def bump_kind(before: str, after: str) -> str:
    """Name the changed semantic-version component, refusing non-increasing versions."""
    old, new = version_key(before), version_key(after)
    if new <= old:
        return "none"
    if new[0] != old[0]:
        return "major" if new[1:] == (0, 0) else "none"
    if new[1] != old[1]:
        return "minor" if new[2] == 0 else "none"
    return "patch"


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
    if actual == "none" or RANK[actual] < RANK[required]:
        findings.append(f"version bump {actual} is too small or invalid; requires {required}")
    if current.change["class"] != actual:
        findings.append(f"change class must be {actual}")
    if actual == "major":
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
                f"this major changes an operator judgment, so its disposition is {floor}"
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
        if required_bump(diff_schemas(old, new, registry)) == "major":
            findings.append(f"not backward compatible with {frozen.version}")
    return findings
