"""Seed replay is a pure function of the seed document."""

from pathlib import Path

import pytest
import yaml

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.validation.seed import replay_document, replay_hash
from tests.annotate.documents import (
    label_body,
    load_labels,
    load_seed,
    refused,
    seed_body,
    write_yaml,
)


def test_identical_seeds_replay_identically(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = load_labels(write_yaml(tmp_path / "labels.yaml", label_body(pack)), pack)
    body = seed_body(labels.space, labels.document_sha256)
    first = write_yaml(tmp_path / "one.yaml", body)
    second = tmp_path / "two.yaml"
    second.write_text(yaml.safe_dump(body, sort_keys=True), encoding="utf-8")
    noted = tmp_path / "noted.yaml"
    noted.write_text("# note\n" + first.read_text(encoding="utf-8"), encoding="utf-8")
    hashes = {replay_hash(load_seed(path, labels)) for path in (first, second, noted)}
    assert len(hashes) == 1
    replay = replay_document(load_seed(first, labels))
    assert replay["roles"][0]["x"] == 1
    assert replay["roles"][1]["x"] == 2
    assert replay["roles"][1]["perturbation_id"] == "shift-1"


def test_the_annotator_is_not_part_of_the_replay(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = load_labels(write_yaml(tmp_path / "labels.yaml", label_body(pack)), pack)
    body = seed_body(labels.space, labels.document_sha256)
    original = load_seed(write_yaml(tmp_path / "seed.yaml", body), labels)
    body["annotator_id"] = "op-2"
    renamed = load_seed(write_yaml(tmp_path / "renamed.yaml", body), labels)
    assert renamed.document_sha256 != original.document_sha256
    assert replay_hash(renamed) == replay_hash(original)


def test_quality_and_a_correction_change_the_selection(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = load_labels(write_yaml(tmp_path / "labels.yaml", label_body(pack)), pack)
    body = seed_body(labels.space, labels.document_sha256)
    clicked = replay_hash(load_seed(write_yaml(tmp_path / "clicked.yaml", body), labels))
    body["quality"] = "imprecise"
    imprecise = load_seed(write_yaml(tmp_path / "imprecise.yaml", body), labels)
    assert replay_hash(imprecise) != clicked
    assert replay_document(imprecise)["roles"][0]["x"] == 1
    body["quality"] = "corrected"
    body["correction"] = {"kind": "box", "x": 5, "y": 2, "width": 4, "height": 3}
    corrected = load_seed(write_yaml(tmp_path / "corrected.yaml", body), labels)
    replay = replay_document(corrected)
    assert replay["roles"][0]["x"] == 5
    assert replay["roles"][1]["x"] == 6
    assert replay_hash(corrected) != clicked


def test_a_stated_time_must_match_the_source(tmp_path: Path, pack: ScenarioPack) -> None:
    labels = load_labels(write_yaml(tmp_path / "labels.yaml", label_body(pack)), pack)
    body = seed_body(labels.space, labels.document_sha256)
    body["pts"] = 0
    body["time_base"] = "1/25"
    accepted = load_seed(write_yaml(tmp_path / "timed.yaml", body), labels)
    assert accepted.pts == 0
    body["pts"] = 9
    refused(lambda: load_seed(write_yaml(tmp_path / "wrong.yaml", body), labels), "pts is 9")
    body["pts"] = 0
    body["time_base"] = None
    refused(
        lambda: load_seed(write_yaml(tmp_path / "half.yaml", body), labels), "both set or both null"
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("label", "cd" * 32, "label_sha256"),
        ("zero", {"dx": 0, "dy": 0, "frame_offset": 0}, "does not move"),
        ("primary", "primary", "reserved"),
        ("outside", {"dx": 80, "dy": 0, "frame_offset": 0}, "outside the stored frame"),
        ("offset", {"dx": 0, "dy": 0, "frame_offset": -1}, "outside the source"),
    ],
)
def test_invalid_seeds_are_refused(
    tmp_path: Path, pack: ScenarioPack, field: str, value: object, reason: str
) -> None:
    labels = load_labels(write_yaml(tmp_path / "labels.yaml", label_body(pack)), pack)
    body = seed_body(labels.space, labels.document_sha256)
    if field == "label":
        body["label_sha256"] = value
    elif field == "primary":
        body["perturbations"][0]["perturbation_id"] = value
    else:
        body["perturbations"][0].update(value)
    path = write_yaml(tmp_path / "seed.yaml", body)
    refused(lambda: load_seed(path, labels), reason)
