"""The single byte form that every hash and seal in this product covers."""

import hashlib
import json
from collections.abc import Mapping

from ss_track.refusal import JsonValue

SEAL_FIELD = "manifest_sha256"


def canonical_json(value: Mapping[str, JsonValue]) -> bytes:
    """Serialize one value to the single byte form that its hash covers."""
    text = json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True
    )
    return text.encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase SHA-256 of some bytes."""
    return hashlib.sha256(payload).hexdigest()


def seal_of(body: Mapping[str, JsonValue]) -> str:
    """Return the hash a record's seal holds, over every field except the seal."""
    return sha256_bytes(canonical_json({k: v for k, v in body.items() if k != SEAL_FIELD}))
