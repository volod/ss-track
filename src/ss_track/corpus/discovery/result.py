"""What `discover run` and `discover verify` report: the run's counts, selection and coverage.

The selection summary counts what was selected and why candidates were excluded; unavailable scores
are counted by score and reason, so a missing feature is visible without reading the inventories.
Coverage states, for each extractor, the least share of a frame's area its model input showed over
the run's streams, and the least scale at which it saw a target.
"""

from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.refusal import JsonValue
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.siblings.tiles import coverage

_DIGITS = 6


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """What a discovery command reports."""

    status: str
    records: DiscoveryRecords
    path: Path
    frame_sizes: Mapping[str, tuple[int, int]] = field(default_factory=dict)  # by stream

    def _candidates(self) -> Iterator[Mapping[str, Any]]:
        for stream_id in sorted(self.records.inventories):
            candidates: Any = self.records.inventories[stream_id]["candidates"]
            yield from candidates

    def _selection(self, run: Mapping[str, Any]) -> dict[str, JsonValue]:
        statuses = [candidate["selection"] for candidate in self._candidates()]
        reasons = Counter(item["reason"] for item in statuses if item["status"] == "excluded")
        return {
            "method": run["selection"]["method"],
            "budget": run["selection"]["budget"],
            "selected": sum(item["status"] == "selected" for item in statuses),
            "excluded": [{"reason": name, "count": reasons[name]} for name in sorted(reasons)],
        }

    def _unavailable(self) -> list[JsonValue]:
        missing = Counter(
            (score["score_id"], score["reason"])
            for candidate in self._candidates()
            for score in candidate["scores"]
            if score["status"] == "unavailable"
        )
        return [
            {"score_id": score_id, "reason": reason, "count": missing[(score_id, reason)]}
            for score_id, reason in sorted(missing)
        ]

    def _coverage(self, run: Mapping[str, Any]) -> list[JsonValue]:
        found: list[JsonValue] = []
        sizes = sorted(self.frame_sizes.values())
        for extractor in run["extractors"]:
            if not sizes:
                continue
            seen = [coverage(extractor["preprocessing"], *size) for size in sizes]
            found.append(
                {
                    "extractor_id": extractor["extractor_id"],
                    "covered_fraction": round(min(item[0] for item in seen), _DIGITS),
                    "scale": round(min(item[1] for item in seen), _DIGITS),
                }
            )
        return found

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible command result."""
        run: Mapping[str, Any] = self.records.run
        return {
            "status": self.status,
            "run_id": run["run_id"],
            "corpus_id": run["corpus_id"],
            "manifest_sha256": run[SEAL_FIELD],
            "manifest_path": str(self.path),
            "inventory_count": len(self.records.inventories),
            "candidate_count": sum(line["candidate_count"] for line in run["inventories"]),
            "feature_row_count": sum(line["row_count"] for line in run.get("feature_rows", [])),
            "hint_sources": [
                {"hint_source_id": source["hint_source_id"], **source["matches"]}
                for source in run["hint_sources"]
                if "matches" in source
            ],
            "selection": self._selection(run),
            "unavailable_scores": self._unavailable(),
            "coverage": self._coverage(run),
        }
