"""Comparing what two hosts staged: identical, or each difference named per source and frame."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import RefusalCode, compare_staged_hashes, record_staged_hashes
from ss_track.corpus.hosts.hash_comparison import HASH_COMPARISON_NAME
from tests.corpus._media import FRAME_COUNT
from tests.corpus.conftest import WriteCorpus, WriteRecording, last_record
from tests.corpus.hosts._host_hashes import (
    CORPUS,
    OTHER_HASH,
    RUN,
    bundle_line,
    compare_refusal,
    declare_and_stage,
    other_host,
    stage_on_other_host,
)


@pytest.fixture
def declared(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> tuple[Path, Path]:
    return declare_and_stage(write_recording, write_corpus, data_root)


@pytest.fixture
def left(declared: tuple[Path, Path], data_root: Path) -> Path:
    return record_staged_hashes(CORPUS, RUN, data_root).record_path


@pytest.fixture
def right(declared: tuple[Path, Path], tmp_path: Path) -> Path:
    return stage_on_other_host(declared, tmp_path)


def _changed_frame(record: dict[str, Any]) -> None:
    """A stream that decoded differently moves its own hash, its case's and the frame set."""
    record["frame_set_sha256"] = OTHER_HASH
    stream = bundle_line(record, "one")
    stream["bundle_sha256"] = OTHER_HASH
    stream["frames"][3][2] = OTHER_HASH
    stream["frames"][5][2] = OTHER_HASH
    case = bundle_line(record, "one-blur")
    case["bundle_sha256"] = OTHER_HASH


def test_equal_frame_sets_compare_identical_and_keep_the_comparison(
    left: Path, right: Path, data_root: Path
) -> None:
    result = compare_staged_hashes(left, right, RUN, data_root)

    assert result.comparison["status"] == "identical"
    assert result.comparison["sources"] == []
    assert result.comparison["source_count"] == 1
    assert result.comparison["bundle_count"] == 2
    assert result.record_path == data_root / "run" / RUN / HASH_COMPARISON_NAME
    assert json.loads(result.record_path.read_text(encoding="ascii"))["status"] == "identical"


def test_a_host_of_another_architecture_stays_named_in_an_identical_result(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = other_host(left, tmp_path, lambda record: record["host"].update(machine="aarch64"))

    comparison = compare_staged_hashes(left, other, RUN, data_root).comparison

    assert comparison["status"] == "identical"
    assert comparison["right"]["host"]["machine"] == "aarch64"  # type: ignore[index, call-overload]


def test_a_differing_frame_is_recorded_per_source_with_where_it_starts(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = other_host(left, tmp_path, _changed_frame)

    refusal = compare_refusal(left, other, data_root)

    source = refusal.details["sources"][0]  # type: ignore[index]
    stream = source["bundles"][0]  # type: ignore[index, call-overload]
    assert refusal.code is RefusalCode.STAGED_HASHES_DIFFER
    assert refusal.details["status"] == "different"
    assert source["codec"] == "mjpeg"  # type: ignore[index, call-overload]
    assert source["source_record_differs"] is False  # type: ignore[index, call-overload]
    assert source["source_pixel_format"] == "yuvj420p"  # type: ignore[index, call-overload]
    assert stream["stream_id"] == "one"  # type: ignore[index, call-overload]
    assert stream["right_bundle_sha256"] == OTHER_HASH  # type: ignore[index, call-overload]
    assert stream["frame_count"] == FRAME_COUNT  # type: ignore[index, call-overload]
    assert stream["differing_frames"] == 2  # type: ignore[index, call-overload]
    assert stream["first_differing_frame"] == 3  # type: ignore[index, call-overload]


def test_a_negative_result_is_kept_on_disk_as_well_as_refused(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = other_host(left, tmp_path, _changed_frame)

    refusal = compare_refusal(left, other, data_root)

    path = data_root / "run" / RUN / HASH_COMPARISON_NAME
    kept = json.loads(path.read_text(encoding="ascii"))
    assert kept["status"] == "different"
    assert kept["sources"] == refusal.details["sources"]
    assert refusal.details["record_path"] == str(path)


def test_a_case_that_moved_only_with_its_parent_says_no_frame_differs(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    """A case's identity covers its parent's hash, so it can differ with equal frames."""
    other = other_host(left, tmp_path, _changed_frame)

    source = compare_refusal(left, other, data_root).details["sources"][0]  # type: ignore[index]

    case = source["bundles"][1]  # type: ignore[index, call-overload]
    assert case["parent_stream_id"] == "one"  # type: ignore[index, call-overload]
    assert case["differing_frames"] == 0  # type: ignore[index, call-overload]
    assert case["first_differing_frame"] is None  # type: ignore[index, call-overload]


def test_a_changed_pts_and_a_frame_only_one_host_decoded_each_count(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    def change(record: dict[str, Any]) -> None:
        _changed_frame(record)
        stream = bundle_line(record, "one")
        stream["frames"][1][1] = 999_999
        stream["frames"].pop()

    other = other_host(left, tmp_path, change)

    source = compare_refusal(left, other, data_root).details["sources"][0]  # type: ignore[index]

    stream = source["bundles"][0]  # type: ignore[index, call-overload]
    assert stream["differing_frames"] == 4  # type: ignore[index, call-overload]
    assert stream["first_differing_frame"] == 1  # type: ignore[index, call-overload]


def test_a_source_record_can_differ_with_every_bundle_equal(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    """Unequal frame sets do not prove unequal bundles, so the comparison states which it was."""

    def change(record: dict[str, Any]) -> None:
        record["frame_set_sha256"] = OTHER_HASH
        record["corpus_manifest_sha256"] = OTHER_HASH
        record["sources"][0]["source_manifest_sha256"] = OTHER_HASH

    other = other_host(left, tmp_path, change)

    source = compare_refusal(left, other, data_root).details["sources"][0]  # type: ignore[index]

    assert source["source_record_differs"] is True  # type: ignore[index, call-overload]
    assert source["bundles"] == []  # type: ignore[index, call-overload]


def test_a_frame_set_that_differs_with_nothing_to_name_stays_different(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    """Finding no cause must not read as agreement: the frame sets still differ."""
    other = other_host(left, tmp_path, lambda record: record.update(frame_set_sha256=OTHER_HASH))

    refusal = compare_refusal(left, other, data_root)

    assert refusal.code is RefusalCode.STAGED_HASHES_DIFFER
    assert refusal.details["sources"] == []


def test_the_commands_exit_zero_when_identical_and_one_when_different(
    left: Path,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_root))
    caplog.set_level(logging.INFO)
    different = other_host(left, tmp_path, _changed_frame)
    compare = ["corpus", "compare", "--left", str(left), "--run-id", RUN, "--right"]

    assert main(["corpus", "hashes", "--corpus", CORPUS, "--run-id", "run-two"]) == EXIT_OK
    assert last_record(caplog)["status"] == "recorded"
    assert main([*compare, str(left)]) == EXIT_OK
    assert last_record(caplog)["status"] == "identical"
    assert main([*compare, str(different)]) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "STAGED_HASHES_DIFFER"
