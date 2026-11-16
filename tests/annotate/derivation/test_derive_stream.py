"""Derivation joins a parent's frozen labels to the corpus stream they sit under.

Labels of another source, or of another decode of this one, would move every case derived
from them, so they are refused before any case is written.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.compare import compare_label_sets
from ss_track.core.refusal import RefusalCode
from ss_track.corpus.storage.layout import corpus_manifest_path, labels_directory
from tests.annotate.derived_corpus import CORPUS, STREAM, copy_data, derive, install_labels
from tests.annotate.review_files import (
    decision_for,
    freeze_written,
    prepare_pair,
    write_review,
    write_settlement,
)
from tests.corpus.conftest import reseal


def test_labels_of_another_source_are_refused(
    built: tuple[Path, Path, Path],
    rotated_clip: Path,
    tmp_path: Path,
    pack: ScenarioPack,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = copy_data(built[0], tmp_path)
    other = tmp_path / "other"
    left, right = prepare_pair(other, pack, rotated_clip, lambda _body: None)
    write_review(other)
    write_settlement(other, [decision_for(row, "left") for row in compare_label_sets(left, right)])
    freeze_written(other, rotated_clip)
    install_labels(data, other)

    refused = derive(data, monkeypatch, caplog, code=1)

    assert refused["code"] == RefusalCode.MANIFEST_INVALID
    assert "source_sha256" in str(refused["message"])
    assert f"stream {STREAM}" in str(refused["message"])
    assert _derived(data) == []


@pytest.mark.parametrize(("fact", "value"), [("frame_count", 23), ("width", 32), ("height", 24)])
def test_labels_of_another_frame_shape_are_refused(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    fact: str,
    value: int,
) -> None:
    data, _clip, folder = built
    copied = copy_data(data, tmp_path)
    install_labels(copied, folder)
    manifest = corpus_manifest_path(copied, CORPUS)
    streams: list[dict[str, Any]] = json.loads(manifest.read_text(encoding="ascii"))["streams"]
    streams[0][fact] = value
    reseal(manifest, streams=streams)

    refused = derive(copied, monkeypatch, caplog, code=1)

    assert refused["code"] == RefusalCode.MANIFEST_INVALID
    assert f"{fact} is" in str(refused["message"])
    assert f"stream {STREAM} is {value}" in str(refused["message"])
    assert _derived(copied) == []


def _derived(data: Path) -> list[str]:
    """Return the label directories derive wrote, which exclude the parent stream's own."""
    root = labels_directory(data, CORPUS)
    return sorted(path.name for path in root.iterdir() if path.is_dir() and path.name != STREAM)
