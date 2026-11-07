"""Seal and write a discovery run: its inventories and feature rows, then the run that seals them.

Every format is checked against its contract and against every rule it states in words before
anything is written, so a defect is `RECORD_INVALID` with nothing on disk. A run is built whole in
scratch and published by one rename under the discovery lock, so a reader meets a whole run or
none, two writers of one run id leave one run or a refusal, and an existing run is never replaced by
different records. Nothing is written for a run that does not name exactly the bundles, source
records and groups its corpus version staged.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.discovery.binding import require_bound
from ss_track.corpus.discovery.features import FeatureFile, feature_findings, lines_findings
from ss_track.corpus.discovery.findings import Finding, inventory_label, require_no_findings
from ss_track.corpus.discovery.inventory_rules import inventory_findings
from ss_track.corpus.discovery.run_rules import run_findings, totals_findings
from ss_track.corpus.records.kinds import CANDIDATE_INVENTORY, DISCOVERY_RUN
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal, write_sealed
from ss_track.corpus.storage.layout import (
    DISCOVERY_RUN_NAME,
    INVENTORIES_DIRECTORY,
    discovery_root,
    discovery_run_path,
)
from ss_track.corpus.storage.scratch import (
    READ_ONLY_FILE_MODE,
    exclusive_lock,
    scratch_directory,
    write_atomically,
)

_PUBLISH_LOCK = ".publish.lock"


@dataclass(frozen=True, slots=True)
class DiscoveryRecords:
    """A sealed run and its sealed inventories, keyed by stream."""

    run: dict[str, JsonValue]
    inventories: dict[str, dict[str, JsonValue]]
    features: dict[str, FeatureFile] = field(default_factory=dict)  # by path inside the run

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
    run: Mapping[str, Any],
    inventories: Mapping[str, Mapping[str, Any]],
    features: Mapping[str, FeatureFile] | None = None,
) -> list[Finding]:
    """Return every rule a run and its records break that their contracts state in words."""
    found = [*run_findings(run), *totals_findings(run, inventories)]
    for stream_id in sorted(inventories):
        found += inventory_findings(inventories[stream_id], run)
    found += lines_findings(run, inventories)
    for name, feature in sorted((features or {}).items()):
        found += feature_findings(feature.record, name)
        found += _feature_line(feature, run, inventories, name)
    return found


def _feature_line(
    feature: FeatureFile,
    run: Mapping[str, Any],
    inventories: Mapping[str, Mapping[str, Any]],
    name: str,
) -> Iterable[Finding]:
    record = feature.record
    for key in ("run_id", "corpus_id"):
        if record[key] != run[key]:
            yield Finding(name, f"/{key}", "binding", f"{key} differs from the run's")
    inventory = inventories.get(feature.stream_id)
    if inventory is not None and record["bundle_sha256"] != inventory["bundle_sha256"]:
        message = "the rows name another bundle than the stream's inventory"
        yield Finding(name, "/bundle_sha256", "binding", message)
    if feature.line() not in run.get("feature_rows", []):
        yield Finding(name, "/manifest_sha256", "features", "the run seals no such feature record")


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
    run_body: Mapping[str, JsonValue],
    inventory_bodies: Iterable[Mapping[str, JsonValue]],
    features: Iterable[FeatureFile] = (),
) -> DiscoveryRecords:
    """Seal each inventory, then the run with one line per inventory, refusing any broken rule.

    `run_body` holds every run field but `kind`, `schema_version`, `inventories`, `feature_rows`
    and the seal; each inventory body every field but `kind`, `schema_version` and the seal. A run
    with feature rows seals one line per already sealed feature record.
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
    by_name = {feature.name: feature for feature in features}
    feature_lines: dict[str, JsonValue] = {}
    if by_name:
        ordered = sorted(by_name.values(), key=lambda item: (item.extractor_id, item.stream_id))
        feature_lines["feature_rows"] = [feature.line() for feature in ordered]
    run = seal({**DISCOVERY_RUN.stamp(), **run_body, **feature_lines, "inventories": lines})
    require_no_findings(discovery_findings(run, inventories, by_name), run_id)
    return DiscoveryRecords(run, inventories, by_name)


def write_discovery(data_root: Path, records: DiscoveryRecords) -> DiscoveryWrite:
    """Publish a whole run by one rename; repeating the same records changes nothing.

    The run must name exactly what its corpus version staged on this data root. Writers wait for
    one another only while they publish, which is brief: the work before it is done outside.
    """
    require_bound(data_root, records.run, records.inventories, records.features)
    root = discovery_root(data_root)
    path = discovery_run_path(data_root, records.run_id)
    with exclusive_lock(root, _PUBLISH_LOCK, clear=(root,)):
        if path.parent.exists():
            _require_same(path, records)
            return DiscoveryWrite(path, written=False)
        with scratch_directory(root) as staged:
            _write_records(staged, records)
            staged.rename(path.parent)
    return DiscoveryWrite(path, written=True)


def _require_same(path: Path, records: DiscoveryRecords) -> None:
    if not path.exists():
        raise CorpusRefusal(
            RefusalCode.CORPUS_CONFLICT,
            "this discovery run directory holds no whole run; remove it or choose a new run id",
            {"run_id": records.run_id, "path": str(path.parent)},
        )
    existing = read_sealed(path, DISCOVERY_RUN)
    if existing[SEAL_FIELD] != records.run[SEAL_FIELD]:
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


def _write_records(directory: Path, records: DiscoveryRecords) -> None:
    for stream_id, inventory in sorted(records.inventories.items()):
        write_sealed(directory / INVENTORIES_DIRECTORY / f"{stream_id}.json", inventory)
    for name, feature in sorted(records.features.items()):
        record_path = directory / name
        write_sealed(record_path, feature.record)
        vectors: Any = feature.record["vectors"]
        write_atomically(
            record_path.parent / str(vectors["file"]), feature.vectors, mode=READ_ONLY_FILE_MODE
        )
    write_sealed(directory / DISCOVERY_RUN_NAME, records.run)
