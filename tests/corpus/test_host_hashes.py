"""Recording what one host staged, and comparing it with what another host staged."""

import json
import logging
import platform
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import EXIT_OK, EXIT_REFUSED, main
from ss_track.corpus import (
    CorpusRefusal,
    RefusalCode,
    build_corpus,
    compare_staged_hashes,
    import_source,
    open_frame_bundle,
    record_staged_hashes,
    stage_corpus,
)
from ss_track.corpus.hash_comparison import HASH_COMPARISON_NAME
from ss_track.corpus.host_hashes import STAGED_HASHES_NAME, run_directory
from ss_track.corpus.sealed import SEAL_FIELD, seal
from tests.corpus._media import FRAME_COUNT
from tests.corpus.conftest import WriteCorpus, WriteRecording, case_of, stream_of

_CORPUS = "pilot-v1"
_RUN = "run-one"
_OTHER_HASH = "f" * 64
_BLUR = case_of("one-blur", "blur", 7, {"max_radius": 2})

type Change = Callable[[dict[str, Any]], None]


@pytest.fixture
def declared(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> tuple[Path, Path]:
    """Declare one source with one generated case, and stage them on the first host."""
    recording = write_recording()
    result = import_source(recording, data_root)
    corpus = write_corpus([stream_of(result, generated_cases=[_BLUR])])
    build_corpus(corpus, data_root)
    stage_corpus(_CORPUS, data_root)
    return recording, corpus


@pytest.fixture
def left(declared: tuple[Path, Path], data_root: Path) -> Path:
    return record_staged_hashes(_CORPUS, _RUN, data_root).record_path


@pytest.fixture
def right(declared: tuple[Path, Path], tmp_path: Path) -> Path:
    """The same corpus staged on another data root, standing for the other host."""
    other_root = tmp_path / "other-host"
    recording, corpus = declared
    import_source(recording, other_root)
    build_corpus(corpus, other_root)
    stage_corpus(_CORPUS, other_root)
    return record_staged_hashes(_CORPUS, _RUN, other_root).record_path


def _other_host(path: Path, target_root: Path, change: Change) -> Path:
    """Change a copy of a record as another host's would differ, keeping its seal whole."""
    target = target_root / "changed" / STAGED_HASHES_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    record = json.loads(path.read_text(encoding="ascii"))
    record.pop(SEAL_FIELD)
    change(record)
    target.write_text(json.dumps(seal(record)), encoding="ascii")
    return target


def _line(record: dict[str, Any], stream_id: str) -> dict[str, Any]:
    return next(line for line in record["bundles"] if line["stream_id"] == stream_id)


def _changed_frame(record: dict[str, Any]) -> None:
    """A stream that decoded differently moves its own hash, its case's and the frame set."""
    record["frame_set_sha256"] = _OTHER_HASH
    stream = _line(record, "one")
    stream["bundle_sha256"] = _OTHER_HASH
    stream["frames"][3][2] = _OTHER_HASH
    stream["frames"][5][2] = _OTHER_HASH
    case = _line(record, "one-blur")
    case["bundle_sha256"] = _OTHER_HASH


def _refusal(left: Path, right: Path, data_root: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        compare_staged_hashes(left, right, _RUN, data_root)
    return caught.value


def test_a_record_names_every_bundle_frame_and_source_beside_the_host(
    left: Path, data_root: Path
) -> None:
    record = json.loads(left.read_text(encoding="ascii"))
    stream = _line(record, "one")
    ref = open_frame_bundle(data_root / "corpus" / _CORPUS / "frames" / "one").frame_ref(2)

    assert left == data_root / "run" / _RUN / STAGED_HASHES_NAME
    assert {line["stream_id"] for line in record["bundles"]} == {"one", "one-blur"}
    assert _line(record, "one-blur")["parent_stream_id"] == "one"
    assert stream["frames"][2] == [2, ref.pts, ref.sha256]
    assert ref.pts is not None
    assert record["sources"][0]["codec"] == "mjpeg"
    assert record["sources"][0]["source_pixel_format"] == "yuvj420p"
    assert record["host"] == {
        "machine": platform.machine(),
        "system": platform.system(),
        "python": platform.python_version(),
    }


def test_a_record_states_the_machine_it_ran_on(
    declared: tuple[Path, Path], data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "machine", lambda: "aarch64")

    result = record_staged_hashes(_CORPUS, _RUN, data_root)

    assert result.host["machine"] == "aarch64"
    assert json.loads(result.record_path.read_text(encoding="ascii"))["host"] == result.host


def test_a_record_states_frames_on_disk_so_damage_writes_none(
    declared: tuple[Path, Path], data_root: Path
) -> None:
    frame = data_root / "corpus" / _CORPUS / "frames" / "one" / "00000002.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"corrupted")

    with pytest.raises(CorpusRefusal) as caught:
        record_staged_hashes(_CORPUS, _RUN, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert not (data_root / "run").exists()


def test_a_corpus_that_never_staged_has_no_record(data_root: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        record_staged_hashes(_CORPUS, _RUN, data_root)

    assert caught.value.code is RefusalCode.CORPUS_NOT_BUILT


def test_equal_frame_sets_compare_identical_and_keep_the_comparison(
    left: Path, right: Path, data_root: Path
) -> None:
    result = compare_staged_hashes(left, right, _RUN, data_root)

    assert result.comparison["status"] == "identical"
    assert result.comparison["sources"] == []
    assert result.comparison["source_count"] == 1
    assert result.comparison["bundle_count"] == 2
    assert result.record_path == data_root / "run" / _RUN / HASH_COMPARISON_NAME
    assert json.loads(result.record_path.read_text(encoding="ascii"))["status"] == "identical"


def test_a_host_of_another_architecture_stays_named_in_an_identical_result(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = _other_host(left, tmp_path, lambda record: record["host"].update(machine="aarch64"))

    comparison = compare_staged_hashes(left, other, _RUN, data_root).comparison

    assert comparison["status"] == "identical"
    assert comparison["right"]["host"]["machine"] == "aarch64"  # type: ignore[index, call-overload]


def test_a_differing_frame_is_recorded_per_source_with_where_it_starts(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = _other_host(left, tmp_path, _changed_frame)

    refusal = _refusal(left, other, data_root)

    source = refusal.details["sources"][0]  # type: ignore[index]
    stream = source["bundles"][0]  # type: ignore[index, call-overload]
    assert refusal.code is RefusalCode.STAGED_HASHES_DIFFER
    assert refusal.details["status"] == "different"
    assert source["codec"] == "mjpeg"  # type: ignore[index, call-overload]
    assert source["source_record_differs"] is False  # type: ignore[index, call-overload]
    assert source["source_pixel_format"] == "yuvj420p"  # type: ignore[index, call-overload]
    assert stream["stream_id"] == "one"  # type: ignore[index, call-overload]
    assert stream["right_bundle_sha256"] == _OTHER_HASH  # type: ignore[index, call-overload]
    assert stream["frame_count"] == FRAME_COUNT  # type: ignore[index, call-overload]
    assert stream["differing_frames"] == 2  # type: ignore[index, call-overload]
    assert stream["first_differing_frame"] == 3  # type: ignore[index, call-overload]


def test_a_negative_result_is_kept_on_disk_as_well_as_refused(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = _other_host(left, tmp_path, _changed_frame)

    refusal = _refusal(left, other, data_root)

    path = data_root / "run" / _RUN / HASH_COMPARISON_NAME
    kept = json.loads(path.read_text(encoding="ascii"))
    assert kept["status"] == "different"
    assert kept["sources"] == refusal.details["sources"]
    assert refusal.details["record_path"] == str(path)


def test_a_case_that_moved_only_with_its_parent_says_no_frame_differs(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    """A case's identity covers its parent's hash, so it can differ with equal frames."""
    other = _other_host(left, tmp_path, _changed_frame)

    source = _refusal(left, other, data_root).details["sources"][0]  # type: ignore[index]

    case = source["bundles"][1]  # type: ignore[index, call-overload]
    assert case["parent_stream_id"] == "one"  # type: ignore[index, call-overload]
    assert case["differing_frames"] == 0  # type: ignore[index, call-overload]
    assert case["first_differing_frame"] is None  # type: ignore[index, call-overload]


def test_a_changed_pts_and_a_frame_only_one_host_decoded_each_count(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    def change(record: dict[str, Any]) -> None:
        _changed_frame(record)
        stream = _line(record, "one")
        stream["frames"][1][1] = 999_999
        stream["frames"].pop()

    other = _other_host(left, tmp_path, change)

    source = _refusal(left, other, data_root).details["sources"][0]  # type: ignore[index]

    stream = source["bundles"][0]  # type: ignore[index, call-overload]
    assert stream["differing_frames"] == 4  # type: ignore[index, call-overload]
    assert stream["first_differing_frame"] == 1  # type: ignore[index, call-overload]


def test_a_source_record_can_differ_with_every_bundle_equal(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    """Unequal frame sets do not prove unequal bundles, so the comparison states which it was."""

    def change(record: dict[str, Any]) -> None:
        record["frame_set_sha256"] = _OTHER_HASH
        record["corpus_manifest_sha256"] = _OTHER_HASH
        record["sources"][0]["source_manifest_sha256"] = _OTHER_HASH

    other = _other_host(left, tmp_path, change)

    source = _refusal(left, other, data_root).details["sources"][0]  # type: ignore[index]

    assert source["source_record_differs"] is True  # type: ignore[index, call-overload]
    assert source["bundles"] == []  # type: ignore[index, call-overload]


def test_a_frame_set_that_differs_with_nothing_to_name_stays_different(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    """Finding no cause must not read as agreement: the frame sets still differ."""
    other = _other_host(left, tmp_path, lambda record: record.update(frame_set_sha256=_OTHER_HASH))

    refusal = _refusal(left, other, data_root)

    assert refusal.code is RefusalCode.STAGED_HASHES_DIFFER
    assert refusal.details["sources"] == []


@pytest.mark.parametrize(
    ("change", "unmatched"),
    [
        pytest.param(lambda r: r.update(corpus_id="pilot-v2"), "corpus_id", id="corpus"),
        pytest.param(
            lambda r: r.update(decode_policy_sha256=_OTHER_HASH),
            "decode_policy_sha256",
            id="decoder",
        ),
        pytest.param(
            lambda r: r["sources"][0].update(source_sha256=_OTHER_HASH), "sources", id="sources"
        ),
        pytest.param(lambda r: r["bundles"].pop(), "bundles", id="bundles"),
    ],
)
def test_records_of_different_questions_are_refused_and_nothing_is_kept(
    left: Path, data_root: Path, tmp_path: Path, change: Change, unmatched: str
) -> None:
    other = _other_host(left, tmp_path, change)

    refusal = _refusal(left, other, data_root)

    assert refusal.code is RefusalCode.HASHES_NOT_COMPARABLE
    assert refusal.details["unmatched"] == [unmatched]
    assert not (data_root / "run" / _RUN / HASH_COMPARISON_NAME).exists()


def test_a_changed_record_is_refused_by_its_seal(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = tmp_path / STAGED_HASHES_NAME
    other.write_text(left.read_text(encoding="ascii").replace("mjpeg", "h264"), encoding="ascii")

    assert _refusal(left, other, data_root).code is RefusalCode.RECORD_TAMPERED


def test_a_record_of_another_schema_is_refused(left: Path, data_root: Path, tmp_path: Path) -> None:
    other = _other_host(left, tmp_path, lambda record: record.update(schema_version=99))

    assert _refusal(left, other, data_root).code is RefusalCode.RECORD_SCHEMA_UNSUPPORTED


def test_a_sealed_record_with_a_field_missing_is_refused(
    left: Path, data_root: Path, tmp_path: Path
) -> None:
    other = _other_host(left, tmp_path, lambda record: record.pop("sources"))

    assert _refusal(left, other, data_root).code is RefusalCode.RECORD_TAMPERED


@pytest.mark.parametrize("run_id", ["../escape", "", "Upper"])
def test_a_run_id_that_cannot_name_a_directory_is_refused(data_root: Path, run_id: str) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        run_directory(data_root, run_id)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_the_commands_exit_zero_when_identical_and_one_when_different(
    left: Path,
    data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_root))
    caplog.set_level(logging.INFO)
    different = _other_host(left, tmp_path, _changed_frame)
    compare = ["corpus", "compare", "--left", str(left), "--run-id", _RUN, "--right"]

    assert main(["corpus", "hashes", "--corpus", _CORPUS, "--run-id", "run-two"]) == EXIT_OK
    assert json.loads(caplog.records[-1].getMessage())["status"] == "recorded"
    assert main([*compare, str(left)]) == EXIT_OK
    assert json.loads(caplog.records[-1].getMessage())["status"] == "identical"
    assert main([*compare, str(different)]) == EXIT_REFUSED
    assert json.loads(caplog.records[-1].getMessage())["code"] == "STAGED_HASHES_DIFFER"
