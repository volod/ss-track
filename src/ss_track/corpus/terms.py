"""Enforce time-dependent source terms without adding evaluation time to sealed records."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode


def evaluation_date(today: date | None) -> date:
    """Choose one UTC date per operation, or the caller's deterministic test date."""
    return today if today is not None else datetime.now(UTC).date()


def require_retention(stream: Mapping[str, Any], today: date) -> None:
    """Allow retention through the declared day; refuse afterwards without deleting bytes."""
    rights = stream["rights"]
    if "retain_until" not in rights or "derived_frames" not in rights:
        raise CorpusRefusal(
            RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
            "source terms are missing; import a schema-2 recording and build a new corpus",
            {"source_sha256": stream["source_sha256"]},
        )
    until = rights["retain_until"]
    if until is not None and today > date.fromisoformat(until):
        raise CorpusRefusal(
            RefusalCode.RETENTION_EXPIRED,
            "source retention has ended",
            {"source_sha256": stream["source_sha256"], "retain_until": until},
        )
