"""Compare a local corpus and safely install a portable review handoff."""

from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from ss_track.core.canonical import SEAL_FIELD, sha256_bytes
from ss_track.core.evidence.sealing import write_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import exclusive_lock, write_atomically
from ss_track.corpus.hosts.hash_comparison import compare_staged_hashes
from ss_track.corpus.hosts.host_hashes import read_staged_hashes, record_staged_hashes
from ss_track.corpus.links.interactive_state import read_checkpoint
from ss_track.corpus.links.portable import PortableResult, authorized
from ss_track.corpus.links.portable_archive import (
    CHECKPOINT_MEMBER,
    HASHES_MEMBER,
    LINKS_MEMBER,
    PortableArchive,
    read_archive,
)
from ss_track.corpus.links.portable_state import accepted_path, checkpoint_path, file_digest
from ss_track.corpus.links.records import read_links
from ss_track.corpus.storage.layout import links_path


def _temporary_records(archive: PortableArchive, directory: Path) -> tuple[Path, Path]:
    links = directory / LINKS_MEMBER
    hashes = directory / HASHES_MEMBER
    links.parent.mkdir(parents=True)
    links.write_bytes(archive.members[LINKS_MEMBER])
    hashes.write_bytes(archive.members[HASHES_MEMBER])
    return links, hashes


def _verify_archive_records(
    archive: PortableArchive, directory: Path
) -> tuple[dict[str, JsonValue], Path]:
    links_file, hashes_file = _temporary_records(archive, directory)
    temporary_root = directory / "data"
    target = links_path(temporary_root, str(archive.manifest["links_run_id"]))
    target.parent.mkdir(parents=True)
    target.write_bytes(links_file.read_bytes())
    links = read_links(temporary_root, str(archive.manifest["links_run_id"]))
    hashes = read_staged_hashes(hashes_file)
    manifest = archive.manifest
    if (
        links[SEAL_FIELD] != manifest["links_manifest_sha256"]
        or links["corpus_id"] != manifest["corpus_id"]
        or links["corpus_manifest_sha256"] != manifest["corpus_manifest_sha256"]
        or links["frame_set_sha256"] != manifest["frame_set_sha256"]
        or hashes["corpus_id"] != manifest["corpus_id"]
        or hashes["corpus_manifest_sha256"] != manifest["corpus_manifest_sha256"]
        or hashes["frame_set_sha256"] != manifest["frame_set_sha256"]
    ):
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "handoff records disagree on identity")
    return links, hashes_file


def _verify_checkpoint(
    archive: PortableArchive, directory: Path, reviewer: str, links: dict[str, JsonValue]
) -> None:
    payload = archive.members.get(CHECKPOINT_MEMBER)
    if payload is None:
        return
    path = directory / CHECKPOINT_MEMBER
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    if sha256_bytes(payload) != archive.manifest["checkpoint_sha256"]:
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "checkpoint identity differs")
    link_rows = cast(list[Mapping[str, Any]], links["links"])
    read_checkpoint(path, reviewer, link_rows)


def _install_checkpoint(archive: PortableArchive, checkpoint: Path) -> str:
    current = file_digest(checkpoint)
    base = archive.manifest["base_checkpoint_sha256"]
    proposed = archive.manifest["checkpoint_sha256"]
    if current == proposed:
        return "unchanged"
    initial_copy = current is None and base == proposed
    if current != base and not initial_copy:
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT,
            "local and returned review checkpoints diverged from their common base",
        )
    payload = archive.members.get(CHECKPOINT_MEMBER)
    if payload is None:
        return "unchanged"
    checkpoint.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    write_atomically(checkpoint, payload, mode=0o600)
    return "updated"


def _install_handoff(archive: PortableArchive, data_root: Path, links: dict[str, JsonValue]) -> str:
    run_id = str(archive.manifest["links_run_id"])
    target = links_path(data_root, run_id)
    run_directory = target.parent
    with exclusive_lock(run_directory, ".portable.lock"):
        if target.exists():
            existing = read_links(data_root, run_id)
            if existing[SEAL_FIELD] != links[SEAL_FIELD]:
                raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "local link run differs")
        else:
            other = [path for path in run_directory.iterdir() if path.name != ".portable.lock"]
            if other:
                raise CorpusRefusal(
                    RefusalCode.CORPUS_CONFLICT,
                    "link run id is already used by another local run",
                )
            write_sealed(target, links)
        checkpoint_status = _install_checkpoint(archive, checkpoint_path(data_root, run_id))
        accepted = accepted_path(data_root, run_id)
        accepted.parent.mkdir(parents=True, exist_ok=True)
        write_sealed(accepted, archive.manifest)
    return checkpoint_status


def accept_handoff(
    data_root: Path,
    archive_path: Path,
    identity_run: str,
    comparison_run: str,
    reviewer: str,
    is_authorized: bool,
) -> PortableResult:
    """Compare a locally created corpus, then safely accept links and checkpoint state."""
    authorized(is_authorized)
    archive = read_archive(archive_path)
    corpus_id = str(archive.manifest["corpus_id"])
    with TemporaryDirectory(prefix="ss-track-handoff-") as directory_name:
        directory = Path(directory_name)
        links, remote_hashes = _verify_archive_records(archive, directory)
        _verify_checkpoint(archive, directory, reviewer, links)
        local = record_staged_hashes(corpus_id, identity_run, data_root)
        comparison = compare_staged_hashes(
            local.record_path, remote_hashes, comparison_run, data_root
        )
    checkpoint_status = _install_handoff(archive, data_root, links)
    return PortableResult(
        "identical",
        str(archive.manifest["links_run_id"]),
        corpus_id,
        str(archive.manifest[SEAL_FIELD]),
        comparison.record_path,
        {
            "transfer_size_bytes": archive_path.stat().st_size,
            "checkpoint_status": checkpoint_status,
        },
    )
