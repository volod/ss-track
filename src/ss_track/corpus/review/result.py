"""What `discover queue`, `discover export` and `corpus freeze` report.

Each counts what review offered and decided, so unreviewed exposure and withheld locked windows are
visible without reading the files a command wrote.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.corpus.review.membership import Membership
from ss_track.corpus.review.queue import ReviewQueue


def review_counts(queue: ReviewQueue, membership: Membership) -> dict[str, JsonValue]:
    """Count what review offered, how it was decided, and the frozen streams it makes."""
    members = membership.members
    return {
        "offered": len(queue.offered),
        "included": sum(len(member.candidates) for member in members),
        "excluded": len(membership.exclusions),
        "unreviewed": len(membership.unreviewed),
        "withheld": len(queue.withheld),
        "stream_count": len(members),
        "frame_count": sum(member.end_frame - member.start_frame for member in members),
    }


@dataclass(frozen=True, slots=True)
class QueueResult:
    """What review of one run offers, and where a review template was written."""

    queue: ReviewQueue
    corpus_id: str
    template_path: Path | None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        record: dict[str, JsonValue] = {
            "status": "listed",
            "run_id": self.queue.run_id,
            "corpus_id": self.corpus_id,
            "queue": self.queue.counts(),
        }
        if self.template_path is not None:
            record["declaration_path"] = str(self.template_path)
        return record


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Where the frozen version's declaration was written and what the review made of the run."""

    status: str
    run_id: str
    corpus_id: str
    path: Path
    declaration_sha256: str
    counts: dict[str, JsonValue]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": self.status,
            "run_id": self.run_id,
            "corpus_id": self.corpus_id,
            "declaration_path": str(self.path),
            "declaration_sha256": self.declaration_sha256,
            "review": self.counts,
        }


@dataclass(frozen=True, slots=True)
class FreezeResult:
    """The sealed freeze record of one corpus version and what it holds, counted."""

    status: str
    record: Mapping[str, Any]
    path: Path
    counts: dict[str, JsonValue]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": self.status,
            "corpus_id": self.record["corpus_id"],
            "manifest_sha256": self.record[SEAL_FIELD],
            "manifest_path": str(self.path),
            "frame_set_sha256": self.record["frame_set_sha256"],
            "review": self.counts,
            "superseded": self.record["superseded"],
        }
