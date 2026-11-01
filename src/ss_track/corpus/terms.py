"""Enforce time-dependent source terms without adding evaluation time to sealed records."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode

_TERM_SECTIONS = ("rights", "sensitivity")


def changed_terms(pinned: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Name each term that differs, so withdrawn rights read apart from any other new record."""
    changed: list[str] = []
    for section in _TERM_SECTIONS:
        before, after = pinned.get(section, {}), current.get(section, {})
        keys = sorted(before.keys() | after.keys())
        changed += [f"{section}.{key}" for key in keys if before.get(key) != after.get(key)]
    return changed


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
