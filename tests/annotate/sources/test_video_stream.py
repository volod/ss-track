"""A file that holds two cameras: each video stream is its own source, as a corpus names it.

The first stream keeps the file hash. A later stream's identity is its stream identity, so a
label drawn on the second camera validates, compares and freezes against that identity only.
"""

import json
import logging
from pathlib import Path

import pytest
import yaml

from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.sources.frame_space import read_frame_space
from ss_track.cli import main
from ss_track.core.evidence.sealing import sha256_file
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import import_source
from ss_track.corpus.sources.identity import source_identity
from tests.annotate.documents import label_body, write_yaml
from tests.annotate.review_files import write_pair, write_review, write_settlement
from tests.annotate.sequence_files import (
    compare_command,
    freeze_command,
    logged_record,
    retain_sequence,
    validate_command,
)
from tests.corpus._media import (
    DUAL_FIRST_FRAMES,
    DUAL_SECOND_FRAMES,
    HEIGHT,
    WIDTH,
    write_dual_video,
)
from tests.corpus.conftest import recording_declaration

_SECOND = ["--video-stream-index", "1"]


@pytest.fixture
def dual(tmp_path: Path) -> Path:
    """Return one container whose two video streams differ in size and length."""
    return write_dual_video(tmp_path / "dual.mkv")


def test_each_stream_has_the_identity_a_corpus_names(dual: Path, tmp_path: Path) -> None:
    file_hash = sha256_file(dual)
    first = read_frame_space(dual, 0)
    second = read_frame_space(dual, 1)

    assert first.source_sha256 == file_hash
    assert (first.width, first.height, first.frame_count) == (WIDTH, HEIGHT, DUAL_FIRST_FRAMES)
    assert second.source_sha256 == source_identity(file_hash, 1) != file_hash
    assert (second.width, second.height) == (WIDTH // 2, HEIGHT // 2)
    assert second.frame_count == DUAL_SECOND_FRAMES
    declaration = recording_declaration("dual.mkv")
    declaration["source"] = {"path": "dual.mkv", "video_stream_index": 1}
    recording = tmp_path / "recording.yaml"
    recording.write_text(yaml.safe_dump(declaration), encoding="utf-8")
    assert import_source(recording, tmp_path / "data").source_sha256 == second.source_sha256


def test_an_unnamed_or_absent_stream_is_refused(dual: Path, tmp_path: Path) -> None:
    for index in (None, 2):
        with pytest.raises(CorpusRefusal) as caught:
            read_frame_space(dual, index)
        assert caught.value.code is RefusalCode.VIDEO_STREAM_UNSPECIFIED
    stored, _identity = retain_sequence(tmp_path / "sequence")
    with pytest.raises(CorpusRefusal, match="has no video stream index") as refused:
        read_frame_space(stored, 0)
    assert refused.value.code is RefusalCode.MANIFEST_INVALID


def test_the_second_camera_validates_compares_and_freezes(
    dual: Path, tmp_path: Path, pack: ScenarioPack, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    space = read_frame_space(dual, 1)
    write_pair(tmp_path, pack, lambda _body: None, space)
    write_review(tmp_path)
    write_settlement(tmp_path, [])
    labels = tmp_path / "left.yaml"

    assert main(validate_command("label", labels, dual)) == 1
    assert logged_record(caplog)["code"] == RefusalCode.VIDEO_STREAM_UNSPECIFIED
    assert main([*validate_command("label", labels, dual), *_SECOND]) == 0
    assert main([*compare_command(tmp_path, dual), *_SECOND]) == 0
    assert main([*freeze_command(tmp_path, dual), *_SECOND]) == 0
    frozen = json.loads((tmp_path / "frozen.json").read_text(encoding="ascii"))
    revision = json.loads((tmp_path / "revision.json").read_text(encoding="ascii"))
    assert frozen["source_sha256"] == revision["source_sha256"] == space.source_sha256


def test_the_file_hash_is_not_the_second_camera(
    dual: Path, tmp_path: Path, pack: ScenarioPack, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    space = read_frame_space(dual, 1)
    body = label_body(pack, space)
    body["source_sha256"] = sha256_file(dual)
    labels = write_yaml(tmp_path / "file-hash.yaml", body)

    assert main([*validate_command("label", labels, dual), *_SECOND]) == 1
    record = logged_record(caplog)
    assert record["code"] == RefusalCode.MANIFEST_INVALID
    assert "source_sha256" in str(record["message"])
    assert space.source_sha256 in str(record["message"])
