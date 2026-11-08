"""Prepare one combined pool from acquired collections.

The command writes ordinary recording and corpus declarations. Later versions and cases follow the
source each recording imports, whose origin list names every collection the bytes came from.
"""

from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.records.kinds import CORPUS_POOL
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import write_sealed
from ss_track.corpus.review.export import write_once
from ss_track.corpus.sources.metadata_claims import Evidence, Unresolved
from ss_track.corpus.sources.metadata_join import join_metadata
from ss_track.corpus.sources.pool_emit import PoolDocuments, emit
from ss_track.corpus.sources.pool_group import Selected, group_selected
from ss_track.corpus.sources.pool_load import LoadedCollection, LoadedPool, LoadedVideo, load_pool
from ss_track.corpus.storage.layout import (
    POOL_RECORDINGS_DIRECTORY,
    pool_corpus_path,
    pool_directory,
    pool_record_path,
    pool_recording_path,
)
from ss_track.corpus.storage.scratch import exclusive_lock
from ss_track.schema.validation.enforce import is_shared_type

_LOCKED = frozenset({"locked", "test", "test_set"})
WRITTEN = "written"
UNCHANGED = "unchanged"


class PoolResult:
    """Where one combined pool was written, or that the same declaration was already there."""

    def __init__(self, status: str, run_id: str, corpus_id: str, path: Path, digest: str) -> None:
        self.status = status
        self.run_id = run_id
        self.corpus_id = corpus_id
        self.path = path
        self.digest = digest

    def to_record(self) -> dict[str, object]:
        """Return the command result. The sealed pool record holds the selection itself."""
        return {
            "status": self.status,
            "run_id": self.run_id,
            "corpus_id": self.corpus_id,
            "manifest_path": str(self.path),
            "manifest_sha256": self.digest,
        }


def prepare_pool(path: Path, run_id: str, data_root: Path) -> PoolResult:
    """Prepare a combined pool, or report the one this declaration already published."""
    if not is_shared_type("identifier", run_id):
        raise invalid("run id is not an identifier")
    loaded = load_pool(path, data_root)
    if loaded.run_id != run_id:
        raise invalid("declaration run id does not match the command")
    if run_id in {item.run_id for item in loaded.collections}:
        raise invalid("pool run id must differ from acquisition run ids")
    evidence, unresolved = _evidence(loaded)
    documents = emit(
        loaded, *group_selected(_selected(loaded, evidence), loaded.related), unresolved
    )
    return _publish(loaded, documents, data_root)


def _evidence(pool: LoadedPool) -> tuple[dict[str, dict[str, Evidence]], list[Unresolved]]:
    found: dict[str, dict[str, Evidence]] = {}
    pending: list[Unresolved] = []
    for collection in pool.collections:
        evidence, unresolved = join_metadata(collection.acquired_sources, collection.metadata)
        found[collection.run_id] = evidence
        selected = {video.path for video in collection.videos}
        pending.extend(
            item for item in unresolved if item.kind != "conflicting_claim" or item.path in selected
        )
        pending.extend(_inventory_conflicts(collection, evidence))
    return found, pending


def _inventory_conflicts(
    collection: LoadedCollection, evidence: dict[str, Evidence]
) -> list[Unresolved]:
    found = []
    for video in collection.videos:
        claims = evidence.get(video.path, Evidence.missing())
        found.extend(_one_conflict(video, claims))
    return found


def _one_conflict(video: LoadedVideo, claims: Evidence) -> list[Unresolved]:
    found = []
    if _disagrees(video.source_reference, claims.source_reference):
        detail = (
            f"{video.path} source_reference inventory={video.source_reference} "
            f"metadata={claims.source_reference}"
        )
        found.append(Unresolved("conflicting_claim", video.path, detail))
    if _disagrees(video.annotation_reference, claims.annotation_reference):
        detail = (
            f"{video.path} annotation_reference inventory={video.annotation_reference} "
            f"metadata={claims.annotation_reference}"
        )
        found.append(Unresolved("conflicting_claim", video.path, detail))
    return found


