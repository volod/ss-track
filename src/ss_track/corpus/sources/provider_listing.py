"""Enumerate pinned provider metadata without following untrusted pagination hosts."""

import json
import re
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources.provider_http import read_json
from ss_track.corpus.sources.provider_metadata import ProviderFile, hf_files, zenodo_archive

_NEXT = re.compile(r'<([^>]+)>\s*;\s*rel="next"')
_MAX_PAGES = 1000
_MAX_LISTING_BYTES = 128 * 1024 * 1024


def _invalid() -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.SOURCE_DAMAGED, "provider pagination is incomplete or unsafe")


def huggingface_listing(
    repository: str, revision: str, token: str | None
) -> dict[str, ProviderFile]:
    """Read every page of a dataset tree at a full commit."""
    base = f"https://huggingface.co/api/datasets/{repository}/tree/{revision}"
    url = f"{base}?recursive=true&expand=false"
    pages: list[Any] = []
    seen: set[str] = set()
    listing_bytes = 0
    for _ in range(_MAX_PAGES):
        if url in seen:
            raise _invalid()
        seen.add(url)
        data, link = read_json(url, token)
        listing_bytes += len(json.dumps(data, ensure_ascii=True))
        if listing_bytes > _MAX_LISTING_BYTES:
            raise _invalid()
        pages.append(data)
        if not link:
            return hf_files(pages)
        match = _NEXT.search(link)
        if match is None:
            raise _invalid()
        next_url = urljoin(url, match.group(1))
        parts = urlsplit(next_url)
        if (
            parts.scheme != "https"
            or parts.netloc != "huggingface.co"
            or parts.path != urlsplit(base).path
        ):
            raise _invalid()
        url = next_url
    raise _invalid()


def zenodo_listing(identity: str, revision: str, archive: str, md5: str) -> tuple[int, Any]:
    """Validate Zenodo's pinned record and its archive checksum."""
    url = f"https://zenodo.org/api/records/{identity}"
    record, _ = read_json(url)
    checked = record
    if (
        isinstance(record, dict)
        and isinstance(record.get("metadata"), dict)
        and record["metadata"].get("version") is None
    ):
        native = read_native_zenodo(url)
        versions = native.get("versions") if isinstance(native, dict) else None
        metadata = native.get("metadata") if isinstance(native, dict) else None
        if (
            not isinstance(native, dict)
            or str(native.get("id")) != identity
            or not isinstance(metadata, dict)
            or metadata.get("version") is not None
            or not isinstance(versions, dict)
            or type(versions.get("index")) is not int
            or versions["index"] < 1
        ):
            raise _invalid()
        checked = {
            **record,
            "metadata": {**record["metadata"], "version": f"v{versions['index']}"},
        }
    return zenodo_archive(checked, identity, revision, archive, md5), record


def read_native_zenodo(url: str) -> Any:
    """Read the native record when the legacy representation has no version label."""
    record, _ = read_json(url, accept="application/vnd.inveniordm.v1+json")
    return record


def huggingface_url(repository: str, revision: str, path: str) -> str:
    """Construct a commit-pinned file URL from validated repository and path."""
    return (
        f"https://huggingface.co/datasets/{repository}/resolve/{revision}/{quote(path, safe='/')}"
    )


def zenodo_url(identity: str, path: str) -> str:
    """Construct a version-specific Zenodo file URL."""
    return f"https://zenodo.org/records/{identity}/files/{quote(path, safe='/')}"
