"""The command result for `annotate compare` and `annotate freeze`. It has no score."""

from dataclasses import dataclass
from pathlib import Path

from ss_track.annotate.review_model import Disagreement, Reviewer
from ss_track.core.refusal import JsonValue


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """One comparison, or one frozen revision and the band both annotators retain."""

    command: str
    coverage: str
    reviewers: tuple[Reviewer, Reviewer]
    rows: tuple[Disagreement, ...]
    label_sha256: str | None = None
    revision_sha256: str | None = None
    labels_path: Path | None = None
    revision_path: Path | None = None

    def to_record(self) -> dict[str, JsonValue]:
        """Return the command result. Compare stays ``valid`` when the documents differ."""
        left, right = self.reviewers
        listed: list[JsonValue] = [row.to_record() for row in self.rows]
        review: dict[str, JsonValue] = {
            "command": self.command,
            "coverage": self.coverage,
            "reviewers": [left.to_record(), right.to_record()],
            "sensitivity_band": {
                "left_sha256": left.label_sha256,
                "right_sha256": right.label_sha256,
            },
            "disagreements": listed,
        }
        if self.command == "compare":
            return {"status": "valid", "label_review": review}
        self._require_freeze()
        review["label_sha256"] = self.label_sha256
        review["revision_sha256"] = self.revision_sha256
        review["labels_path"] = None if self.labels_path is None else str(self.labels_path)
        review["revision_path"] = None if self.revision_path is None else str(self.revision_path)
        return {"status": "frozen", "label_review": review}

    def _require_freeze(self) -> None:
        if (
            self.label_sha256 is None
            or self.revision_sha256 is None
            or self.labels_path is None
            or self.revision_path is None
        ):
            raise TypeError("a freeze result needs the revision hashes and paths")
