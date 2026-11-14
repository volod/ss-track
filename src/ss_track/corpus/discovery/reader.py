"""Read a discovery run back as evidence, and check it against the corpus version it read.

`read_discovery` needs only the run directory: each record's seal, its contract and every rule its
contract states in words, and each feature vector file's hash. `verify_discovery` also binds the run
to the frame set and corpus manifest on this data root, so its candidates rest on exactly the
source records and terms staged, its sibling windows on the slot rule, and its rows on the frames.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.read_refusals import incomplete_record
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.discovery.binding import require_bound
from ss_track.corpus.discovery.features import FeatureFile, read_vectors
from ss_track.corpus.discovery.findings import Finding, require_no_findings
from ss_track.corpus.discovery.records import DiscoveryRecords, discovery_findings
from ss_track.corpus.records.kinds import (
    CANDIDATE_INVENTORY,
    DISCOVERY_RUN,
    FEATURE_ROWS,
    RecordFormat,
)
from ss_track.corpus.storage.layout import (
    DISCOVERY_RUN_NAME,
    candidate_inventory_path,
    discovery_run_directory,
    discovery_run_path,
    feature_rows_name,
)
from ss_track.schema.validation.enforce import is_shared_type, require_record


def _read(path: Path, record_format: RecordFormat) -> dict[str, JsonValue]:
    """A seal proves only that a record matches itself, so its contract is checked too."""
    record = read_sealed(path, record_format)
    require_record(record)
    return record


def _lines(run: Mapping[str, Any]) -> list[Any]:
    return list(run["inventories"])


def read_discovery(data_root: Path, run_id: str) -> DiscoveryRecords:
    """Read a run and every inventory it seals, refusing a missing, altered or rule-breaking one."""
    path = discovery_run_path(data_root, run_id)
    if not is_shared_type("identifier", run_id) or not path.is_file():
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "no such discovery run",
            {"record": DISCOVERY_RUN_NAME, "run_id": run_id},
        )
    run = _read(path, DISCOVERY_RUN)
    inventories: dict[str, dict[str, JsonValue]] = {}
    for line in _lines(run):
        stream_id = line["stream_id"]
        inventory_path = candidate_inventory_path(data_root, run_id, stream_id)
        inventory = _read(inventory_path, CANDIDATE_INVENTORY)
        if inventory[SEAL_FIELD] != line["inventory_sha256"]:
            raise CorpusRefusal(
                RefusalCode.RECORD_TAMPERED,
                "an inventory is not the one its run sealed",
                {"record": inventory_path.name, "run_id": run_id, "stream_id": stream_id},
            )
        inventories[stream_id] = inventory
    features = _features(data_root, run)
    require_no_findings(_findings(run, inventories, features), run_id)
    return DiscoveryRecords(run, inventories, features)


def _features(data_root: Path, run: Mapping[str, Any]) -> dict[str, FeatureFile]:
    """Read each feature record the run seals and the vector bytes that record seals."""
    directory = discovery_run_directory(data_root, str(run["run_id"]))
    features: dict[str, FeatureFile] = {}
    for line in run.get("feature_rows", []):
        name = feature_rows_name(line["extractor_id"], line["stream_id"])
        record = _read(directory / name, FEATURE_ROWS)
        if record[SEAL_FIELD] != line["rows_sha256"]:
            raise CorpusRefusal(
                RefusalCode.RECORD_TAMPERED,
                "a feature record is not the one its run sealed",
                {"record": name, "run_id": run["run_id"]},
            )
        features[name] = FeatureFile(record, read_vectors((directory / name).parent, record))
    return features


def _findings(
    run: Mapping[str, Any],
    inventories: Mapping[str, Mapping[str, Any]],
    features: Mapping[str, FeatureFile],
) -> list[Finding]:
    with incomplete_record(DISCOVERY_RUN_NAME):
        return discovery_findings(run, inventories, features)


def verify_discovery(data_root: Path, run_id: str) -> DiscoveryRecords:
    """Read a run, then refuse it unless it names exactly what its corpus version staged here."""
    records = read_discovery(data_root, run_id)
    require_bound(data_root, records.run, records.inventories, records.features)
    return records
