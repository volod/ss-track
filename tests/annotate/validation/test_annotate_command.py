"""`ss-track annotate validate` on a video whose display rotation is recorded."""

import json
import logging
from pathlib import Path

import pytest

from ss_track.annotate.declarations.contracts import (
    LABEL_CONTRACT,
    MASK_CONTRACT,
    SEED_CONTRACT,
    read_version,
)
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.annotate.validation.result import AnnotationEntry, AnnotationResult
from ss_track.cli import main
from ss_track.core.refusal import RefusalCode
from ss_track.schema.registry.store import load_contract_set
from tests.annotate.documents import label_body, mask_body, seed_body, write_yaml
from tests.annotate.support import DRAFT


def test_validate_reports_a_label_a_seed_and_a_mask(
    tmp_path: Path, pack: object, rotated_clip: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    space = read_frame_space(rotated_clip)
    labels = write_yaml(tmp_path / "labels.yaml", label_body(pack, space))
    assert main(_command("label", labels, rotated_clip)) == 0
    record = _record(caplog)
    assert record["annotation"]["kind"] == "label"
    assert record["annotation"]["entries"][0]["disposition"] == "scorable"
    assert record["version"] == _newest(LABEL_CONTRACT)
    label_hash = str(record["annotation"]["document_sha256"])
    seed = write_yaml(tmp_path / "seed.yaml", seed_body(space, label_hash))
    assert main(_command("seed", seed, rotated_clip, labels)) == 0
    assert _record(caplog)["version"] == _newest(SEED_CONTRACT)
    replay = _record(caplog)["annotation"]["replay_sha256"]
    assert main(_command("seed", seed, rotated_clip, labels)) == 0
    assert _record(caplog)["annotation"]["replay_sha256"] == replay
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
    assert main(_command("mask", mask, rotated_clip, labels)) == 0
    assert _record(caplog)["annotation"]["kind"] == "mask"
    assert _record(caplog)["version"] == _newest(MASK_CONTRACT)
    assert "score" not in _record(caplog)["annotation"]


def test_validate_refuses_a_label_drawn_in_the_display_orientation(
    tmp_path: Path, pack: object, rotated_clip: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    space = read_frame_space(rotated_clip)
    body = label_body(pack, space)
    body["orientation_degrees"] = 90
    path = write_yaml(tmp_path / "turned.yaml", body)
    assert main(_command("label", path, rotated_clip)) == 1
    record = _record(caplog)
    assert record["code"] == RefusalCode.MANIFEST_INVALID
    assert "stored orientation" in str(record["message"])


def test_validate_requires_labels_for_a_seed(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    assert (
        main(
            [
                "annotate",
                "validate",
                "--kind",
                "seed",
                "--file",
                "seed.yaml",
                "--pack",
                "pack.yaml",
                "--source",
                "clip.mp4",
            ]
        )
        == 1
    )
    record = _record(caplog)
    assert record["code"] == RefusalCode.MANIFEST_INVALID
    assert "--labels is required" in str(record["message"])


def test_validate_refuses_a_directory(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    assert main(_command("label", tmp_path / "labels.yaml", tmp_path)) == 1
    record = _record(caplog)
    assert record["code"] == RefusalCode.SOURCE_NOT_FOUND
    assert "not a video file" in str(record["message"])


def _command(kind: str, path: Path, source: Path, labels: Path | None = None) -> list[str]:
    command = [
        "annotate",
        "validate",
        "--kind",
        kind,
        "--file",
        str(path),
        "--pack",
        str(DRAFT),
        "--source",
        str(source),
    ]
    if labels is not None:
        command.extend(["--labels", str(labels)])
    return command


def _record(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    return json.loads(caplog.records[-1].getMessage())


def _newest(contract_name: str) -> str:
    """Return the newest frozen version of one contract, read from the registry itself."""
    frozen = load_contract_set().named(contract_name).newest()
    assert frozen is not None
    return frozen.version
