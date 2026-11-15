"""Version and change-log policy shared by freeze and the history gate."""

from pathlib import Path

from ss_track.contract.breaking import breaking_findings
from ss_track.contract.image import fingerprints
from ss_track.schema.compatibility.change_rules import NO_BUMP, RANK
from ss_track.schema.compatibility.dispositions import disposition_floor
from ss_track.schema.compatibility.evolution import diff_schemas, required_bump
from ss_track.schema.registry.contract import (
    DISPOSITIONS,
    EVENT_FAMILY,
    FACTS,
    MAJOR,
    MINOR,
    PATCH,
    VIEW,
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
    if contract.family == EVENT_FAMILY:
        return _event_transition(contracts, contract, previous, current)
    registry = contracts.schema_registry()
    new = contracts.frozen_schema(contract, current)
    changes = diff_schemas(contracts.frozen_schema(contract, previous), new, registry)
    required = required_bump(changes)
    findings = _policy_findings(
        previous, current, required, disposition_floor(changes, new, registry)
    )
    return findings + _transitive_findings(contracts, contract, current)


def _policy_findings(
    previous: FrozenVersion,
    current: FrozenVersion,
    required: str,
    floor: str,
    floor_reason: str | None = None,
) -> list[str]:
    actual = bump_kind(previous.version, current.version)
    findings = []
    if actual == NO_BUMP or RANK[actual] < RANK[required]:
        findings.append(f"version bump {actual} is too small or invalid; requires {required}")
    if current.change["class"] != actual:
        findings.append(f"change class must be {actual}")
    if actual == MAJOR:
        findings += _major_findings(current, floor, floor_reason)
    return findings


def _major_findings(current: FrozenVersion, floor: str, floor_reason: str | None) -> list[str]:
    findings = []
    if not str(current.change.get("migration", "")).strip():
        findings.append("a major requires migration text")
    disposition = current.change.get("disposition")
    if disposition not in DISPOSITIONS:
        findings.append("a major requires the predecessor's disposition: view, facts or retired")
    elif DISPOSITIONS.index(str(disposition)) < DISPOSITIONS.index(floor):
        findings.append(
            floor_reason
            or (
                "this major changes an operator judgment or an algorithm revision, "
                f"so its disposition is {floor}"
            )
        )
    return findings


def _event_transition(
    contracts: ContractSet, contract: Contract, previous: FrozenVersion, current: FrozenVersion
) -> list[str]:
    """Classify a descriptor change with ``buf breaking``, not a JSON Schema diff."""
    old = contracts.root / contract.relative_path(previous)
    new = contracts.root / contract.relative_path(current)
    if old.read_bytes() == new.read_bytes():
        return ["descriptor bytes are unchanged"]
    required = _event_bump(old, new, contract.urn(previous), contract.urn(current))
    floor = FACTS if required == MAJOR else VIEW
    findings = _policy_findings(
        previous,
        current,
        required,
        floor,
        "a wire-incompatible event major cannot be a view, so its disposition is facts",
    )
    return findings + _event_transitive(contracts, contract, current, new)


def _event_bump(old: Path, new: Path, old_urn: str, new_urn: str) -> str:
    if breaking_findings(new, old):
        return MAJOR
    old_structure, _meaning = fingerprints(old.read_bytes(), old_urn)
    new_structure, _meaning = fingerprints(new.read_bytes(), new_urn)
    if old_structure != new_structure:
        return MINOR
    return PATCH


def _event_transitive(
    contracts: ContractSet, contract: Contract, current: FrozenVersion, new: Path
) -> list[str]:
    findings = []
    for frozen in contract.versions:
        if frozen == current or frozen.major != current.major:
            continue
        if version_key(frozen.version) >= version_key(current.version):
            continue
        old = contracts.root / contract.relative_path(frozen)
        if breaking_findings(new, old):
            findings.append(f"not backward compatible with {frozen.version}")
    return findings


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
