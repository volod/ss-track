"""`ss-track annotate compare` and `annotate freeze` on one rotated clip."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.cli import main
from ss_track.core.refusal import RefusalCode
from tests.annotate.documents import frame, replace_frame
from tests.annotate.review_files import write_pair, write_review, write_settlement
from tests.annotate.support import DRAFT


def test_compare_succeeds_when_the_documents_differ(
    tmp_path: Path, pack: object, rotated_clip: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    space = read_frame_space(rotated_clip)
    write_pair(tmp_path, pack, lambda body: replace_frame(body, frame(visibility="absent")), space)
    write_review(tmp_path)
    assert main(_compare(tmp_path, rotated_clip)) == 0
    record = _record(caplog)
    assert record["status"] == "valid"
    review = record["label_review"]
    assert review["command"] == "compare"
    assert review["disagreements"]
    assert all(row["outcome"] == "unresolved" for row in review["disagreements"])
    assert "score" not in json.dumps(record)
    assert "label_sha256" not in review


def test_freeze_refuses_an_unresolved_disagreement(
    tmp_path: Path, pack: object, rotated_clip: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    space = read_frame_space(rotated_clip)
    write_pair(tmp_path, pack, lambda body: replace_frame(body, frame(visibility="absent")), space)
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    assert main(_freeze(tmp_path, rotated_clip)) == 1
    record = _record(caplog)
    assert record["code"] == RefusalCode.MANIFEST_INVALID
    assert "unresolved disagreement" in str(record["message"])
    assert not (tmp_path / "frozen.json").exists()


def _pair(folder: Path, source: Path) -> list[str]:
    return [
        "--left",
        str(folder / "left.yaml"),
        "--right",
        str(folder / "right.yaml"),
        "--pack",
        str(DRAFT),
        "--source",
        str(source),
        "--review",
        str(folder / "review.yaml"),
    ]


def _compare(folder: Path, source: Path) -> list[str]:
    return ["annotate", "compare", *_pair(folder, source)]


def _freeze(folder: Path, source: Path) -> list[str]:
    return [
        "annotate",
        "freeze",
        *_pair(folder, source),
        "--settlement",
        str(folder / "settlement.yaml"),
        "--labels-out",
        str(folder / "frozen.json"),
        "--revision-out",
        str(folder / "revision.json"),
    ]


def _record(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    loaded = json.loads(caplog.records[-1].getMessage())
    if not isinstance(loaded, dict):
        raise TypeError("command record is not an object")
    return loaded
