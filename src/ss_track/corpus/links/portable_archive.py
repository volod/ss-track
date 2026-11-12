"""Deterministic, media-free archives for portable recording-link review."""

import io
import tarfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import cast

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.kinds import LINK_REVIEW_HANDOFF
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import seal
from ss_track.corpus.storage.scratch import write_atomically

MANIFEST_MEMBER = "manifest.json"
LINKS_MEMBER = "records/links.json"
HASHES_MEMBER = "records/staged-hashes.json"
CHECKPOINT_MEMBER = "checkpoint/decisions.yaml"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
RECIPE_SUFFIXES = frozenset({".csv", ".json", ".md", ".toml", ".txt", ".yaml", ".yml"})


@dataclass(frozen=True, slots=True)
class PortableArchive:
    """A verified handoff manifest and its exact member bytes."""

    manifest: dict[str, JsonValue]
    members: dict[str, bytes]


def _refuse(message: str, details: dict[str, JsonValue] | None = None) -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.RECORD_TAMPERED, message, details)


def _member(path: str, role: str, payload: bytes) -> dict[str, JsonValue]:
    return {"path": path, "role": role, "size": len(payload), "sha256": sha256_bytes(payload)}


def recipe_members(paths: list[Path]) -> dict[str, bytes]:
    """Read operator-selected creation inputs under stable archive names."""
    members: dict[str, bytes] = {}
    names: set[str] = set()
    for position, path in enumerate(paths, 1):
        if not path.is_file() or path.is_symlink():
            raise CorpusRefusal(
                RefusalCode.SOURCE_NOT_FOUND,
                "review recipe is not a regular file",
                {"path": str(path)},
            )
        if path.suffix.lower() not in RECIPE_SUFFIXES:
            raise CorpusRefusal(
                RefusalCode.MANIFEST_INVALID,
                "review recipes must be text declarations or metadata, not media or weights",
                {"path": str(path)},
            )
        name = path.name
        if name in names:
            raise CorpusRefusal(
                RefusalCode.MANIFEST_INVALID,
                "review recipe basenames must be unique",
                {"name": name},
            )
        names.add(name)
        payload = path.read_bytes()
        if len(payload) > MAX_MEMBER_BYTES:
            raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "review recipe is too large")
        members[f"recipes/{position:03d}-{name}"] = payload
    return members


def build_archive(
    *,
    expires_on: str,
    corpus_id: str,
    corpus_manifest_sha256: str,
    frame_set_sha256: str,
    links_run_id: str,
    links_manifest_sha256: str,
    base_checkpoint_sha256: str | None,
    checkpoint_sha256: str | None,
    members: dict[str, bytes],
) -> tuple[bytes, dict[str, JsonValue]]:
    """Return deterministic tar bytes and their sealed interchange manifest."""
    roles = {
        LINKS_MEMBER: "links",
        HASHES_MEMBER: "staged_hashes",
        CHECKPOINT_MEMBER: "checkpoint",
    }
    files: list[JsonValue] = [
        _member(path, roles.get(path, "recipe"), payload)
        for path, payload in sorted(members.items())
    ]
    manifest = seal(
        {
            **LINK_REVIEW_HANDOFF.stamp(),
            "expires_on": expires_on,
            "corpus_id": corpus_id,
            "corpus_manifest_sha256": corpus_manifest_sha256,
            "frame_set_sha256": frame_set_sha256,
            "links_run_id": links_run_id,
            "links_manifest_sha256": links_manifest_sha256,
            "base_checkpoint_sha256": base_checkpoint_sha256,
            "checkpoint_sha256": checkpoint_sha256,
            "files": files,
        }
    )
    payloads = {MANIFEST_MEMBER: canonical_json(manifest), **members}
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, payload in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o600
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    archive_bytes = stream.getvalue()
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "review handoff is too large")
    return archive_bytes, manifest


