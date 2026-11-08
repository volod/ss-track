"""Bounded provider HTTP operations; never include credentials or URLs in errors."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.core.strict_json import finite_float, reject_constant, unique_object

_CHUNK = 1024 * 1024
_METADATA_LIMIT = 16 * _CHUNK
_TIMEOUT = 120


class _SafeRedirect(HTTPRedirectHandler):
    """Do not send provider credentials to a different host or a non-HTTPS URL."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        target = urlsplit(newurl)
        if target.scheme != "https" or target.username or target.password:
            raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "provider redirect is unsafe")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and target.netloc != urlsplit(req.full_url).netloc:
            redirected.remove_header("Authorization")
        return redirected


def _request(url: str, token: str | None) -> Any:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "provider URL is unsafe")
    headers = {"User-Agent": "ss-track-source-acquisition/1.0"}
    if token and parsed.hostname == "huggingface.co":
        headers["Authorization"] = f"Bearer {token}"
    try:
        return build_opener(_SafeRedirect()).open(Request(url, headers=headers), timeout=_TIMEOUT)
    except (HTTPError, URLError, OSError, ValueError) as error:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "provider request failed") from error


def parse_json(payload: bytes) -> Any:
    """Decode JSON without silently discarding duplicate keys or non-finite numbers."""
    return json.loads(
        payload,
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
        parse_float=finite_float,
    )


def read_json(url: str, token: str | None = None) -> tuple[Any, str | None]:
    """Fetch one bounded JSON page and return its next-page Link header."""
    try:
        with _request(url, token) as response:
            data = response.read(_METADATA_LIMIT + 1)
            if len(data) > _METADATA_LIMIT:
                raise CorpusRefusal(RefusalCode.SOURCE_DAMAGED, "provider metadata exceeds limit")
            return parse_json(data), response.headers.get("Link")
    except (OSError, ValueError) as error:
        raise CorpusRefusal(
            RefusalCode.SOURCE_UNREADABLE, "provider metadata could not be read"
        ) from error


def download(
    url: str,
    target: Path,
    size: int,
    algorithm: str,
    expected: str,
    token: str | None = None,
    *,
    scratch: Path | None = None,
) -> str:
    """Download exact bytes to a temporary file and publish without replacing existing files."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "download destination is a symbolic link")
    if target.exists():
        return verify(target, size, algorithm, expected)
    fd, temporary = tempfile.mkstemp(prefix=".incoming-", dir=scratch or target.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as output, _request(url, token) as response:
            count = 0
            while chunk := response.read(_CHUNK):
                count += len(chunk)
                if count > size:
                    raise CorpusRefusal(
                        RefusalCode.SOURCE_HASH_MISMATCH, "download exceeds declared size"
                    )
                output.write(chunk)
        digest = verify(temporary_path, size, algorithm, expected)
        try:
            os.link(temporary_path, target)
        except FileExistsError:
            return verify(target, size, algorithm, expected)
        return digest
    except (OSError, URLError) as error:
        raise CorpusRefusal(RefusalCode.SOURCE_UNREADABLE, "provider download failed") from error
    finally:
        temporary_path.unlink(missing_ok=True)


def verify(path: Path, size: int, algorithm: str, expected: str) -> str:
    """Verify exact length and upstream digest, returning the local SHA-256."""
    upstream = hashlib.new("sha1" if algorithm == "git-sha1" else algorithm, usedforsecurity=False)
    if algorithm == "git-sha1":
        upstream.update(f"blob {size}\0".encode("ascii"))
    local = hashlib.sha256()
    count = 0
    with path.open("rb") as source:
        while chunk := source.read(_CHUNK):
            count += len(chunk)
            if count > size:
                break
            upstream.update(chunk)
            local.update(chunk)
    if count != size or upstream.hexdigest() != expected:
        raise CorpusRefusal(
            RefusalCode.SOURCE_HASH_MISMATCH, "downloaded bytes do not match upstream"
        )
    return local.hexdigest()
