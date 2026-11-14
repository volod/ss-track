"""Acquire explicitly authorized source videos at immutable provider revisions."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.records.kinds import SOURCE_ACQUISITION
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal
from ss_track.corpus.review.export import write_once
from ss_track.corpus.sources.acquisition_inventory import populate, select
from ss_track.corpus.sources.archive import _target, extract_selected, list_files
from ss_track.corpus.sources.inventory import InventoryResult, _path, read_inventory
from ss_track.corpus.sources.provider_http import download
from ss_track.corpus.sources.provider_listing import (
    huggingface_listing,
    huggingface_url,
    zenodo_listing,
    zenodo_url,
)
from ss_track.corpus.sources.provider_metadata import ProviderFile, is_video
from ss_track.corpus.sources.zenodo_splits import apply_splits, fetch_splits, split_file
from ss_track.corpus.storage.scratch import exclusive_lock
from ss_track.schema.validation.enforce import is_shared_type


@dataclass(frozen=True, slots=True)
class AcquisitionRequest:
    """Explicit selection, operator assertion and byte limits for a single collection."""

    inventory: Path
    provider: str
    collection_id: str
    selection: list[str]
    run_id: str
    download_budget: int
    extraction_budget: int
    authorized: bool
    metadata: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    """Location and seal of the resulting acquisition record."""

    path: Path
    digest: str
    status: str
    inventory: InventoryResult

    def to_record(self) -> dict[str, object]:
        """Return the existing command result fields."""
        return {
            "status": self.status,
            "manifest_path": str(self.path),
            "manifest_sha256": self.digest,
            "source_inventory": self.inventory.to_record()["source_inventory"],
        }


def _collection(document: dict[str, Any], request: AcquisitionRequest) -> dict[str, Any]:
    matches = [
        item
        for item in document["collections"]
        if item["provider"] == request.provider and item["collection_id"] == request.collection_id
    ]
    if len(matches) != 1:
        raise invalid("the selected collection is not in the inventory")
    return cast(dict[str, Any], matches[0])


def _budget(total: int, budget: int) -> None:
    if budget < 0 or total > budget:
        raise CorpusRefusal(
            RefusalCode.SOURCE_UNREADABLE, "selected acquisition exceeds its byte budget"
        )


def _hf_videos(
    collection: dict[str, Any], request: AcquisitionRequest, root: Path
) -> tuple[list[JsonValue], list[JsonValue], str | None, str | None, str | None]:
    token = os.environ.get("HF_TOKEN") or None
    files = huggingface_listing(collection["collection_id"], collection["revision"], token)
    populate(collection, set(files))
    chosen = [files[path] for path in sorted(request.selection)]
    if any(path not in files or is_video(path) for path in request.metadata):
        raise CorpusRefusal(
            RefusalCode.SOURCE_DAMAGED, "selected metadata does not match provider files"
        )
    metadata = [files[path] for path in sorted(request.metadata)]
    _budget(sum(item.size for item in chosen + metadata), request.download_budget)
    _budget(sum(item.size for item in chosen + metadata), request.extraction_budget)
    return (
        [_hf_video(collection, item, root, token, "media") for item in chosen],
        [_hf_video(collection, item, root, token, "metadata") for item in metadata],
        None,
        None,
        None,
    )


def _hf_video(
    collection: dict[str, Any], item: ProviderFile, root: Path, token: str | None, directory: str
) -> JsonValue:
    relative = f"{directory}/{item.path}"
    target = _target(root, relative)
    algorithm = "sha256" if item.sha256 else "git-sha1"
    expected = item.sha256 or item.git_oid
    digest = download(
        huggingface_url(collection["collection_id"], collection["revision"], item.path),
        target,
        item.size,
        algorithm,
        expected,
        token,
        scratch=root / "scratch",
    )
    return {
        "path": item.path,
        "local_path": relative,
        "size": item.size,
        "sha256": digest,
        "git_oid": item.git_oid,
        "lfs_sha256": item.sha256,
    }


def _zenodo_videos(
    collection: dict[str, Any], request: AcquisitionRequest, root: Path
) -> tuple[list[JsonValue], list[JsonValue], str | None, str | None, str | None]:
    if request.metadata:
        raise invalid("explicit metadata files are supported only for Hugging Face")
    archive, md5 = collection["archive_path"], collection["archive_md5"]
    if archive is None or md5 is None:
        raise invalid("Zenodo archive path and published checksum are required")
    size, metadata = zenodo_listing(
        collection["collection_id"], collection["revision"], archive, md5
    )
    split_info = split_file(metadata)
    _budget(size + (split_info[0] if split_info else 0), request.download_budget)
    target = _target(root, "cache/source.zip")
    archive_sha = download(
        zenodo_url(collection["collection_id"], archive),
        target,
        size,
        "md5",
        md5,
        scratch=root / "scratch",
    )
    files = list_files(target)
    populate(collection, set(files))
    split_path = _target(root, "cache/splits.json")
    _, split_md5, split_sha = fetch_splits(collection, metadata, split_path, root / "scratch")
    if split_info is not None:
        apply_splits(collection, split_path)
    selected = set(request.selection)
    _budget(sum(files[path] for path in selected), request.extraction_budget)
    hashes = extract_selected(
        target,
        _target(root, "media"),
        selected,
        request.extraction_budget,
        scratch=root / "scratch",
    )
    rows: list[JsonValue] = [
        {
            "path": path,
            "local_path": f"media/{path}",
            "size": files[path],
            "sha256": digest,
            "git_oid": None,
            "lfs_sha256": None,
        }
        for path, digest in sorted(hashes.items())
    ]
    return rows, [], archive_sha, split_md5, split_sha


def _check_existing(root: Path, request: AcquisitionRequest, input_sha: str) -> None:
    path = root / "acquisition.json"
    if not path.exists():
        return
    record = read_sealed(path, SOURCE_ACQUISITION)
    videos = record.get("videos")
    selected = (
        sorted(
            cast(str, row["path"])
            for row in videos
            if isinstance(row, dict) and isinstance(row.get("path"), str)
        )
        if isinstance(videos, list)
        else []
    )
    metadata_files = record.get("metadata_files")
    metadata = (
        sorted(
            cast(str, row["path"])
            for row in metadata_files
            if isinstance(row, dict) and isinstance(row.get("path"), str)
        )
        if isinstance(metadata_files, list)
        else []
    )
    if (
        metadata != sorted(request.metadata)
        or record.get("input_inventory_sha256") != input_sha
        or record.get("provider") != request.provider
        or record.get("collection_id") != request.collection_id
        or selected != sorted(request.selection)
    ):
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT, "run already contains a different acquisition"
        )


def _reserve_request(root: Path, request: AcquisitionRequest, input_sha: str) -> None:
    identity: dict[str, JsonValue] = {
        "inventory": input_sha,
        "provider": request.provider,
        "collection": request.collection_id,
        "videos": list(sorted(request.selection)),
        "metadata": list(sorted(request.metadata)),
    }
    marker = root / (".request-" + sha256_bytes(canonical_json(identity)))
    if any(
        path != marker or not path.is_dir() or path.is_symlink() for path in root.glob(".request-*")
    ):
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "run already holds a different request")
    marker.mkdir(exist_ok=True)


def acquire(request: AcquisitionRequest, data_root: Path) -> AcquisitionResult:
    """Acquire selected videos and publish an immutable normalized inventory and record."""
    if not is_shared_type("identifier", request.run_id):
        raise invalid("run id is not an identifier")
    if request.download_budget < 0 or request.extraction_budget < 0:
        raise invalid("byte budgets must be nonnegative")
    if len(set(request.metadata)) != len(request.metadata):
        raise invalid("metadata paths must be unique")
    for metadata_path in request.metadata:
        _path(metadata_path)
    document = read_inventory(request.inventory)
    collection = _collection(document, request)
    select(collection, request.selection, request.authorized)
    input_inventory = canonical_json(document)
    input_sha = sha256_bytes(input_inventory)
    root = _target(data_root.resolve(), f"self-supervised-corpus/{request.run_id}")
    scratch = _target(root, "scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(root, ".acquisition.lock", clear=(scratch,)):
        _check_existing(root, request, input_sha)
        _reserve_request(root, request, input_sha)
        write_once(root / "input-inventory.json", input_inventory)
        if request.provider == "huggingface":
            videos, metadata_files, archive_sha, split_md5, split_sha = _hf_videos(
                collection, request, root
            )
        else:
            videos, metadata_files, archive_sha, split_md5, split_sha = _zenodo_videos(
                collection, request, root
            )
        inventory = canonical_json(document)
        inventory_sha = sha256_bytes(inventory)
        body: dict[str, JsonValue] = {
            **SOURCE_ACQUISITION.stamp(),
            "provider": collection["provider"],
            "collection_id": collection["collection_id"],
            "revision": collection["revision"],
            "inventory_sha256": inventory_sha,
            "input_inventory_sha256": input_sha,
            "archive_md5": collection["archive_md5"],
            "archive_sha256": archive_sha,
            "split_md5": split_md5,
            "split_sha256": split_sha,
            "videos": videos,
            "metadata_files": metadata_files,
        }
        record = seal(body)
        write_once(root / "inventory.json", inventory)
        path = root / "acquisition.json"
        status = write_once(path, canonical_json(record))
        digest = record["manifest_sha256"]
        assert isinstance(digest, str)
        result_status = "unchanged" if status == "unchanged" else "written"
        return AcquisitionResult(
            path,
            digest,
            result_status,
            InventoryResult(root / "inventory.json", result_status, document, inventory_sha),
        )
