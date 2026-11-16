"""A freeze that settles disagreements and keeps one hashed revision."""

import copy
import json
from pathlib import Path
from typing import Any

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.compare import compare_label_sets
from ss_track.annotate.review.result import ReviewResult
from ss_track.annotate.review.revision import read_annotation_revision
from ss_track.annotate.sources.frame_space import FrameSpace, read_frame_space
from ss_track.annotate.validation.result import label_entries
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations
from tests.annotate.documents import frame, label_body, load_labels, replace_frame, write_yaml
from tests.annotate.review_files import (
    decision_for,
    freeze_written,
    prepare_pair,
    widen_box,
    write_review,
    write_settlement,
)


def test_an_unknown_decision_stays_unknown_and_is_not_a_score(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    left, right = prepare_pair(
        tmp_path, pack, rotated_clip, lambda body: replace_frame(body, frame(visibility="absent"))
    )
    write_review(tmp_path)
    write_settlement(
        tmp_path, [decision_for(row, "unknown") for row in compare_label_sets(left, right)]
    )
    result = freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))
    assert frozen.instances[0].frames[0].visibility == "unknown"
    assert frozen.instances[0].frames[0].geometry.kind == "unlocalizable"
    assert frozen.instances[0].frames[0].annotator_id == "ada"
    assert frozen.motion_events == ()
    assert label_entries(frozen)[0].reason == "unknown"
    record = _assert_review(result)
    band = record["label_review"]["sensitivity_band"]
    assert band == {"left_sha256": left.document_sha256, "right_sha256": right.document_sha256}
    sealed = read_annotation_revision(tmp_path / "revision.json")
    assert sealed["label_sha256"] == frozen.document_sha256
    assert sealed["sensitivity_band"] == band
    again = freeze_written(tmp_path, rotated_clip)
    assert again.label_sha256 == result.label_sha256
    assert again.revision_sha256 == result.revision_sha256


def test_settling_every_field_left_keeps_that_box(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    left, right = prepare_pair(tmp_path, pack, rotated_clip, widen_box)
    write_review(tmp_path)
    write_settlement(
        tmp_path, [decision_for(row, "left") for row in compare_label_sets(left, right)]
    )
    freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))
    assert frozen.instances[0].frames[0].geometry.box == left.instances[0].frames[0].geometry.box
    assert frozen.instances[0].frames[0].annotator_id == "ada"
    assert frozen.label_id == "g0-labels"
    assert frozen.motion_events[0].visibility == "visible"
    assert frozen.motion_events[0].selection_quality == "reviewed"


def test_a_box_outside_the_sample_stays_unknown_without_a_decision(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, widen_box)
    write_review(tmp_path, coverage="sample", items=[])
    write_settlement(tmp_path, [])
    result = freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))
    assert frozen.instances[0].frames[0].visibility == "unknown"
    assert frozen.instances[0].frames[0].geometry.kind == "unlocalizable"
    assert result.rows[0].obligation == "outside"
    assert result.rows[0].outcome == "unknown"
    assert result.rows[0].difficult is False
    assert result.rows[0].rationale is None


def test_an_unknown_camera_keeps_the_box(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    def move_camera(body: dict[str, Any]) -> None:
        body["instances"][0]["frames"][0]["camera_motion"] = "shake"

    prepare_pair(tmp_path, pack, rotated_clip, move_camera)
    write_review(tmp_path, coverage="sample", items=[])
    write_settlement(tmp_path, [])
    freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))
    frame_row = frozen.instances[0].frames[0]
    assert frame_row.camera_motion == "unknown"
    assert frame_row.visibility == "visible"
    assert frame_row.geometry.kind == "box"


def test_unknown_class_stays_unscorable_and_keeps_the_agreed_box(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    def rename_class(body: dict[str, Any]) -> None:
        body["instances"][0]["class_id"] = "drone"

    left, right = prepare_pair(tmp_path, pack, rotated_clip, rename_class)
    write_review(tmp_path)
    write_settlement(
        tmp_path, [decision_for(row, "unknown") for row in compare_label_sets(left, right)]
    )
    freeze_written(tmp_path, rotated_clip)
    frozen = load_labels(tmp_path / "frozen.json", pack, read_frame_space(rotated_clip))
    assert frozen.instances[0].class_id == "bird"
    assert frozen.instances[0].identity == "identity_ambiguous"
    assert frozen.instances[0].frames[0].geometry.kind == "box"
    assert label_entries(frozen)[0].reason == "identity_ambiguous"


def test_instance_order_does_not_change_the_revision(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    space = read_frame_space(rotated_clip)
    left_body = _two_instances(pack, space)
    right_body = copy.deepcopy(left_body)
    for instance in right_body["instances"]:
        instance["frames"][0]["annotator_id"] = "ann-b"
    right_body["instances"].reverse()
    write_yaml(tmp_path / "left.yaml", left_body)
    write_yaml(tmp_path / "right.yaml", right_body)
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    first = freeze_written(tmp_path, rotated_clip)
    right_body["instances"].reverse()
    write_yaml(tmp_path / "right.yaml", right_body)
    second = freeze_written(tmp_path, rotated_clip, tmp_path / "again")
    assert first.label_sha256 == second.label_sha256
    assert first.revision_sha256 != second.revision_sha256
    assert first.label_sha256 != load_labels(tmp_path / "left.yaml", pack, space).document_sha256


def _two_instances(pack: ScenarioPack, space: FrameSpace) -> dict[str, Any]:
    body = label_body(pack, space)
    extra = copy.deepcopy(body["instances"][0])
    extra["instance_id"] = "target-2"
    body["instances"].append(extra)
    return body


def _assert_review(result: ReviewResult) -> dict[str, Any]:
    record = json.loads(json.dumps(result.to_record()))
    contracts = load_contract_set()
    contract = contracts.named("result/command")
    frozen = contract.newest()
    assert frozen is not None
    found = violations(
        record, contracts.frozen_schema(contract, frozen), contracts.schema_registry()
    )
    assert not found, found
    assert "score" not in json.dumps(record)
    assert record["status"] == "frozen"
    return record
