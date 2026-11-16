"""Annotation commands accept a retained image sequence and its sequence identity."""

import json
import logging
from pathlib import Path

import pytest

from ss_track.annotate.declarations.contracts import MASK_CONTRACT, read_version
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.annotate.validation.result import AnnotationEntry, AnnotationResult
from ss_track.annotate.validation.validate import validate_labels, validate_seed
from ss_track.cli import main
from ss_track.core.evidence.sealing import sha256_file
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.sources.image_sequence import image_name
from tests.annotate.documents import label_body, mask_body, seed_body, write_yaml
from tests.annotate.review_files import write_pair, write_review, write_settlement
from tests.annotate.sequence_files import (
    compare_command,
    freeze_command,
    logged_record,
    retain_sequence,
    validate_command,
)
from tests.annotate.support import DRAFT
from tests.corpus._images import image

_OTHER_HASH = "ab" * 32


def test_validate_accepts_a_sequence_label_seed_and_mask(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    stored, identity = retain_sequence(tmp_path / "seq")
    space = read_frame_space(stored)
    assert space.source_sha256 == identity
    assert identity != sha256_file(rotated_clip)
    assert identity != sha256_file(stored / image_name(0))
    assert (space.width, space.height, space.frame_count) == (8, 8, 2)
    assert space.time_base == "1/25"
    assert space.pts == (0, 1)
    labels = write_yaml(tmp_path / "labels.yaml", label_body(pack, space))
    assert main(validate_command("label", labels, stored)) == 0
    record = logged_record(caplog)
    assert record["annotation"]["kind"] == "label"
    assert record["annotation"]["entries"][0]["disposition"] == "scorable"
    label_hash = str(record["annotation"]["document_sha256"])
    seed = seed_body(space, label_hash)
    assert space.pts[0] is not None
    seed["pts"] = space.pts[0]
    seed["time_base"] = space.time_base
    seed_path = write_yaml(tmp_path / "seed.yaml", seed)
    assert main(validate_command("seed", seed_path, stored, labels)) == 0
    entries = tuple(
        AnnotationEntry(
            str(row["entry_id"]), int(row["frame_index"]), row["disposition"], row["reason"]
        )
        for row in record["annotation"]["entries"]
    )
    reported = AnnotationResult(
        labels, MASK_CONTRACT, read_version(MASK_CONTRACT), "mask", label_hash, None, None, entries
    )
    mask = write_yaml(tmp_path / "mask.yaml", mask_body(label_hash, reported, space.frame_count))
    assert main(validate_command("mask", mask, stored, labels)) == 0
    assert logged_record(caplog)["annotation"]["kind"] == "mask"
    assert "score" not in logged_record(caplog)["annotation"]


@pytest.mark.parametrize("digest_name", ["video", "other"])
def test_a_label_hash_other_than_the_sequence_identity_is_refused(
    tmp_path: Path,
    pack: ScenarioPack,
    rotated_clip: Path,
    digest_name: str,
) -> None:
    stored, identity = retain_sequence(tmp_path / "seq")
    space = read_frame_space(stored)
    digest = sha256_file(rotated_clip) if digest_name == "video" else _OTHER_HASH
    body = label_body(pack, space)
    body["source_sha256"] = digest
    path = write_yaml(tmp_path / "labels.yaml", body)
    with pytest.raises(CorpusRefusal) as caught:
        validate_labels(path, DRAFT, stored)
    assert caught.value.code == RefusalCode.MANIFEST_INVALID
    message = str(caught.value)
    assert "source_sha256" in message
    assert digest in message
    assert identity in message


def test_a_seed_with_a_video_file_hash_is_refused(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    stored, _identity = retain_sequence(tmp_path / "seq")
    space = read_frame_space(stored)
    labels = write_yaml(tmp_path / "labels.yaml", label_body(pack, space))
    label_hash = validate_labels(labels, DRAFT, stored).document_sha256
    body = seed_body(space, label_hash)
    body["source_sha256"] = sha256_file(rotated_clip)
    with pytest.raises(CorpusRefusal) as caught:
        validate_seed(write_yaml(tmp_path / "seed.yaml", body), labels, DRAFT, stored)
    assert caught.value.code == RefusalCode.MANIFEST_INVALID
    assert "source_sha256" in str(caught.value)


def test_a_label_must_match_the_decoded_frame(tmp_path: Path, pack: ScenarioPack) -> None:
    stored, _identity = retain_sequence(tmp_path / "seq")
    space = read_frame_space(stored)
    body = label_body(pack, space)
    body["width"] = space.width + 1
    with pytest.raises(CorpusRefusal) as caught:
        validate_labels(write_yaml(tmp_path / "wide.yaml", body), DRAFT, stored)
    assert caught.value.code == RefusalCode.MANIFEST_INVALID
    assert "width" in str(caught.value)


def test_compare_and_freeze_use_the_sequence_identity(
    tmp_path: Path, pack: ScenarioPack, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    stored, identity = retain_sequence(tmp_path / "seq")
    space = read_frame_space(stored)
    write_pair(tmp_path, pack, lambda _body: None, space)
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    assert main(compare_command(tmp_path, stored)) == 0
    assert logged_record(caplog)["status"] == "valid"
    assert "score" not in logged_record(caplog)["label_review"]
    assert main(freeze_command(tmp_path, stored)) == 0
    assert logged_record(caplog)["status"] == "frozen"
    frozen = json.loads((tmp_path / "frozen.json").read_text(encoding="ascii"))
    revision = json.loads((tmp_path / "revision.json").read_text(encoding="ascii"))
    assert frozen["source_sha256"] == identity
    assert revision["source_sha256"] == identity


def test_compare_and_freeze_refuse_a_video_file_hash(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    stored, _identity = retain_sequence(tmp_path / "seq")
    space = read_frame_space(stored)
    digest = sha256_file(rotated_clip)
    for name, annotator in (("left.yaml", "ann-a"), ("right.yaml", "ann-b")):
        body = label_body(pack, space)
        body["source_sha256"] = digest
        body["instances"][0]["frames"][0]["annotator_id"] = annotator
        write_yaml(tmp_path / name, body)
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    assert main(compare_command(tmp_path, stored)) == 1
    assert logged_record(caplog)["code"] == RefusalCode.MANIFEST_INVALID
    assert "source_sha256" in str(logged_record(caplog)["message"])
    assert main(freeze_command(tmp_path, stored)) == 1
    assert not (tmp_path / "frozen.json").exists()
    assert not (tmp_path / "revision.json").exists()


def test_a_directory_of_images_without_an_inventory_is_refused(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    loose = tmp_path / "images"
    loose.mkdir()
    image(loose / "00000000.png", 1, 8, height=8)
    image(loose / "00000001.png", 2, 8, height=8)
    assert main(validate_command("label", tmp_path / "labels.yaml", loose)) == 1
    record = logged_record(caplog)
    assert record["code"] == RefusalCode.SOURCE_NOT_FOUND
    assert "not a video file or an image sequence" in str(record["message"])


def test_a_changed_image_or_extra_file_is_refused(tmp_path: Path) -> None:
    stored, _identity = retain_sequence(tmp_path / "changed")
    target = stored / image_name(0)
    target.chmod(0o644)
    target.write_bytes(b"changed")
    with pytest.raises(CorpusRefusal) as changed:
        read_frame_space(stored)
    assert changed.value.code == RefusalCode.SOURCE_HASH_MISMATCH
    assert f"image changed: {image_name(0)}" in str(changed.value)
    extra, _identity = retain_sequence(tmp_path / "extra")
    (extra / "extra.png").write_bytes(b"extra")
    with pytest.raises(CorpusRefusal) as membership:
        read_frame_space(extra)
    assert membership.value.code == RefusalCode.SOURCE_HASH_MISMATCH
    assert "sequence membership changed" in str(membership.value)


def test_mixed_image_geometry_is_refused(tmp_path: Path) -> None:
    stored, _identity = retain_sequence(tmp_path / "mixed", widths=(8, 6))
    with pytest.raises(CorpusRefusal) as caught:
        read_frame_space(stored)
    assert caught.value.code == RefusalCode.SOURCE_FORMAT_CHANGED


def test_a_damaged_inventory_is_refused(tmp_path: Path) -> None:
    stored, _identity = retain_sequence(tmp_path / "damaged")
    index = stored / "index.json"
    index.chmod(0o644)
    index.write_text("{}\n", encoding="ascii")
    with pytest.raises(CorpusRefusal) as caught:
        read_frame_space(stored)
    assert caught.value.code == RefusalCode.RECORD_TAMPERED


def test_a_sequence_without_a_rate_keeps_missing_timestamps(tmp_path: Path) -> None:
    stored, identity = retain_sequence(tmp_path, rate=None)
    space = read_frame_space(stored)
    assert space.source_sha256 == identity
    assert space.time_base is None
    assert space.pts == (None, None)


def test_a_video_file_keeps_its_file_hash(
    tmp_path: Path, pack: ScenarioPack, rotated_clip: Path
) -> None:
    video = read_frame_space(rotated_clip)
    assert video.source_sha256 == sha256_file(rotated_clip)
    _stored, identity = retain_sequence(tmp_path / "seq")
    body = label_body(pack, video)
    body["source_sha256"] = identity
    with pytest.raises(CorpusRefusal) as caught:
        validate_labels(write_yaml(tmp_path / "labels.yaml", body), DRAFT, rotated_clip)
    assert caught.value.code == RefusalCode.MANIFEST_INVALID
    assert "source_sha256" in str(caught.value)
    assert identity in str(caught.value)
