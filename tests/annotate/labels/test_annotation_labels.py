"""Label validation against the draft pack and a synthetic stored frame."""

from pathlib import Path

import pytest
import yaml

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.annotate.validation.validate import validate_labels
from tests.annotate.documents import (
    SPACE,
    assert_command,
    frame,
    label_body,
    label_result,
    load_labels,
    refused,
    replace_frame,
    write_yaml,
)
from tests.annotate.support import DRAFT
from tests.corpus._media import HEIGHT, WIDTH


def test_a_reviewed_box_is_scorable_and_has_no_score(tmp_path: Path, pack: ScenarioPack) -> None:
    path = write_yaml(tmp_path / "labels.yaml", label_body(pack))
    labels = load_labels(path, pack)
    again = load_labels(path, pack)
    record = assert_command(label_result(path, labels, pack))
    assert labels.document_sha256 == again.document_sha256
    assert labels.instances[0].frames[0].geometry.amodal_box is None
    assert record["annotation"]["pack_hash"] == pack.pack_hash
    assert record["annotation"]["replay_sha256"] is None
    assert record["annotation"]["entries"][0]["disposition"] == "scorable"
    assert record["annotation"]["entries"][0]["reason"] is None


def test_unverifiable_and_withheld_frames_are_not_zeros(tmp_path: Path, pack: ScenarioPack) -> None:
    ambiguous = label_body(pack)
    ambiguous["instances"][0]["identity"] = "identity_ambiguous"
    absent = replace_frame(label_body(pack), frame(visibility="absent"))
    point = frame()
    point["geometry"] = {
        "kind": "point_only",
        "point": {"x": 3, "y": 4},
        "uncertainty_px": 1,
        "plausible_extent_px": None,
    }
    cases = {
        "ambiguous": (ambiguous, "unscorable", "identity_ambiguous"),
        "absent": (absent, "not_denominator", "absent"),
        "point": (replace_frame(label_body(pack), point), "not_denominator", "no_plausible_extent"),
    }
    for name, (body, status, reason) in cases.items():
        labels = load_labels(write_yaml(tmp_path / f"{name}.yaml", body), pack)
        row = assert_command(label_result(tmp_path / name, labels, pack))["annotation"]["entries"][
            0
        ]
        assert row["disposition"] == status
        assert row["reason"] == reason


def test_a_distractor_can_score_and_an_ignore_region_stays_out(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    insect = label_body(pack)
    insect["instances"][0]["class_id"] = "insect"
    insect["instances"][0]["non_scoring_mark"] = "distractor"
    scored = load_labels(write_yaml(tmp_path / "insect.yaml", insect), pack)
    assert label_result(tmp_path / "insect.yaml", scored, pack).entries[0].disposition == "scorable"
    clutter = label_body(pack)
    clutter["instances"][0]["class_id"] = "clutter"
    clutter["instances"][0]["non_scoring_mark"] = "ignore_region"
    ignored = load_labels(write_yaml(tmp_path / "clutter.yaml", clutter), pack)
    row = label_result(tmp_path / "clutter.yaml", ignored, pack).entries[0]
    assert row.disposition == "not_denominator"
    assert row.reason == "ignore_region"


def test_an_amodal_box_stays_distinct(tmp_path: Path, pack: ScenarioPack) -> None:
    body = label_body(pack)
    body["instances"][0]["frames"][0]["geometry"]["amodal_box"] = {
        "x": 0,
        "y": 0,
        "width": 8,
        "height": 6,
    }
    labels = load_labels(write_yaml(tmp_path / "labels.yaml", body), pack)
    visible = labels.instances[0].frames[0].geometry.box
    amodal = labels.instances[0].frames[0].geometry.amodal_box
    assert visible is not None and amodal is not None
    assert (amodal.x, amodal.y, amodal.width, amodal.height) == (0, 0, 8, 6)
    assert (amodal.width, amodal.height) != (visible.width, visible.height)
    body["instances"][0]["frames"][0]["geometry"]["amodal_box"] = {
        "x": 60,
        "y": 40,
        "width": 8,
        "height": 10,
    }
    bad = write_yaml(tmp_path / "outside.yaml", body)
    refused(lambda: load_labels(bad, pack), "amodal box")


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("class", "not in the pack"),
        ("mark", "cannot use mark"),
        ("box", "outside the stored frame"),
        ("extent", "cannot carry"),
        ("duplicate", "duplicate instance id"),
        ("orientation", "stored orientation"),
        ("rotation", "display rotation"),
        ("hash", "pack_hash"),
        ("schema", "is not one of"),
    ],
)
def test_invalid_labels_are_refused(
    tmp_path: Path, pack: ScenarioPack, change: str, reason: str
) -> None:
    path = write_yaml(tmp_path / "labels.yaml", _broken(pack, change))
    refused(lambda: load_labels(path, pack), reason)


def test_a_rotated_source_is_labelled_in_stored_pixels(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    space = read_frame_space(rotated_clip)
    assert abs(space.display_rotation_degrees) == 90
    assert (space.width, space.height) == (WIDTH, HEIGHT)
    path = write_yaml(tmp_path / "labels.yaml", label_body(pack, space))
    record = assert_command(validate_labels(path, DRAFT, rotated_clip))
    assert record["annotation"]["entries"][0]["disposition"] == "scorable"
    swapped = label_body(pack, space)
    swapped["width"], swapped["height"] = space.height, space.width
    refused(
        lambda: validate_labels(
            write_yaml(tmp_path / "swapped.yaml", swapped), DRAFT, rotated_clip
        ),
        "width",
    )
    turned = label_body(pack, space)
    turned["orientation_degrees"] = 90
    refused(
        lambda: validate_labels(write_yaml(tmp_path / "turned.yaml", turned), DRAFT, rotated_clip),
        "stored orientation",
    )


def test_key_order_and_comments_do_not_change_the_label_hash(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    body = label_body(pack)
    first = write_yaml(tmp_path / "one.yaml", body)
    second = tmp_path / "two.yaml"
    second.write_text(yaml.safe_dump(body, sort_keys=True), encoding="utf-8")
    noted = tmp_path / "noted.yaml"
    noted.write_text("# operator note\n" + first.read_text(encoding="utf-8"), encoding="utf-8")
    hashes = {load_labels(path, pack).document_sha256 for path in (first, second, noted)}
    assert len(hashes) == 1
    assert SPACE.display_rotation_degrees == 90


def _broken(pack: ScenarioPack, change: str) -> dict[str, object]:
    body = label_body(pack)
    if change == "class":
        body["instances"][0]["class_id"] = "no-such"
    elif change == "mark":
        body["instances"][0]["non_scoring_mark"] = "distractor"
    elif change == "box":
        body["instances"][0]["frames"][0]["geometry"]["box"]["x"] = 80
    elif change == "extent":
        replace_frame(body, frame(visibility="absent"))
        body["instances"][0]["frames"][0]["geometry"] = frame()["geometry"]
    elif change == "duplicate":
        body["instances"].append(dict(body["instances"][0]))
    elif change == "orientation":
        body["orientation_degrees"] = 90
    elif change == "rotation":
        body["display_rotation_degrees"] = 0
    elif change == "hash":
        body["pack_hash"] = "cd" * 32
    elif change == "schema":
        body["instances"][0]["frames"][0]["visibility"] = "gone"
    return body