def write_archive(path: Path, payload: bytes) -> str:
    """Publish one archive atomically, refusing a different existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_file() and not path.is_symlink() and path.read_bytes() == payload:
            return "unchanged"
        raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "archive path already holds other bytes")
    write_atomically(path, payload, mode=0o600)
    return "exported"


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and str(path) == name


def _read_manifest(payload: bytes) -> dict[str, JsonValue]:
    with TemporaryDirectory(prefix="ss-track-handoff-") as directory:
        path = Path(directory) / MANIFEST_MEMBER
        path.write_bytes(payload)
        return read_sealed(path, LINK_REVIEW_HANDOFF)


def _read_members(path: Path) -> dict[str, bytes]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise _refuse("handoff archive is missing, symbolic or too large")
    found: dict[str, bytes] = {}
    try:
        with tarfile.open(path, mode="r:") as archive:
            for info in archive:
                if not info.isfile() or not _safe_name(info.name) or info.name in found:
                    raise _refuse("handoff archive has an unsafe or duplicate member")
                if info.size > MAX_MEMBER_BYTES:
                    raise _refuse("handoff archive member is too large", {"path": info.name})
                handle = archive.extractfile(info)
                if handle is None:
                    raise _refuse("handoff archive member cannot be read", {"path": info.name})
                found[info.name] = handle.read()
    except (tarfile.TarError, EOFError) as error:
        raise _refuse("handoff archive is not a complete tar file") from error
    return found


def _verify_file_table(
    rows: list[dict[str, JsonValue]], members: dict[str, bytes]
) -> dict[str, str]:
    expected = {str(row["path"]): (int(cast(int, row["size"])), str(row["sha256"])) for row in rows}
    if len(expected) != len(rows):
        raise _refuse("handoff file list repeats a path")
    actual = {name: (len(payload), sha256_bytes(payload)) for name, payload in members.items()}
    if expected != actual:
        raise _refuse("handoff archive members do not match its manifest")
    roles = {str(row["path"]): str(row["role"]) for row in rows}
    if rows != sorted(rows, key=lambda row: str(row["path"])):
        raise _refuse("handoff file list is not sorted")
    return roles


def _verify_roles(roles: dict[str, str], manifest: dict[str, JsonValue]) -> None:
    if list(roles.values()).count("links") != 1 or list(roles.values()).count("staged_hashes") != 1:
        raise _refuse("handoff must contain one links and one staged-hashes record")
    if roles.get(LINKS_MEMBER) != "links" or roles.get(HASHES_MEMBER) != "staged_hashes":
        raise _refuse("handoff record members are not at their fixed paths")
    checkpoint_count = list(roles.values()).count("checkpoint")
    if checkpoint_count > 1:
        raise _refuse("handoff repeats its checkpoint")
    checkpoint_present = checkpoint_count == 1
    if checkpoint_present != (manifest["checkpoint_sha256"] is not None):
        raise _refuse("handoff checkpoint fields disagree")
    if checkpoint_present and roles.get(CHECKPOINT_MEMBER) != "checkpoint":
        raise _refuse("handoff checkpoint is not at its fixed path")
    if any(
        role == "recipe"
        and (
            not path.startswith("recipes/")
            or len(Path(path).name) < 5
            or not Path(path).name[:3].isdigit()
            or Path(path).name[3] != "-"
            or Path(path).suffix.lower() not in RECIPE_SUFFIXES
        )
        for path, role in roles.items()
    ):
        raise _refuse("handoff recipe member is not at a generated recipe path")


def _verify_expiry(manifest: dict[str, JsonValue], today: date | None) -> None:
    try:
        expiry = date.fromisoformat(str(manifest["expires_on"]))
    except ValueError as error:
        raise _refuse("handoff expiry is not a calendar date") from error
    if expiry < (today or date.today()):
        raise CorpusRefusal(RefusalCode.RETENTION_EXPIRED, "review handoff has expired")


def read_archive(path: Path, *, today: date | None = None) -> PortableArchive:
    """Read, verify and expiry-check a portable handoff without extracting it."""
    members = _read_members(path)
    manifest_payload = members.pop(MANIFEST_MEMBER, None)
    if manifest_payload is None:
        raise _refuse("handoff archive omits manifest.json")
    manifest = _read_manifest(manifest_payload)
    rows = cast(list[dict[str, JsonValue]], manifest["files"])
    _verify_roles(_verify_file_table(rows, members), manifest)
    _verify_expiry(manifest, today)
    return PortableArchive(manifest, members)


def extract_recipes(archive: PortableArchive, output: Path) -> int:
    """Write verified recipe members into a new directory without media extraction."""
    rows = cast(list[dict[str, JsonValue]], archive.manifest["files"])
    recipes = [
        (str(row["path"]), archive.members[str(row["path"])])
        for row in rows
        if row["role"] == "recipe"
    ]
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise CorpusRefusal(RefusalCode.CORPUS_CONFLICT, "recipe output path is not empty")
    output.mkdir(parents=True, exist_ok=True)
    for name, payload in recipes:
        archived_name = Path(name).name
        write_atomically(output / archived_name[4:], payload, mode=0o600)
    return len(recipes)