def _disagrees(inventory: str | None, metadata: str | None) -> bool:
    return inventory is not None and metadata is not None and inventory != metadata


def _selected(pool: LoadedPool, evidence: dict[str, dict[str, Evidence]]) -> tuple[Selected, ...]:
    return tuple(
        _one(collection, video, evidence[collection.run_id].get(video.path, Evidence.missing()))
        for collection in pool.collections
        for video in collection.videos
    )


def _one(collection: LoadedCollection, video: LoadedVideo, claims: Evidence) -> Selected:
    association = _association(video, claims)
    source_blocked = "source_reference" in claims.conflicted or _disagrees(
        video.source_reference, claims.source_reference
    )
    annotation_blocked = "annotation_reference" in claims.conflicted or _disagrees(
        video.annotation_reference, claims.annotation_reference
    )
    block = (
        "locked"
        if video.upstream_split in _LOCKED
        else "conflict"
        if association == "conflict"
        else None
    )
    return Selected(
        collection.run_id,
        video.path,
        collection.provider,
        collection.collection_id,
        collection.provider_version,
        video.content_sha256,
        video.local_path,
        video.split,
        video.upstream_split,
        None if source_blocked else _filled(claims.source_reference, video.source_reference),
        None
        if annotation_blocked
        else _filled(claims.annotation_reference, video.annotation_reference),
        video.attribution,
        video.terms,
        video.terms_reference,
        None if "license" in claims.conflicted else claims.license_name,
        None if "license" in claims.conflicted else claims.license_reference,
        None if claims.conflicted else claims.metadata_sha256,
        association,
        block,
        dict(collection.rights),
        dict(collection.sensitivity),
    )


def _association(video: LoadedVideo, claims: Evidence) -> str:
    if claims.association == "conflict" or _disagrees(
        video.source_reference, claims.source_reference
    ):
        return "conflict"
    if _disagrees(video.annotation_reference, claims.annotation_reference):
        return "conflict"
    return claims.association


def _filled(metadata: str | None, inventory: str | None) -> str | None:
    return metadata if metadata is not None else inventory


def _publish(pool: LoadedPool, documents: PoolDocuments, data_root: Path) -> PoolResult:
    root = pool_directory(data_root, pool.run_id)
    if (root / "acquisition.json").is_file():
        raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "run already holds an acquisition")
    expected = _expected(data_root, pool.run_id, documents)
    with exclusive_lock(root, ".pool.lock"):
        if (root / "acquisition.json").is_file():
            raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "run already holds an acquisition")
        record_path = pool_record_path(data_root, pool.run_id)
        if record_path.exists():
            _require_same(root, record_path, documents.record, expected)
            status = UNCHANGED
        else:
            for path, payload in expected.items():
                write_once(path, payload)
            write_sealed(record_path, documents.record)
            status = WRITTEN
    digest = documents.record["manifest_sha256"]
    assert isinstance(digest, str)
    return PoolResult(status, pool.run_id, pool.corpus_id, record_path, digest)


def _expected(data_root: Path, run_id: str, documents: PoolDocuments) -> dict[Path, bytes]:
    files = {pool_corpus_path(data_root, run_id): documents.corpus}
    files.update(
        {
            pool_recording_path(data_root, run_id, stream_id): payload
            for stream_id, payload in documents.recordings
        }
    )
    return files


def _require_same(
    root: Path, record_path: Path, record: dict[str, JsonValue], expected: dict[Path, bytes]
) -> None:
    if read_sealed(record_path, CORPUS_POOL) != record:
        raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "run already holds a different pool")
    for path, payload in expected.items():
        if not path.is_file() or path.read_bytes() != payload:
            raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "run already holds a different pool")
    directory = root / POOL_RECORDINGS_DIRECTORY
    found = set(directory.glob("*.yaml")) if directory.is_dir() else set()
    wanted = {path for path in expected if path.parent == directory}
    if found != wanted:
        raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "run already holds a different pool")
