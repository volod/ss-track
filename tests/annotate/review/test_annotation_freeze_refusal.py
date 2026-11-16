"""A freeze refuses an unsettled required disagreement and an invalid settlement."""

from pathlib import Path
from typing import Any

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.compare import compare_label_sets
from ss_track.annotate.review.freeze import freeze_labels
from ss_track.annotate.review.obligation import apply_obligation
from ss_track.annotate.review.read import read_review
from ss_track.annotate.sources.frame_space import read_frame_space
from tests.annotate.documents import frame, load_labels, refused, replace_frame
from tests.annotate.review_files import (
    decision_for,
    freeze_written,
    prepare_pair,
    review_inputs,
    widen_box,
    write_review,
    write_settlement,
)


def test_an_unresolved_disagreement_blocks_the_freeze(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(
        tmp_path, pack, rotated_clip, lambda body: replace_frame(body, frame(visibility="absent"))
    )
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    refusal = refused(lambda: freeze_written(tmp_path, rotated_clip), "unresolved disagreement")
    assert "frame target-1 0 visibility" in refusal.message
    assert "event onset-1 visibility" in refusal.message
    assert not (tmp_path / "frozen.json").exists()


def test_a_difficult_disagreement_outside_the_sample_still_blocks(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(
        tmp_path, pack, rotated_clip, lambda body: replace_frame(body, frame(visibility="unknown"))
    )
    write_review(tmp_path, coverage="sample", items=[])
    write_settlement(tmp_path, [])
    refused(lambda: freeze_written(tmp_path, rotated_clip), "unresolved disagreement")
    space = read_frame_space(rotated_clip)
    left = load_labels(tmp_path / "left.yaml", pack, space)
    right = load_labels(tmp_path / "right.yaml", pack, space)
    rows = apply_obligation(
        compare_label_sets(left, right), left, right, read_review(tmp_path / "review.yaml")
    )
    assert any(row.difficult and row.field == "visibility" for row in rows)


def test_a_named_sample_frame_is_required(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, widen_box)
    write_review(tmp_path, coverage="sample", items=[{"instance_id": "target-1", "frame_index": 0}])
    write_settlement(tmp_path, [])
    refused(lambda: freeze_written(tmp_path, rotated_clip), "frame target-1 0 geometry.box")


def test_a_decision_that_is_not_a_disagreement_is_refused(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, widen_box)
    write_review(tmp_path)
    write_settlement(
        tmp_path,
        [
            {
                "subject": "frame",
                "instance_id": "target-1",
                "frame_index": 0,
                "field": "camera_motion",
                "outcome": "left",
                "rationale": "the camera did not move",
            }
        ],
    )
    refused(lambda: freeze_written(tmp_path, rotated_clip), "is not a disagreement")


def test_a_duplicate_decision_is_refused(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    left, right = prepare_pair(tmp_path, pack, rotated_clip, widen_box)
    write_review(tmp_path)
    chosen = decision_for(compare_label_sets(left, right)[0], "left")
    write_settlement(tmp_path, [chosen, chosen])
    refused(lambda: freeze_written(tmp_path, rotated_clip), "duplicate decision")


def test_a_class_and_mark_the_pack_rejects_are_refused(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    def mark_insect(body: dict[str, Any]) -> None:
        body["instances"][0]["class_id"] = "insect"
        body["instances"][0]["non_scoring_mark"] = "distractor"

    left, right = prepare_pair(tmp_path, pack, rotated_clip, mark_insect)
    write_review(tmp_path)
    decisions = [
        decision_for(row, "right" if row.field == "class_id" else "left")
        for row in compare_label_sets(left, right)
    ]
    write_settlement(tmp_path, decisions)
    refused(lambda: freeze_written(tmp_path, rotated_clip), "cannot use mark")


def test_omitting_every_instance_refuses_an_empty_revision(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    def rename(body: dict[str, Any]) -> None:
        body["instances"][0]["instance_id"] = "target-2"
        body["motion_events"][0]["instance_id"] = "target-2"
        body["motion_events"][0]["event_id"] = "onset-2"

    left, right = prepare_pair(tmp_path, pack, rotated_clip, rename)
    write_review(tmp_path)
    decisions = []
    for row in compare_label_sets(left, right):
        omits = "right" if row.left == "true" else "left"
        decisions.append(decision_for(row, omits))
    write_settlement(tmp_path, decisions)
    refused(lambda: freeze_written(tmp_path, rotated_clip), "frozen revision has no instance")


def test_an_entire_review_lists_no_sample(tmp_path: Path) -> None:
    path = write_review(
        tmp_path, coverage="entire", items=[{"instance_id": "target-1", "frame_index": 0}]
    )
    refused(lambda: read_review(path), "lists no sample")


def test_a_sample_frame_is_listed_once(tmp_path: Path) -> None:
    item = {"instance_id": "target-1", "frame_index": 0}
    path = write_review(tmp_path, coverage="sample", items=[item, item])
    refused(lambda: read_review(path), "duplicate sample frame")


def test_a_sample_names_an_instance_the_labels_have(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, lambda _body: None)
    write_review(tmp_path, coverage="sample", items=[{"instance_id": "missing", "frame_index": 0}])
    write_settlement(tmp_path, [])
    refused(lambda: freeze_written(tmp_path, rotated_clip), "not in either label document")


def test_the_settlement_authority_matches_the_review(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, lambda _body: None)
    write_review(tmp_path, authority="ada")
    write_settlement(tmp_path, [], authority="bob")
    refused(lambda: freeze_written(tmp_path, rotated_clip), "authority does not match")


def test_the_label_and_revision_are_different_files(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    prepare_pair(tmp_path, pack, rotated_clip, lambda _body: None)
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    same = tmp_path / "same.json"
    refused(
        lambda: freeze_labels(
            review_inputs(tmp_path, rotated_clip), tmp_path / "settlement.yaml", same, same
        ),
        "different files",
    )
