"""Verify WetlandBirds split metadata and join it to enumerated archive paths."""

import re
from pathlib import Path, PurePosixPath
from typing import Any

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources.provider_http import download, parse_json
from ss_track.corpus.sources.provider_listing import zenodo_url

_MAX_SPLITS_BYTES = 1024 * 1024
_MD5 = re.compile(r"^md5:([0-9a-f]{32})$")


def _invalid() -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.SOURCE_DAMAGED, "Zenodo split metadata is incomplete or mismatched"
    )


def split_file(record: Any) -> tuple[int, str] | None:
    """Return verified metadata for splits.json, or None if no such file is published."""
    entries = [
        item
        for item in record["files"]
        if isinstance(item, dict) and item.get("key") == "splits.json"
    ]
    if not entries:
        return None
    if len(entries) != 1:
        raise _invalid()
    size, checksum = entries[0].get("size"), entries[0].get("checksum")
    if type(size) is not int or not 0 < size <= _MAX_SPLITS_BYTES or not isinstance(checksum, str):
        raise _invalid()
    match = _MD5.fullmatch(checksum)
    if match is None:
        raise _invalid()
    return size, match.group(1)


def _mapping(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise _invalid()
    result: dict[str, str] = {}
    for split, names in payload.items():
        if split not in ("train_set", "val_set", "test_set") or not isinstance(names, list):
            raise _invalid()
        for name in names:
            if not isinstance(name, str) or not name.isascii() or name in result or not name:
                raise _invalid()
            result[name] = split
    return result


def apply_splits(collection: dict[str, Any], path: Path) -> None:
    """Join split names by unique archive video stem, refusing mismatches and ambiguity."""
    try:
        mapping = _mapping(parse_json(path.read_bytes()))
    except (ValueError, OSError) as error:
        raise _invalid() from error
    stems: dict[str, dict[str, Any]] = {}
    for video in collection["videos"]:
        stem = PurePosixPath(video["path"]).stem
        if stem in stems:
            raise _invalid()
        stems[stem] = video
    if not mapping.keys() <= stems.keys():
        raise _invalid()
    for stem, split in mapping.items():
        video = stems[stem]
        if video["upstream_split"] is not None and video["upstream_split"] != split:
            raise _invalid()
        video["upstream_split"] = split


def fetch_splits(
    collection: dict[str, Any], record: Any, target: Path, scratch: Path
) -> tuple[int, str | None, str | None]:
    """Fetch and verify an optional split file before joining its claims."""
    info = split_file(record)
    if info is None:
        return 0, None, None
    size, md5 = info
    digest = download(
        zenodo_url(collection["collection_id"], "splits.json"),
        target,
        size,
        "md5",
        md5,
        scratch=scratch,
    )
    return size, md5, digest
