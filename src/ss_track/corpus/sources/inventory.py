"""Read, check and normalize an operator's upstream video source inventory."""

import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import CorpusRefusal
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.review.export import write_once
from ss_track.schema.validation.enforce import read_declaration

CONTRACT = "declaration/source-inventory"
_VERSION = 1
_HF_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_HF_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_ZENODO_ID = re.compile(r"^[1-9][0-9]*$")
_ZENODO_REVISION = re.compile(r"^v[1-9][0-9]*$")
_SECRET = re.compile(
    r"(?i)(hf_[A-Za-z0-9]{12,}|bearer\s+\S+|(?:token|password|secret|api[_-]?key)\s*[=:]\s*\S+)"
)
_FACTS = (
    "source_reference",
    "annotation_reference",
    "upstream_split",
    "attribution",
    "terms",
    "terms_reference",
)


def _text(value: object) -> None:
    if value is None:
        return
    if (
        not isinstance(value, str)
        or not value.strip()
        or not value.isascii()
        or _SECRET.search(value)
    ):
        raise invalid("inventory contains invalid text or a credential")
    if "://" in value:
        try:
            url = urlsplit(value)
        except ValueError as error:
            raise invalid("inventory reference is not a valid URL") from error
        if url.query or url.fragment or url.username or url.password:
            raise invalid("inventory references cannot contain credentials, queries or fragments")


def _path(value: str) -> None:
    _text(value)
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "\\" in value
        or any(part in (".", "..") for part in value.split("/"))
        or str(path) != value
    ):
        raise invalid("inventory paths must be normalized relative paths")


def _video(item: dict[str, Any]) -> None:
    for value in item.values():
        _text(value)
    _path(item["path"])
    if (item["status"] == "excluded") != (item["exclusion_reason"] is not None):
        raise invalid("only excluded videos must state an exclusion reason")


def _collection(item: dict[str, Any]) -> None:
    for key in ("provider", "collection_id", "revision", "archive_path", "archive_md5"):
        _text(item[key])
    provider, identity, revision = item["provider"], item["collection_id"], item["revision"]
    if provider == "huggingface":
        if not _HF_REPO.fullmatch(identity) or not _HF_COMMIT.fullmatch(revision):
            raise invalid("Hugging Face inventory requires a dataset id and full commit")
        if item["archive_path"] is not None or item["archive_md5"] is not None:
            raise invalid("Hugging Face inventories do not declare a Zenodo archive")
    elif not _ZENODO_ID.fullmatch(identity) or not _ZENODO_REVISION.fullmatch(revision):
        raise invalid("Zenodo inventory requires a numeric record id and numbered version")
    if item["archive_path"] is not None:
        _path(item["archive_path"])
    seen: set[str] = set()
    for video in item["videos"]:
        _video(video)
        path = video["path"]
        if path in seen:
            raise invalid("inventory repeats a video path within a collection")
        seen.add(path)
    item["videos"].sort(key=lambda video: video["path"])


def read_inventory(path: Path) -> dict[str, Any]:
    """Validate an inventory and normalize its ordering; never echo malformed inputs."""
    try:
        document = read_declaration(path, CONTRACT, _VERSION)
    except CorpusRefusal as error:
        raise invalid(
            "source inventory could not be read or does not conform to its contract"
        ) from error
    seen: set[tuple[str, str]] = set()
    for item in document["collections"]:
        _collection(item)
        key = (item["provider"], item["collection_id"])
        if key in seen:
            raise invalid("inventory repeats a collection")
        seen.add(key)
    document["collections"].sort(key=lambda item: (item["provider"], item["collection_id"]))
    return document


class InventoryResult:
    """The normalized inventory path, digest and unresolved-fact counts."""

    def __init__(self, path: Path, status: str, document: dict[str, Any], digest: str) -> None:
        self.path = path
        self.status = status
        self.document = document
        self.digest = digest

    def to_record(self) -> dict[str, Any]:
        """State counts without echoing upstream metadata."""
        videos = [video for item in self.document["collections"] for video in item["videos"]]
        statuses = Counter(video["status"] for video in videos)
        counts = {name: statuses[name] for name in ("candidate", "excluded", "unknown")}
        counts.update({field: sum(video[field] is None for video in videos) for field in _FACTS})
        counts["unresolved_zenodo_archive"] = sum(
            item["archive_path"] is None or item["archive_md5"] is None
            for item in self.document["collections"]
            if item["provider"] == "zenodo"
        )
        return {
            "status": self.status,
            "source_inventory": {
                **counts,
                "path": str(self.path),
                "sha256": self.digest,
                "collection_count": len(self.document["collections"]),
                "video_count": len(videos),
            },
        }


def inventory_sources(path: Path, out: Path) -> InventoryResult:
    """Write a canonical declaration once, without acquiring video or granting approval."""
    document = read_inventory(path)
    payload = canonical_json(document)
    return InventoryResult(out, write_once(out, payload), document, sha256_bytes(payload))
