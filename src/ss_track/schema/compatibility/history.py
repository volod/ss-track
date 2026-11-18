"""Compare the working contract set with Git history, by the stage each revision states.

A development set is checked against its own pins alone; a released revision's versions are
immutable, and no revision may return a released set to development.
"""

import argparse
import logging
import subprocess
import tempfile
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.versioning import transition_findings
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.contract import (
    DEVELOPMENT,
    INITIAL,
    RELEASED,
    Contract,
    FrozenVersion,
)
from ss_track.schema.registry.stage import regression_finding, stage_of, stated_stage
from ss_track.schema.registry.store import ContractSet, load_contract_set, registry_document

_LOG = logging.getLogger(__name__)


def _git(project: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(project), *arguments], capture_output=True, check=False
    )
    if result.returncode:
        raise ValueError(f"git {' '.join(arguments)}: {result.stderr.decode().strip()}")
    return result.stdout


def _snapshot(project: Path, revision: str, destination: Path) -> bool:
    paths = (
        _git(project, "ls-tree", "-r", "--name-only", revision, "--", "contracts")
        .decode()
        .splitlines()
    )
    if "contracts/registry.yaml" not in paths:
        return False  # This revision predates the first published contract set.
    for name in paths:
        relative = Path(name).relative_to("contracts")
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_git(project, "show", f"{revision}:{name}"))
    return True


def immutable_findings(previous: ContractSet, current: ContractSet) -> list[str]:
    """Neither frozen bytes nor their version entries may be rewritten or removed."""
    findings = []
    available = {contract.name: contract for contract in current.contracts}
    for contract in previous.contracts:
        successor = available.get(contract.name)
        versions = {item.version: item for item in successor.versions} if successor else {}
        findings += _immutable_versions(previous, current, contract, versions)

    return findings


def _immutable_versions(
    previous: ContractSet,
    current: ContractSet,
    contract: Contract,
    versions: dict[str, FrozenVersion],
) -> list[str]:
    findings = []
    for frozen in contract.versions:
        label = f"{contract.name} {frozen.version}"
        if versions.get(frozen.version) != frozen:
            findings.append(f"{label}: frozen registry entry changed or removed")
        path = current.root / contract.relative_path(frozen)
        original = previous.root / contract.relative_path(frozen)
        if not path.is_file() or path.read_bytes() != original.read_bytes():
            findings.append(f"{label}: frozen file changed or removed")
    return findings


def evolution_findings(contracts: ContractSet) -> list[str]:
    """Recompute each transition instead of trusting the change class an author supplied."""
    findings = []
    for contract in contracts.contracts:
        if contract.versions and contract.versions[0].change["class"] != INITIAL:
            findings.append(f"{contract.name}: the first frozen version must be initial")
        for previous, current in zip(contract.versions, contract.versions[1:], strict=False):
            found = transition_findings(contracts, contract, previous, current)
            findings += [f"{contract.name} {current.version}: {item}" for item in found]
    return findings


def _revision_findings(snapshot: Path, revision: str, current: ContractSet) -> list[str]:
    """Compare a committed set by the stage rules of spec section 17.7.

    A development revision froze nothing, so only a released one holds bytes that must not move.
    """
    previous = stage_of(snapshot)
    findings = regression_finding(previous, current.stage, revision)
    if previous == RELEASED:
        findings += immutable_findings(load_contract_set(snapshot), current)
    return findings


def _released_history(project: Path) -> tuple[set[str], list[str]]:
    """Inspect registry revisions and refuse a later return after any ancestral release."""
    revisions = _git(
        project, "log", "--full-history", "--format=%H", "HEAD", "--", "contracts/registry.yaml"
    )
    stages = {}
    for revision in revisions.decode().splitlines():
        payload = _git(project, "show", f"{revision}:contracts/registry.yaml")
        try:
            stages[revision] = stated_stage(registry_document(payload))
        except CorpusRefusal as error:
            raise ValueError(f"the registry at {revision}: {error.message}") from error
    released = {revision for revision, stage in stages.items() if stage == RELEASED}
    findings = []
    for revision in released:
        later = (
            _git(
                project,
                "rev-list",
                "--full-history",
                "--ancestry-path",
                f"{revision}..HEAD",
                "--",
                "contracts/registry.yaml",
            )
            .decode()
            .splitlines()
        )
        for descendant in later:
            if stages.get(descendant) == DEVELOPMENT:
                findings.append(
                    f"the contract set was released at {revision} and cannot return to "
                    f"development at {descendant}"
                )
    return released, findings


def history_findings(project: Path, base_ref: str) -> list[str]:
    """Compare merge base, HEAD and every released registry in their ancestry."""
    root = project / "contracts"
    findings = check_contract_set(root)
    if findings:
        return findings
    try:
        current = load_contract_set(root)
        findings += evolution_findings(current)
        if _git(project, "rev-parse", "--is-shallow-repository").strip() == b"true":
            return [*findings, "contract history requires a full checkout (fetch-depth: 0)"]
        base = _git(project, "merge-base", "HEAD", base_ref).decode().strip()
        head = _git(project, "rev-parse", "HEAD").decode().strip()
        released, stage_history = _released_history(project)
        findings += stage_history
        for revision in sorted({base, head} | released):
            with tempfile.TemporaryDirectory(prefix="ss-track-contract-history-") as temporary:
                snapshot = Path(temporary)
                if _snapshot(project, revision, snapshot):
                    findings += _revision_findings(snapshot, revision, current)
    except (ValueError, OSError, CorpusRefusal) as error:
        findings.append(f"cannot check contract history: {error}")
    return sorted(set(findings))


def main() -> int:
    """Run history-aware validation for a source checkout, separately from wheel validation."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--base-ref", required=True)
    args = parser.parse_args()
    findings = history_findings(args.project.resolve(), args.base_ref)
    for finding in findings:
        _LOG.error("ERROR: %s", finding)
    _LOG.info("[contract evolution] %d finding(s)", len(findings))
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
