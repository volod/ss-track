"""Enforce time-dependent source terms without adding evaluation time to sealed records."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from ss_track.core.refusal import CorpusRefusal, RefusalCode

AMEND_COMMAND = "ss-track import --amend-terms"
TERM_SECTIONS = ("rights", "sensitivity")
_ABSENT = object()


def changed_terms(pinned: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    """Name each term that differs, so withdrawn rights read apart from any other new record."""
    changed: list[str] = []
    for section in TERM_SECTIONS:
        before, after = pinned.get(section, {}), current.get(section, {})
        for key in sorted(before.keys() | after.keys()):
            if before.get(key, _ABSENT) != after.get(key, _ABSENT):
                changed.append(f"{section}.{key}")
    return changed


def evaluation_date(today: date | None) -> date:
    """Choose one UTC date per operation, or the caller's deterministic test date."""
    return today if today is not None else datetime.now(UTC).date()


def require_retention(stream: Mapping[str, Any], today: date) -> None:
    """Allow retention through the declared day; refuse afterwards without deleting bytes.

    Every stream holds its source terms: a corpus manifest sealed before they existed is a stated
    shape that the read path refuses as evidence, so it never reaches this rule.
    """
    until = stream["rights"]["retain_until"]
    if until is not None and today > date.fromisoformat(until):
        raise CorpusRefusal(
            RefusalCode.RETENTION_EXPIRED,
            "source retention has ended",
            {"source_sha256": stream["source_sha256"], "retain_until": until},
        )
