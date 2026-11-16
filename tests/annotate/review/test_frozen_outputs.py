"""A frozen revision is written once, and a freeze never writes over what it reads."""

from pathlib import Path

import pytest

from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.compare import compare_label_sets
from ss_track.annotate.review.freeze import freeze_labels
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from tests.annotate.documents import load_labels, refused
from tests.annotate.review_files import (
    decision_for,
    freeze_written,
    prepare_pair,
    review_inputs,
    widen_box,
    write_review,
    write_settlement,
)


def test_a_frozen_revision_is_written_once(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, widen_box)
    write_review(tmp_path)
    left, right = _pair(tmp_path, pack, rotated_clip)
    write_settlement(
        tmp_path, [decision_for(row, "left") for row in compare_label_sets(left, right)]
    )
    first = freeze_written(tmp_path, rotated_clip)
    written = _outputs(tmp_path)
    again = freeze_written(tmp_path, rotated_clip)

    assert (again.label_sha256, again.revision_sha256) == (
        first.label_sha256,
        first.revision_sha256,
    )
    assert _outputs(tmp_path) == written

    write_settlement(
        tmp_path, [decision_for(row, "right") for row in compare_label_sets(left, right)]
    )
    with pytest.raises(CorpusRefusal) as caught:
        freeze_written(tmp_path, rotated_clip)
    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert _outputs(tmp_path) == written
    other = freeze_written(tmp_path, rotated_clip, tmp_path / "other")
    assert other.revision_sha256 != first.revision_sha256


def test_an_output_that_is_an_input_is_refused(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, lambda _body: None)
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    inputs = review_inputs(tmp_path, rotated_clip)
    before = {path: path.read_bytes() for path in (inputs.left, inputs.review)}

    refused(
        lambda: freeze_labels(
            inputs, tmp_path / "settlement.yaml", inputs.left, tmp_path / "revision.json"
        ),
        "is the left input",
    )
    refused(
        lambda: freeze_labels(
            inputs, tmp_path / "settlement.yaml", tmp_path / "frozen.json", inputs.review
        ),
        "is the review input",
    )
    assert {path: path.read_bytes() for path in before} == before
    assert not (tmp_path / "frozen.json").exists()


def _pair(folder: Path, pack: ScenarioPack, source: Path) -> tuple[LabelSet, LabelSet]:
    space = read_frame_space(source)
    return (
        load_labels(folder / "left.yaml", pack, space),
        load_labels(folder / "right.yaml", pack, space),
    )


def _outputs(folder: Path) -> dict[str, tuple[bytes, int]]:
    return {
        name: ((folder / name).read_bytes(), (folder / name).stat().st_mtime_ns)
        for name in ("frozen.json", "revision.json")
    }
