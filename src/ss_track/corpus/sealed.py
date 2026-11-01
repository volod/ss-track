"""Canonical hashing and self-verifying JSON records."""

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile

from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode

SEAL_FIELD = "manifest_sha256"
READ_ONLY_FILE_MODE = 0o444
_CHUNK_BYTES = 1024 * 1024


def canonical_json(value: Mapping[str, JsonValue]) -> bytes:
    """Serialize one value to the single byte form that its hash covers."""
    text = json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True
    )
    return text.encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase SHA-256 of some bytes."""
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 of a file's bytes."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def copy_with_sha256(source: Path, target: Path) -> tuple[str, int]:
    """Copy a file and hash the bytes actually copied, so one read serves both."""
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as reader, target.open("xb") as writer:
        while chunk := reader.read(_CHUNK_BYTES):
            digest.update(chunk)
            writer.write(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def seal(body: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the record with a hash that covers every other field."""
    sealed = dict(body)
    sealed[SEAL_FIELD] = sha256_bytes(canonical_json(body))
    return sealed


def write_sealed(path: Path, sealed: Mapping[str, JsonValue]) -> None:
    """Write a read-only record so that a crash cannot leave a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(sealed, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
    with NamedTemporaryFile(
        "w", encoding="ascii", dir=path.parent, prefix=".incoming-", delete=False
    ) as handle:
        handle.write(payload + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary = Path(handle.name)
    temporary.chmod(READ_ONLY_FILE_MODE)
    temporary.replace(path)


def read_sealed(path: Path, kind: str) -> dict[str, JsonValue]:
    """Read a record and refuse it unless it is the expected kind and intact."""
    try:
        loaded = json.loads(path.read_text(encoding="ascii"))
    except FileNotFoundError as error:
        raise _tampered(path, "record is missing") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _tampered(path, f"record is not valid JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise _tampered(path, "record is not a JSON object")
    body = {key: value for key, value in loaded.items() if key != SEAL_FIELD}
    if body.get("kind") != kind:
        raise _tampered(path, f"record kind is not {kind}")
    if loaded.get(SEAL_FIELD) != sha256_bytes(canonical_json(body)):
        raise _tampered(path, "record content does not match its seal")
    return loaded


def _tampered(path: Path, message: str) -> CorpusRefusal:
    return CorpusRefusal(RefusalCode.RECORD_TAMPERED, message, {"record": path.name})
