"""A mask repeats the label dispositions and adds no score."""

from pathlib import Path

from ss_track.annotate.pack_model import ScenarioPack
from tests.annotate.documents import (
    frame,
    label_body,
    label_result,
    load_labels,
    load_mask,
    mask_body,
    refused,
    write_yaml,
)


def test_a_mask_repeats_the_label_and_can_exclude_a_scorable_episode(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels_path = write_yaml(tmp_path / "labels.yaml", label_body(pack))
    labels = load_labels(labels_path, pack)
    body = mask_body(
        labels.document_sha256, label_result(labels_path, labels, pack), labels.space.frame_count
    )
    mask = load_mask(write_yaml(tmp_path / "mask.yaml", body), labels)
    assert mask.frames[0].disposition == "scorable"
    assert mask.frames[0].reason is None
    assert mask.episodes[0].eligibility == "eligible"
    body["episodes"][0]["eligibility"] = "excluded"
    body["episodes"][0]["exclusion_reason"] = "operator withheld"
    excluded = load_mask(write_yaml(tmp_path / "excluded.yaml", body), labels)
    assert excluded.episodes[0].eligibility == "excluded"
    assert excluded.frames[0].disposition == "scorable"


def test_an_unscorable_frame_cannot_become_a_score(tmp_path: Path, pack: ScenarioPack) -> None:
    body = label_body(pack)
    body["instances"][0]["identity"] = "identity_ambiguous"
    labels_path = write_yaml(tmp_path / "labels.yaml", body)
    labels = load_labels(labels_path, pack)
    mask = mask_body(
        labels.document_sha256, label_result(labels_path, labels, pack), labels.space.frame_count
    )
    accepted = load_mask(write_yaml(tmp_path / "mask.yaml", mask), labels)
    assert accepted.frames[0].disposition == "unscorable"
    assert accepted.episodes[0].eligibility == "excluded"
    mask["frames"][0]["disposition"] = "scorable"
    mask["frames"][0]["reason"] = None
    mask["episodes"][0]["eligibility"] = "eligible"
    mask["episodes"][0]["exclusion_reason"] = None
    refused(
        lambda: load_mask(write_yaml(tmp_path / "promoted.yaml", mask), labels), "but the label is"
    )


def test_a_mask_that_omits_or_excuses_nothing_is_refused(
    tmp_path: Path, pack: ScenarioPack
) -> None:
    labels_document = label_body(pack)
    labels_document["instances"][0]["frames"].append(frame(1))
    labels_path = write_yaml(tmp_path / "labels.yaml", labels_document)
    labels = load_labels(labels_path, pack)
    body = mask_body(
        labels.document_sha256, label_result(labels_path, labels, pack), labels.space.frame_count
    )
    omitted = dict(body)
    omitted["frames"] = list(body["frames"][:-1])
    refused(lambda: load_mask(write_yaml(tmp_path / "omitted.yaml", omitted), labels), "omits")
    blank = dict(body)
    blank["episodes"] = [dict(body["episodes"][0])]
    blank["episodes"][0]["eligibility"] = "excluded"
    blank["episodes"][0]["exclusion_reason"] = " "
    refused(lambda: load_mask(write_yaml(tmp_path / "blank.yaml", blank), labels), "blank")
    excused = dict(body)
    excused["episodes"] = [dict(body["episodes"][0])]
    excused["episodes"][0]["exclusion_reason"] = "not eligible"
    refused(
        lambda: load_mask(write_yaml(tmp_path / "excused.yaml", excused), labels),
        "exclusion reason",
    )
