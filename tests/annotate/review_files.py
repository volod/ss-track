"""Fixtures for two label documents, a review plan and a settlement."""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.review import freeze_labels
from ss_track.annotate.review_model import Disagreement
from ss_track.annotate.review_result import ReviewResult
from ss_track.annotate.space import FrameSpace, read_frame_space
from tests.annotate.documents import SPACE, label_body, load_labels, write_yaml
from tests.annotate.support import DRAFT

type Mutate = Callable[[dict[str, Any]], None]


def write_pair(
    folder: Path, pack: ScenarioPack, mutate: Mutate, space: FrameSpace = SPACE
) -> tuple[LabelSet, LabelSet]:
    """Write two label documents. The right annotator id differs even when nothing else does."""
    folder.mkdir(parents=True, exist_ok=True)
    left_body = label_body(pack, space)
    right_body = copy.deepcopy(left_body)
    right_body["instances"][0]["frames"][0]["annotator_id"] = "ann-b"
    mutate(right_body)
    left = load_labels(write_yaml(folder / "left.yaml", left_body), pack, space)
    right = load_labels(write_yaml(folder / "right.yaml", right_body), pack, space)
    return left, right


def write_review(
    folder: Path,
    *,
    coverage: str = "entire",
    items: list[dict[str, Any]] | None = None,
    authority: str = "ada",
) -> Path:
    """Write a review plan. An entire review lists no sample."""
    return write_yaml(
        folder / "review.yaml",
        {
            "schema_version": 1,
            "review_id": "g0-review",
            "authority": authority,
            "coverage": coverage,
            "items": [] if items is None else items,
        },
    )


def write_settlement(folder: Path, decisions: list[dict[str, Any]], authority: str = "ada") -> Path:
    """Write a settlement whose revision id becomes the frozen label id."""
    return write_yaml(
        folder / "settlement.yaml",
        {
            "schema_version": 1,
            "settlement_id": "g0-settlement",
            "revision_id": "g0-labels",
            "authority": authority,
            "decisions": decisions,
        },
    )


def decision_for(row: Disagreement, outcome: str) -> dict[str, Any]:
    """Return one settlement decision for a disagreement row."""
    body: dict[str, Any] = {
        "subject": row.subject,
        "field": row.field,
        "outcome": outcome,
        "rationale": "settled from the fixture",
    }
    if row.subject == "instance":
        body["instance_id"] = row.instance_id
    elif row.subject == "frame":
        body["instance_id"] = row.instance_id
        body["frame_index"] = row.frame_index
    else:
        body["event_id"] = row.event_id
    return body


def prepare_pair(
    folder: Path, pack: ScenarioPack, source: Path, mutate: Mutate
) -> tuple[LabelSet, LabelSet]:
    """Write a pair whose declared space is the video at `source`."""
    return write_pair(folder, pack, mutate, read_frame_space(source))


def widen_box(body: dict[str, Any]) -> None:
    """Move the only box one pixel wider."""
    body["instances"][0]["frames"][0]["geometry"]["box"]["width"] = 5


def freeze_written(folder: Path, source: Path) -> ReviewResult:
    """Freeze the pair written in `folder` against `source`."""
    return freeze_labels(
        folder / "left.yaml",
        folder / "right.yaml",
        DRAFT,
        source,
        folder / "review.yaml",
        folder / "settlement.yaml",
        folder / "frozen.json",
        folder / "revision.json",
    )
