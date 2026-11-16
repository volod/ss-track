"""The validation result `ss-track annotate validate` logs. It has no score."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ss_track.annotate.labels.disposition import DispositionStatus
from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.labels.rules import label_dispositions
from ss_track.core.refusal import JsonValue

AnnotationKind = Literal["label", "seed", "mask"]


@dataclass(frozen=True, slots=True)
class AnnotationEntry:
    """One label frame, seed role or mask frame."""

    entry_id: str
    frame_index: int
    disposition: DispositionStatus
    reason: str | None

    def to_record(self) -> dict[str, JsonValue]:
        """Return this row. There is no score field."""
        return {
            "entry_id": self.entry_id,
            "frame_index": self.frame_index,
            "disposition": self.disposition,
            "reason": self.reason,
        }


def label_entries(labels: LabelSet) -> tuple[AnnotationEntry, ...]:
    """Return one row per labeled frame, in document order, with no score."""
    return tuple(
        AnnotationEntry(instance_id, frame_index, found.status, found.reason)
        for (instance_id, frame_index), found in label_dispositions(labels).items()
    )


@dataclass(frozen=True, slots=True)
class AnnotationResult:
    """One document that validated, including rows that stay unscorable.

    `version` is the frozen contract version the document was validated under.
    """

    path: Path
    contract: str
    version: str
    kind: AnnotationKind
    document_sha256: str
    pack_hash: str | None
    replay_sha256: str | None
    entries: tuple[AnnotationEntry, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the command result. An unscorable row is not a zero."""
        listed: list[JsonValue] = [entry.to_record() for entry in self.entries]
        return {
            "status": "valid",
            "path": str(self.path),
            "contract": self.contract,
            "version": self.version,
            "annotation": {
                "kind": self.kind,
                "document_sha256": self.document_sha256,
                "pack_hash": self.pack_hash,
                "replay_sha256": self.replay_sha256,
                "entries": listed,
            },
        }
