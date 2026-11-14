"""Validate provider file listings before any selected media is acquired."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources.inventory import _path

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_VIDEO_EXTENSIONS = frozenset({".avi", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"})


@dataclass(frozen=True, slots=True)
class ProviderFile:
    """A pinned upstream file's path, byte count and object digests."""

    path: str
    size: int
    git_oid: str
    sha256: str | None


def is_video(path: str) -> bool:
    """Recognize supported video filename extensions without inferring file contents."""
    return PurePosixPath(path).suffix.lower() in _VIDEO_EXTENSIONS


def _invalid() -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.SOURCE_DAMAGED, "provider metadata is incomplete or invalid")


def _hf_file(entry: dict[str, Any], path: str) -> ProviderFile:
    size, oid = entry.get("size"), entry.get("oid")
    if type(size) is not int or size < 0 or not isinstance(oid, str) or not _HEX40.fullmatch(oid):
        raise _invalid()
    return ProviderFile(path, size, oid, _lfs_digest(entry.get("lfs"), size))


def _lfs_digest(lfs: Any, size: int) -> str | None:
    if lfs is None:
        return None
    if not isinstance(lfs, dict) or not isinstance(lfs.get("oid"), str):
        raise _invalid()
    digest: str = lfs["oid"].removeprefix("sha256:")
    if not _HEX64.fullmatch(digest) or lfs.get("size") != size:
        raise _invalid()
    return digest


def _add_hf_entry(files: dict[str, ProviderFile], entry: Any) -> None:
    if not isinstance(entry, dict) or entry.get("type") not in ("file", "directory"):
        raise _invalid()
    path = entry.get("path")
    if not isinstance(path, str):
        raise _invalid()
    _path(path)
    if entry["type"] == "directory":
        return
    if path in files:
        raise _invalid()
    files[path] = _hf_file(entry, path)


def hf_files(pages: list[Any]) -> dict[str, ProviderFile]:
    """Validate complete Hugging Face tree pages, including Git and LFS object identity."""
    files: dict[str, ProviderFile] = {}
    for page in pages:
        if not isinstance(page, list):
            raise _invalid()
        for entry in page:
            _add_hf_entry(files, entry)
    return files


def zenodo_archive(record: Any, record_id: str, revision: str, name: str, md5: str) -> int:
    """Verify a pinned Zenodo record and return its published archive byte count."""
    if not isinstance(record, dict) or str(record.get("id")) != record_id:
        raise _invalid()
    metadata = record.get("metadata")
    files = record.get("files")
    if not isinstance(metadata, dict) or metadata.get("version") != revision:
        raise _invalid()
    if not isinstance(files, list):
        raise _invalid()
    matches = [item for item in files if isinstance(item, dict) and item.get("key") == name]
    if len(matches) != 1:
        raise _invalid()
    item = matches[0]
    size = item.get("size")
    if item.get("checksum") != f"md5:{md5}" or type(size) is not int or size <= 0:
        raise _invalid()
    return size
