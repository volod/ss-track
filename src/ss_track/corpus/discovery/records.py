"""Seal and write a discovery run: one candidate inventory per stream, then the run that seals them.

Both formats are checked against their contracts and against every rule their contracts state in
words before anything is written, so a defect is `RECORD_INVALID` with nothing on disk. The run is
written last, so a run record exists only once each inventory it seals does, and an existing run is
never replaced by different records. Nothing is written for a run that does not name exactly the
bundles, source records and groups its corpus version staged.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.discovery.binding import require_bound
from ss_track.corpus.discovery.findings import Finding, inventory_label, require_no_findings
from ss_track.corpus.discovery.inventory_rules import inventory_findings
from ss_track.corpus.discovery.run_rules import run_findings, totals_findings
from ss_track.corpus.records.kinds import CANDIDATE_INVENTORY, DISCOVERY_RUN
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.storage.layout import candidate_inventory_path, discovery_run_path


@dataclass(frozen=True, slots=True)
class DiscoveryRecords:
    """A sealed run and its sealed inventories, keyed by stream."""

    run: dict[str, JsonValue]
    inventories: dict[str, dict[str, JsonValue]]

    @property
    def run_id(self) -> str:
        """Return the run's identifier."""
        return str(self.run["run_id"])


@dataclass(frozen=True, slots=True)
class DiscoveryWrite:
    """Where a run was written, and whether it was already there."""

    path: Path
    written: bool


def discovery_findings(
    run: Mapping[str, Any], inventories: Mapping[str, Mapping[str, Any]]
) -> list[Finding]:
    """Return every rule a run and its inventories break that their contracts state in words."""
    found = [*run_findings(run), *totals_findings(run, inventories)]
    for stream_id in sorted(inventories):
        found += inventory_findings(inventories[stream_id], run)
    return found


def _line(inventory: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    candidates = inventory["candidates"]
    return {
        "stream_id": inventory["stream_id"],
        "bundle_sha256": inventory["bundle_sha256"],
        "source_manifest_sha256": inventory["source_manifest_sha256"],
        "inventory_sha256": inventory[SEAL_FIELD],
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
    }


def seal_discovery(
    run_body: Mapping[str, JsonValue], inventory_bodies: Iterable[Mapping[str, JsonValue]]
) -> DiscoveryRecords:
    """Seal each inventory, then the run with one line per inventory, refusing any broken rule.

    `run_body` holds every run field but `kind`, `schema_version`, `inventories` and the seal;
    each inventory body every field but `kind`, `schema_version` and the seal.
    """
    run_id = str(run_body.get("run_id"))
    inventories: dict[str, dict[str, JsonValue]] = {}
    repeated: list[Finding] = []
    for body in inventory_bodies:
        sealed = seal({**CANDIDATE_INVENTORY.stamp(), **body})
        stream_id = str(sealed["stream_id"])
        if stream_id in inventories:
            message = "a stream has one inventory per run"
            repeated.append(Finding(inventory_label(stream_id), "/stream_id", "order", message))
        inventories[stream_id] = sealed
    require_no_findings(repeated, run_id)
    lines: list[JsonValue] = [_line(inventories[name]) for name in sorted(inventories)]
    run = seal({**DISCOVERY_RUN.stamp(), **run_body, "inventories": lines})
    require_no_findings(discovery_findings(run, inventories), run_id)
    return DiscoveryRecords(run, inventories)


def write_discovery(data_root: Path, records: DiscoveryRecords) -> DiscoveryWrite:
    """Write the inventories, then the run; repeating the same records changes nothing.

    The run must name exactly what its corpus version staged on this data root.
    """
    require_bound(data_root, records.run, records.inventories)
    path = discovery_run_path(data_root, records.run_id)
    if path.exists():
        existing = read_sealed(path, DISCOVERY_RUN)
        if existing[SEAL_FIELD] == records.run[SEAL_FIELD]:
            return DiscoveryWrite(path, written=False)
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this discovery run already holds different records; choose a new run id",
            {
                "run_id": records.run_id,
                "path": str(path),
                "manifest_sha256": existing[SEAL_FIELD],
                "proposed_manifest_sha256": records.run[SEAL_FIELD],
            },
        )
    for stream_id, inventory in sorted(records.inventories.items()):
        write_sealed(candidate_inventory_path(data_root, records.run_id, stream_id), inventory)
    write_sealed(path, records.run)
    return DiscoveryWrite(path, written=True)
