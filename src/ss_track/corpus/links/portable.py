"""Export and unpack media-free link-review handoffs for independent local corpora."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.hosts.host_hashes import read_staged_hashes, record_staged_hashes
from ss_track.corpus.links.interactive_state import read_checkpoint
from ss_track.corpus.links.portable_archive import (
    CHECKPOINT_MEMBER,
    HASHES_MEMBER,
    LINKS_MEMBER,
    build_archive,
    extract_recipes,
    read_archive,
    recipe_members,
    write_archive,
)
from ss_track.corpus.links.portable_state import base_checkpoint, checkpoint_path, file_digest
from ss_track.corpus.links.records import read_links
from ss_track.corpus.storage.layout import links_path


@dataclass(frozen=True, slots=True)
class PortableResult:
    """One portable-review action reported through the existing command envelope."""

    status: str
    run_id: str
    corpus_id: str
    digest: str
    path: Path
    details: dict[str, JsonValue]

    def to_record(self) -> dict[str, object]:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "corpus_id": self.corpus_id,
            "manifest_sha256": self.digest,
            "manifest_path": str(self.path),
            "details": self.details,
        }


def export_handoff(
    data_root: Path,
    run_id: str,
    corpus_id: str,
    identity_run: str,
    expires_on: str,
    output: Path,
    recipes: list[Path],
    reviewer: str,
) -> PortableResult:
    """Export recipe inputs, identity evidence, links and checkpoint, but no dataset bytes."""
    if not recipes:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID, "portable review requires a local creation recipe"
        )
    links = read_links(data_root, run_id)
    if links["corpus_id"] != corpus_id:
        raise CorpusRefusal(RefusalCode.HASHES_NOT_COMPARABLE, "link run names another corpus")
    checkpoint = checkpoint_path(data_root, run_id)
    if checkpoint.exists():
        link_rows = cast(list[Mapping[str, Any]], links["links"])
        read_checkpoint(checkpoint, reviewer, link_rows)
    checkpoint_sha = file_digest(checkpoint)
    hashes_result = record_staged_hashes(corpus_id, identity_run, data_root)
    hashes = read_staged_hashes(hashes_result.record_path)
    if (
        links["corpus_manifest_sha256"] != hashes["corpus_manifest_sha256"]
        or links["frame_set_sha256"] != hashes["frame_set_sha256"]
    ):
        raise CorpusRefusal(RefusalCode.HASHES_NOT_COMPARABLE, "link and corpus identities differ")
    members = {
        LINKS_MEMBER: links_path(data_root, run_id).read_bytes(),
        HASHES_MEMBER: hashes_result.record_path.read_bytes(),
        **recipe_members(recipes),
    }
    if checkpoint_sha is not None:
        members[CHECKPOINT_MEMBER] = checkpoint.read_bytes()
    payload, manifest = build_archive(
        expires_on=expires_on,
        corpus_id=corpus_id,
        corpus_manifest_sha256=str(hashes["corpus_manifest_sha256"]),
        frame_set_sha256=str(hashes["frame_set_sha256"]),
        links_run_id=run_id,
        links_manifest_sha256=str(links[SEAL_FIELD]),
        base_checkpoint_sha256=base_checkpoint(data_root, run_id, checkpoint_sha),
        checkpoint_sha256=checkpoint_sha,
        members=members,
    )
    status = write_archive(output, payload)
    return PortableResult(
        status,
        run_id,
        corpus_id,
        str(manifest[SEAL_FIELD]),
        output,
        {"transfer_size_bytes": len(payload), "recipe_count": len(recipes)},
    )


def authorized(asserted: bool) -> None:
    """Require the operator assertion before opening a handoff."""
    if not asserted:
        raise CorpusRefusal(
            RefusalCode.RIGHTS_CONFLICT,
            "opening a review handoff requires an explicit authorization assertion",
        )


def unpack_handoff(archive_path: Path, output: Path, is_authorized: bool) -> PortableResult:
    """Extract only verified creation inputs so this host can build its own local corpus."""
    authorized(is_authorized)
    archive = read_archive(archive_path)
    count = extract_recipes(archive, output)
    manifest = archive.manifest
    return PortableResult(
        "exported",
        str(manifest["links_run_id"]),
        str(manifest["corpus_id"]),
        str(manifest[SEAL_FIELD]),
        output,
        {"transfer_size_bytes": archive_path.stat().st_size, "recipe_count": count},
    )
