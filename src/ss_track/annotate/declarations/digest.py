"""The one hash of a validated declaration: canonical JSON, then SHA-256."""

from collections.abc import Mapping
from typing import Any, cast

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import JsonValue


def as_document(document: Mapping[str, Any]) -> Mapping[str, JsonValue]:
    """Return a validated declaration as the JSON object its hash covers."""
    return cast(Mapping[str, JsonValue], document)


def declaration_hash(document: Mapping[str, JsonValue]) -> str:
    """Return the SHA-256 of the canonical JSON of one validated declaration.

    Object key order and comments do not change it. Array order does.
    """
    return sha256_bytes(canonical_json(document))
