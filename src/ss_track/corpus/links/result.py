"""What `discover links` reports: the review's status and how many links each state and method holds.

The record holds every link and its evidence; the result counts them, so an undecided pair across
splits, or a method that could not compare some streams, is visible without reading the record.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.corpus.links.review import UNRESOLVED


@dataclass(frozen=True, slots=True)
class LinksResult:
    """What a link review command reports."""

    status: str
    record: Mapping[str, Any]
    path: Path

    def _summary(self) -> dict[str, JsonValue]:
        links = self.record["links"]
        states = Counter(link["status"] for link in links)
        flagged = Counter(
            (flag["method"], flag.get("extractor_id", ""))
            for link in links
            for flag in link["evidence"]
        )
        summary: dict[str, JsonValue] = {
            "status": self.record["status"],
            "count": len(links),
            "states": [{"status": name, "count": states[name]} for name in sorted(states)],
            "unresolved_cross_split": sum(
                link["status"] == UNRESOLVED and link["cross_split"] for link in links
            ),
            "flagged": [
                {"method": method, **({"extractor_id": base} if base else {}), "count": count}
                for (method, base), count in sorted(flagged.items())
            ],
            "not_compared": len(self.record["not_compared"]),
        }
        if "decisions_outside_links" in self.record:
            summary["decisions_outside_links"] = len(self.record["decisions_outside_links"])
        return summary

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible result shown to the operator."""
        return {
            "status": self.status,
            "run_id": self.record["run_id"],
            "corpus_id": self.record["corpus_id"],
            "manifest_sha256": self.record[SEAL_FIELD],
            "manifest_path": str(self.path),
            "links": self._summary(),
        }
