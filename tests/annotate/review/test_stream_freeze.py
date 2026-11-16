"""`annotate freeze --corpus --stream` reads the stream's stored source and files the labels there.

The join to the stream is made at freeze time, so labels are never frozen against one source
and filed under another, and a stream with no generated case is checked too.
"""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import main
from ss_track.core.refusal import RefusalCode
from ss_track.corpus.storage.layout import corpus_manifest_path, labels_directory
from tests.annotate.derived_corpus import CORPUS, STREAM, copy_data, derive
from tests.annotate.sequence_files import logged_record
from tests.annotate.support import DRAFT
from tests.corpus.conftest import reseal


def _freeze(folder: Path, *extra: str) -> list[str]:
    return [
        "annotate",
        "freeze",
        "--left",
        str(folder / "left.yaml"),
        "--right",
        str(folder / "right.yaml"),
        "--pack",
        str(DRAFT),
        "--review",
        str(folder / "review.yaml"),
        "--settlement",
        str(folder / "settlement.yaml"),
        *extra,
    ]


def _by_stream(folder: Path, stream: str = STREAM) -> list[str]:
    return _freeze(folder, "--corpus", CORPUS, "--stream", stream)


def test_a_stream_freeze_files_the_revision_under_its_stream(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data, clip, folder = built
    copied = copy_data(data, tmp_path)
    monkeypatch.setenv("DATA_DIR", str(copied))
    caplog.set_level(logging.INFO)

    assert main(_by_stream(folder)) == 0
    record: dict[str, Any] = logged_record(caplog)["label_review"]  # type: ignore[assignment]
    home = labels_directory(copied, CORPUS) / STREAM
    assert record["labels_path"] == str(home / "labels.json")
    assert record["revision_path"] == str(home / "revision.json")
    by_paths = json.loads((folder / "revision.json").read_text(encoding="ascii"))
    assert record["revision_sha256"] == by_paths["manifest_sha256"]
    assert main(_by_stream(folder)) == 0
    derived = derive(copied, monkeypatch, caplog)
    assert {case["status"] for case in derived["label_derivation"]["cases"]} == {"derived"}
    assert clip.is_file()


def test_a_stream_freeze_refuses_mixed_or_unknown_addresses(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data, clip, folder = built
    copied = copy_data(data, tmp_path)
    monkeypatch.setenv("DATA_DIR", str(copied))
    caplog.set_level(logging.INFO)
    refused = {
        "are given together": _freeze(folder, "--corpus", CORPUS),
        "replace --source": [*_by_stream(folder), "--source", str(clip)],
        "or --corpus and --stream": _freeze(folder, "--source", str(clip)),
        "is a generated case": _by_stream(folder, "shake"),
        "has no stream nope": _by_stream(folder, "nope"),
    }

    for reason, command in refused.items():
        assert main(command) == 1
        record = logged_record(caplog)
        assert record["code"] == RefusalCode.MANIFEST_INVALID
        assert reason in str(record["message"])
    assert not labels_directory(copied, CORPUS).exists()


def test_a_stream_of_another_frame_shape_is_refused_at_freeze(
    built: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    data, _clip, folder = built
    copied = copy_data(data, tmp_path)
    monkeypatch.setenv("DATA_DIR", str(copied))
    caplog.set_level(logging.INFO)
    manifest = corpus_manifest_path(copied, CORPUS)
    streams: list[dict[str, Any]] = json.loads(manifest.read_text(encoding="ascii"))["streams"]
    streams[0]["frame_count"] = 23
    reseal(manifest, streams=streams)

    assert main(_by_stream(folder)) == 1
    record = logged_record(caplog)
    assert record["code"] == RefusalCode.MANIFEST_INVALID
    assert f"stream {STREAM} is 23" in str(record["message"])
    assert not labels_directory(copied, CORPUS).exists()
