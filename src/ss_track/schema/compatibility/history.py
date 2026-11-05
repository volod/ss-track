"""Compare the working contract set with immutable versions held by Git history."""

import argparse
import logging
import subprocess
import tempfile
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal
from ss_track.schema.compatibility.versioning import transition_findings
from ss_track.schema.registry.check import check_contract_set
from ss_track.schema.registry.contract import INITIAL, Contract, FrozenVersion
from ss_track.schema.registry.store import ContractSet, load_contract_set

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


def history_findings(project: Path, base_ref: str) -> list[str]:
    """Fail closed on absent history; compare the merge base and the committed working baseline."""
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
        for revision in sorted({base, head}):
            with tempfile.TemporaryDirectory(prefix="ss-track-contract-history-") as temporary:
                snapshot = Path(temporary)
                if _snapshot(project, revision, snapshot):
                    findings += immutable_findings(load_contract_set(snapshot), current)
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
