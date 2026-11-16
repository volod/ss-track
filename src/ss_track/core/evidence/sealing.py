"""Writing a sealed record: validate it once, seal it, and replace its file in one read-only step.

The bytes a record pins are hashed here too, because the hash a record holds and the hash a check
compares it with must come from one function. Reading a sealed record is `core.evidence.sealed`.
"""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from ss_track.core.canonical import SEAL_FIELD, seal_of
from ss_track.core.evidence.contract_stamp import record_written
from ss_track.core.refusal import JsonValue
from ss_track.core.scratch import READ_ONLY_FILE_MODE, write_atomically
from ss_track.schema.validation.enforce import require_record

_CHUNK_BYTES = 1024 * 1024
_UNSEALED = "0" * 64  # a well-formed stand-in, so validation needs no hash of an invalid body


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
    """Return the record with a hash that covers every other field, once its contract holds.

    This is the one validation a record gets: a writer defect is `RECORD_INVALID` with nothing
    sealed, and a read then trusts the seal instead of walking the fields again.
    """
    require_record(_unsealed(body))  # before hashing, which a NaN would break
    sealed = dict(body)
    sealed[SEAL_FIELD] = seal_of(body)
    return sealed


def _unsealed(body: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return dict(body) | {SEAL_FIELD: _UNSEALED}


def sealed_bytes(sealed: Mapping[str, JsonValue]) -> bytes:
    """Return the bytes a sealed record is stored as."""
    text = json.dumps(sealed, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
    return f"{text}\n".encode("ascii")


def write_sealed(path: Path, sealed: Mapping[str, JsonValue]) -> None:
    """Write a read-only record so that a crash cannot leave a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, sealed_bytes(sealed), mode=READ_ONLY_FILE_MODE)
    record_written(path)
