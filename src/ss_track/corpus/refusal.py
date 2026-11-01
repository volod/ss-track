"""Structured refusals raised instead of recording evidence that cannot be trusted."""

from collections.abc import Mapping
from enum import StrEnum

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None


class RefusalCode(StrEnum):
    """Stable reason codes that callers may match on."""

    MANIFEST_INVALID = "MANIFEST_INVALID"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    SOURCE_UNREADABLE = "SOURCE_UNREADABLE"
    SOURCE_EMPTY = "SOURCE_EMPTY"
    SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"
    SOURCE_DAMAGED = "SOURCE_DAMAGED"
    SOURCE_NO_FRAMES = "SOURCE_NO_FRAMES"
    SOURCE_FORMAT_CHANGED = "SOURCE_FORMAT_CHANGED"
    PTS_NON_INCREASING = "PTS_NON_INCREASING"
    TIMESTAMP_CLAIM_UNSUPPORTED = "TIMESTAMP_CLAIM_UNSUPPORTED"
    SELECTION_OUT_OF_RANGE = "SELECTION_OUT_OF_RANGE"
    SOURCE_NOT_IMPORTED = "SOURCE_NOT_IMPORTED"
    RECORD_TAMPERED = "RECORD_TAMPERED"
    DECODE_POLICY_MISMATCH = "DECODE_POLICY_MISMATCH"
    IMPORT_CONFLICT = "IMPORT_CONFLICT"
    CORPUS_CONFLICT = "CORPUS_CONFLICT"
    CORPUS_NOT_BUILT = "CORPUS_NOT_BUILT"
    DECODE_DRIFT = "DECODE_DRIFT"
    BUNDLE_CONFLICT = "BUNDLE_CONFLICT"
    BUNDLE_NOT_STAGED = "BUNDLE_NOT_STAGED"
    STAGING_IN_PROGRESS = "STAGING_IN_PROGRESS"
    FRAME_CORRUPTED = "FRAME_CORRUPTED"
    FRAME_NOT_IN_BUNDLE = "FRAME_NOT_IN_BUNDLE"
    STORAGE_FAILED = "STORAGE_FAILED"


class CorpusRefusal(Exception):
    """A source or manifest was refused, with a machine-readable reason."""

    def __init__(
        self,
        code: RefusalCode,
        message: str,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, JsonValue] = dict(details or {})

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible refusal record shown to the operator."""
        return {
            "status": "refused",
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }
