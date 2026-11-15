"""The command result for `ss-track annotate derive`. It has no score.

A case whose parent has no frozen revision is `unscorable`. That is not a zero.
"""

from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import JsonValue

_NO_FROZEN_LABELS = "no_frozen_labels"


@dataclass(frozen=True, slots=True)
class DerivedCase:
    """One generated case after derivation, or an unscorable case with no parent revision."""

    case_id: str
    status: str
    reason: str | None = None
    label_sha256: str | None = None
    revision_sha256: str | None = None
    labels_path: Path | None = None
    revision_path: Path | None = None
    timestamp_quality: str | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return this case. An unscorable case has no hash and no path."""
        if self.status == "unscorable":
            return {
                "case_id": self.case_id,
                "status": "unscorable",
                "reason": self.reason or _NO_FROZEN_LABELS,
            }
        return {
            "case_id": self.case_id,
            "status": "derived",
            "label_sha256": self.label_sha256,
            "revision_sha256": self.revision_sha256,
            "labels_path": None if self.labels_path is None else str(self.labels_path),
            "revision_path": None if self.revision_path is None else str(self.revision_path),
            "timestamp_quality": self.timestamp_quality,
        }


@dataclass(frozen=True, slots=True)
class DeriveResult:
    """Every generated case of one corpus, in manifest order."""

    corpus_id: str
    cases: tuple[DerivedCase, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the command result. There is no score field."""
        listed: list[JsonValue] = [case.to_record() for case in self.cases]
        return {
            "status": "derived",
            "label_derivation": {"corpus_id": self.corpus_id, "cases": listed},
        }
