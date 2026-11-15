"""Load one acquisition and check every byte the pool will read.

The acquisition record is evidence of which files were taken and which hash they had. A missing
file, a hash that does not match, or metadata over the size limit refuses the pool.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import sha256_file
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.records.kinds import SOURCE_ACQUISITION
from ss_track.corpus.sources.inventory import read_inventory
from ss_track.corpus.sources.metadata_claims import MAX_METADATA_BYTES
from ss_track.corpus.storage.layout import discovery_run_directory

_TERMS = ("attribution", "terms", "terms_reference")


@dataclass(frozen=True, slots=True)
class AcquiredFile:
    """One acquired file whose local bytes match the acquisition record."""

    path: str
    local_path: str
    sha256: str
    location: Path


@dataclass(frozen=True, slots=True)
class InventoryVideo:
    """Inventory facts for one video. Null terms are retained so the caller can refuse them."""

    source_reference: str | None
    annotation_reference: str | None
    upstream_split: str | None
    attribution: str | None
    terms: str | None
    terms_reference: str | None
    status: str


@dataclass(frozen=True, slots=True)
class AcquisitionFacts:
    """An acquisition run, its inventory and the files whose hashes were checked."""

    provider: str
    collection_id: str
    provider_version: str
    videos: dict[str, AcquiredFile]
    inventory: dict[str, InventoryVideo]
    metadata: tuple[tuple[str, Path, str], ...]


def load_acquisition(run_id: str, data_root: Path) -> AcquisitionFacts:
    """Read one acquisition, refusing a run that is missing or whose bytes changed."""
    root = discovery_run_directory(data_root, run_id)
    record_path = root / "acquisition.json"
    if not record_path.is_file():
        raise CorpusRefusal(
            RefusalCode.SOURCE_NOT_FOUND, "acquisition run was not found", {"run_id": run_id}
        )
    record = read_sealed(record_path, SOURCE_ACQUISITION)
    inventory = _inventory(root, record)
    videos = {item.path: item for item in _files(root, _rows(record.get("videos")), metadata=False)}
    metadata = tuple(_files(root, _rows(record.get("metadata_files", [])), metadata=True))
    return AcquisitionFacts(
        _string(record, "provider"),
        _string(record, "collection_id"),
        _string(record, "revision"),
        videos,
        inventory,
        tuple((item.path, item.location, item.sha256) for item in metadata),
    )


def _inventory(root: Path, record: dict[str, JsonValue]) -> dict[str, InventoryVideo]:
    path = root / "inventory.json"
    if not path.is_file() or sha256_file(path) != record.get("inventory_sha256"):
        raise CorpusRefusal(
            RefusalCode.SOURCE_DAMAGED, "inventory bytes do not match the acquisition"
        )
    document = read_inventory(path)
    provider, collection_id = _string(record, "provider"), _string(record, "collection_id")
    matches = [
        item
        for item in document["collections"]
        if item["provider"] == provider and item["collection_id"] == collection_id
    ]
    if len(matches) != 1:
        raise invalid("acquisition collection is not in its inventory")
    return {video["path"]: _inventory_video(video) for video in matches[0]["videos"]}


def _inventory_video(video: dict[str, object]) -> InventoryVideo:
    return InventoryVideo(
        _optional(video, "source_reference"),
        _optional(video, "annotation_reference"),
        _optional(video, "upstream_split"),
        _optional(video, "attribution"),
        _optional(video, "terms"),
        _optional(video, "terms_reference"),
        str(video["status"]),
    )


def _optional(video: dict[str, object], key: str) -> str | None:
    value = video[key]
    return value if isinstance(value, str) else None


def _files(
    root: Path, rows: list[dict[str, JsonValue]], *, metadata: bool
) -> tuple[AcquiredFile, ...]:
    return tuple(_file(root, row, metadata=metadata) for row in rows)


def _file(root: Path, row: dict[str, JsonValue], *, metadata: bool) -> AcquiredFile:
    path = _string(row, "path")
    local_path = _string(row, "local_path")
    digest = _string(row, "sha256")
    location = _inside(root, local_path)
    if metadata and location.stat().st_size > MAX_METADATA_BYTES:
        raise CorpusRefusal(RefusalCode.SOURCE_DAMAGED, "acquired metadata exceeds its size limit")
    if sha256_file(location) != digest:
        raise CorpusRefusal(
            RefusalCode.SOURCE_DAMAGED, "acquired bytes do not match the acquisition"
        )
    return AcquiredFile(path, local_path, digest, location)


def _inside(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    path = root / relative
    if parts.is_absolute() or ".." in parts.parts or not path.is_file() or path.is_symlink():
        raise CorpusRefusal(
            RefusalCode.SOURCE_DAMAGED, "acquired path escapes the run or is missing"
        )
    if not path.resolve().is_relative_to(root.resolve()):
        raise CorpusRefusal(
            RefusalCode.SOURCE_DAMAGED, "acquired path escapes the run or is missing"
        )
    return path


def _rows(value: JsonValue) -> list[dict[str, JsonValue]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise CorpusRefusal(RefusalCode.SOURCE_DAMAGED, "acquisition record is incomplete")
    return cast(list[dict[str, JsonValue]], value)


def _string(record: dict[str, JsonValue], key: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value.strip():
        raise CorpusRefusal(RefusalCode.SOURCE_DAMAGED, "acquisition record is incomplete")
    return value


def require_terms(video: InventoryVideo) -> None:
    """Refuse a selected video whose inventory lacks attribution or terms."""
    if video.status != "candidate" or any(getattr(video, key) is None for key in _TERMS):
        raise invalid("a selected video is missing candidate attribution or terms")
