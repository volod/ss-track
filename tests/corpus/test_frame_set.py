"""The frame set: one sealed hash for everything a corpus version staged."""

import fcntl
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus import staging as staging_module
from ss_track.corpus.frame_set import commit_frame_set
from ss_track.corpus.staging import FramesResult
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    reseal,
    stream_of,
)

_CORPUS = "pilot-v1"
_SHAKE = {"amplitude": 2}

type Refused = Callable[[RefusalCode], CorpusRefusal]


def _frame_set(data_root: Path, corpus: str = _CORPUS) -> Path:
    return data_root / "corpus" / corpus / "frame-set.json"


def _bundle(data_root: Path, name: str) -> Path:
    return data_root / "corpus" / _CORPUS / "frames" / name


def _remove_bundle(data_root: Path, name: str) -> None:
    directory = _bundle(data_root, name)
    directory.chmod(0o755)
    shutil.rmtree(directory)


def _replace_bundle(data_root: Path, name: str, donor: str) -> None:
    """Put another stream's frames under a name, in a record consistent with itself."""
    _remove_bundle(data_root, name)
    shutil.copytree(_bundle(data_root, donor), _bundle(data_root, name))
    reseal(_bundle(data_root, name) / "manifest.json", stream_id=name)


def _record(path: Path) -> dict[str, object]:
    record: dict[str, object] = json.loads(path.read_text(encoding="ascii"))
    return record


def _hashes(result: FramesResult) -> dict[str, str]:
    return {bundle.stream_id: bundle.bundle_sha256 for bundle in result.bundles}


def _refused_by(action: Callable[[str, Path], FramesResult], root: Path) -> Refused:
    def refused(code: RefusalCode) -> CorpusRefusal:
        with pytest.raises(CorpusRefusal) as caught:
            action(_CORPUS, root)
        assert caught.value.code is code
        return caught.value

    return refused


@pytest.fixture
def staged(
    first: ImportResult, second: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> FramesResult:
    streams = [
        stream_of(
            first,
            stream_id="one",
            generated_cases=[case_of("shaken", "camera_shake", 1, _SHAKE)],
        ),
        stream_of(second, stream_id="two"),
    ]
    build_corpus(write_corpus(streams), data_root)
    return stage_corpus(_CORPUS, data_root)


@pytest.fixture
def verify_refuses(data_root: Path) -> Refused:
    return _refused_by(verify_corpus_frames, data_root)


@pytest.fixture
def stage_refuses(data_root: Path) -> Refused:
    return _refused_by(stage_corpus, data_root)


def test_staging_names_every_bundle_and_the_source_record_it_rests_on(
    staged: FramesResult, first: ImportResult, second: ImportResult, data_root: Path
) -> None:
    record = _record(_frame_set(data_root))
    hashes = _hashes(staged)
    corpus = _record(data_root / "corpus" / _CORPUS / "manifest.json")

    assert record == {
        "kind": "ss-track.frame-set",
        "schema_version": 1,
        "corpus_id": _CORPUS,
        "corpus_manifest_sha256": corpus["manifest_sha256"],
        "bundles": [
            {
                "stream_id": "one",
                "parent_stream_id": None,
                "bundle_sha256": hashes["one"],
                "source_sha256": first.source_sha256,
                "source_manifest_sha256": first.manifest_sha256,
            },
            {
                "stream_id": "shaken",
                "parent_stream_id": "one",
                "bundle_sha256": hashes["shaken"],
                "source_sha256": first.source_sha256,
                "source_manifest_sha256": first.manifest_sha256,
            },
            {
                "stream_id": "two",
                "parent_stream_id": None,
                "bundle_sha256": hashes["two"],
                "source_sha256": second.source_sha256,
                "source_manifest_sha256": second.manifest_sha256,
            },
        ],
        "manifest_sha256": staged.frame_set_sha256,
    }


def test_a_verified_corpus_reports_the_hash_a_scenario_pins(
    staged: FramesResult, data_root: Path
) -> None:
    assert verify_corpus_frames(_CORPUS, data_root).frame_set_sha256 == staged.frame_set_sha256
    assert stage_corpus(_CORPUS, data_root).frame_set_sha256 == staged.frame_set_sha256


def test_the_record_is_read_only(staged: FramesResult, data_root: Path) -> None:
    assert _frame_set(data_root).stat().st_mode & 0o777 == 0o444


def test_two_stagings_give_one_hash_across_data_roots(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, tmp_path: Path
) -> None:
    records = []
    for name in ("a", "b/nested/deeper"):
        root = tmp_path / name
        imported = import_source(write_recording(), root)
        cases = [case_of("shaken", "camera_shake", 1, _SHAKE)]
        build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), root)
        stage_corpus(_CORPUS, root)
        records.append(_frame_set(root).read_bytes())

    assert records[0] == records[1]


def test_versions_sharing_every_bundle_keep_separate_frame_sets(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    results = []
    for corpus in ("first", "second"):
        build_corpus(write_corpus([stream_of(imported)], corpus_id=corpus), data_root)
        results.append(stage_corpus(corpus, data_root))

    assert results[0].bundles[0].bundle_sha256 == results[1].bundles[0].bundle_sha256
    assert results[0].frame_set_sha256 != results[1].frame_set_sha256


def test_a_second_process_writes_identical_bytes(
    staged: FramesResult, data_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(data_root, copy)
    _frame_set(copy).unlink()
    for name in ("one", "two", "shaken"):
        directory = copy / "corpus" / _CORPUS / "frames" / name
        directory.chmod(0o755)
        shutil.rmtree(directory)

    subprocess.run(
        [sys.executable, "-m", "ss_track.cli", "corpus", "stage", "--corpus", _CORPUS],
        check=True,
        capture_output=True,
        env={"DATA_DIR": str(copy), "PATH": ""},
    )

    assert _frame_set(copy).read_bytes() == _frame_set(data_root).read_bytes()


def test_a_repeated_stage_leaves_the_record_alone(staged: FramesResult, data_root: Path) -> None:
    before = _frame_set(data_root).stat()

    repeated = stage_corpus(_CORPUS, data_root)

    after = _frame_set(data_root).stat()
    assert repeated.status == "unchanged"
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


def test_a_replaced_bundle_fails_verify_by_name(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    hashes = _hashes(staged)
    _replace_bundle(data_root, "two", "one")

    refusal = verify_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == [
        {
            "stream_id": "two",
            "reason": "replaced",
            "frame_set_bundle_sha256": hashes["two"],
            "bundle_sha256": hashes["one"],
        }
    ]
    assert refusal.details["corpus_id"] == _CORPUS
    assert refusal.details["frame_set_sha256"] == staged.frame_set_sha256


def test_every_replaced_bundle_is_named_at_once(
    first: ImportResult,
    second: ImportResult,
    third: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    verify_refuses: Refused,
) -> None:
    streams = [
        stream_of(first, stream_id="one"),
        stream_of(second, stream_id="two"),
        stream_of(third, stream_id="three"),
    ]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus(_CORPUS, data_root)
    _replace_bundle(data_root, "one", "three")
    _replace_bundle(data_root, "two", "three")

    bundles = verify_refuses(RefusalCode.FRAME_SET_MISMATCH).details["bundles"]

    assert isinstance(bundles, list)
    assert [entry["stream_id"] for entry in bundles] == ["one", "two"]  # type: ignore[index,call-overload]


def test_a_replaced_parent_of_a_case_is_named(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    _replace_bundle(data_root, "one", "two")

    refusal = verify_refuses(RefusalCode.BUNDLE_CONFLICT)

    assert refusal.details["stream_id"] == "shaken"
    assert refusal.details["parent_stream_id"] == "one"


def test_a_stage_cannot_carry_the_record_along_with_a_replaced_bundle(
    staged: FramesResult, data_root: Path, stage_refuses: Refused
) -> None:
    pinned = _frame_set(data_root).read_bytes()
    _replace_bundle(data_root, "two", "one")

    refusal = stage_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert _frame_set(data_root).read_bytes() == pinned
    assert refusal.details["frame_set_sha256"] == staged.frame_set_sha256


def test_a_missing_bundle_fails_verify_by_name_and_staging_restores_one_hash(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    _remove_bundle(data_root, "two")

    refusal = verify_refuses(RefusalCode.BUNDLE_NOT_STAGED)

    assert refusal.details == {"stream_id": "two"}
    assert stage_corpus(_CORPUS, data_root).frame_set_sha256 == staged.frame_set_sha256
    assert verify_corpus_frames(_CORPUS, data_root).status == "verified"


def test_a_failed_stage_leaves_no_frame_set_and_a_repeat_writes_one(
    first: ImportResult,
    second: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    stage_refuses: Refused,
) -> None:
    streams = [stream_of(first, stream_id="one"), stream_of(second, stream_id="two")]
    build_corpus(write_corpus(streams), data_root)
    stored = next(second.manifest_path.parent.glob("source*"))
    held = stored.read_bytes()
    stored.chmod(0o644)
    stored.write_bytes(held[:-1])

    stage_refuses(RefusalCode.SOURCE_HASH_MISMATCH)

    assert _bundle(data_root, "one").is_dir()
    assert not _frame_set(data_root).exists()

    stored.write_bytes(held)
    result = stage_corpus(_CORPUS, data_root)
    assert result.status == "staged"
    assert _frame_set(data_root).is_file()


def test_a_case_that_fails_after_every_stream_leaves_no_frame_set(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage_refuses: Refused,
) -> None:
    cases = [case_of("shaken", "camera_shake", 1, _SHAKE)]
    build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    def fail(*_: object) -> None:
        raise CorpusRefusal(RefusalCode.CASE_INVALID, "injected", {})

    monkeypatch.setattr(staging_module, "write_case_bundle", fail)

    stage_refuses(RefusalCode.CASE_INVALID)

    assert _bundle(data_root, "one").is_dir()
    assert not _frame_set(data_root).exists()


def test_verify_refuses_a_fully_staged_corpus_with_no_frame_set(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    _frame_set(data_root).unlink()

    refusal = verify_refuses(RefusalCode.FRAME_SET_NOT_STAGED)

    assert refusal.details == {"corpus_id": _CORPUS}


def test_a_stage_over_finished_bundles_writes_the_missing_record(
    staged: FramesResult, data_root: Path
) -> None:
    _frame_set(data_root).unlink()

    result = stage_corpus(_CORPUS, data_root)

    assert result.status == "staged"
    assert {bundle.status for bundle in result.bundles} == {"unchanged"}
    assert result.frame_set_sha256 == staged.frame_set_sha256


def test_a_directory_no_frame_set_names_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused, stage_refuses: Refused
) -> None:
    stray = _bundle(data_root, "stray")
    stray.mkdir()

    for refused in (verify_refuses, stage_refuses):
        refusal = refused(RefusalCode.FRAME_SET_MISMATCH)
        assert refusal.details["bundles"] == [{"stream_id": "stray", "reason": "unnamed"}]

    stray.rmdir()
    assert verify_corpus_frames(_CORPUS, data_root).status == "verified"


def test_a_first_stage_writes_no_record_beside_a_stray_directory(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path, stage_refuses: Refused
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    _bundle(data_root, "stray").mkdir(parents=True)

    refusal = stage_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == [{"stream_id": "stray", "reason": "unnamed"}]
    assert not _frame_set(data_root).exists()


def test_a_record_of_another_corpus_state_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    reseal(_frame_set(data_root), corpus_manifest_sha256="c" * 64)

    refusal = verify_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == []
    assert refusal.details["frame_set_corpus_manifest_sha256"] == "c" * 64


def test_lines_on_one_side_only_are_named(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    record = _record(_frame_set(data_root))
    lines = record["bundles"]
    assert isinstance(lines, list)
    gone = {**lines[-1], "stream_id": "gone"}
    reseal(_frame_set(data_root), bundles=[*lines[:-1], gone])

    refusal = verify_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == [
        {"stream_id": "gone", "reason": "missing"},
        {"stream_id": "two", "reason": "unnamed"},
    ]


def test_a_damaged_record_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    path = _frame_set(data_root)
    path.chmod(0o644)
    path.write_text(path.read_text(encoding="ascii").replace("one", "eno"), encoding="ascii")

    verify_refuses(RefusalCode.RECORD_TAMPERED)


def test_a_record_of_another_schema_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    reseal(_frame_set(data_root), schema_version=99)

    verify_refuses(RefusalCode.RECORD_SCHEMA_UNSUPPORTED)


@pytest.mark.parametrize(
    "bundles", [[{"stream_id": "one"}, 3], [{}], [{"stream_id": []}], "no", None]
)
def test_a_malformed_list_of_bundles_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused, bundles: object
) -> None:
    reseal(_frame_set(data_root), bundles=bundles)

    verify_refuses(RefusalCode.RECORD_TAMPERED)


def test_a_damaged_frame_is_still_named(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    frame = _bundle(data_root, "one") / "00000000.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"x" * frame.stat().st_size)

    refusal = verify_refuses(RefusalCode.FRAME_CORRUPTED)

    assert refusal.details["damaged_count"] == 1


def test_a_killed_run_leaves_no_partial_record_after_the_next_run(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    partial = data_root / "corpus" / _CORPUS / ".incoming-killed"
    partial.write_text("{", encoding="ascii")

    stage_corpus(_CORPUS, data_root)

    assert not partial.exists()
    assert _frame_set(data_root).is_file()


def test_the_record_is_written_while_the_staging_lock_is_held(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    lock_path = _bundle(data_root, "one").parent / ".staging.lock"
    held: list[bool] = []

    def commit(*arguments: object) -> tuple[str, bool]:
        with lock_path.open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                held.append(True)
        return commit_frame_set(*arguments)  # type: ignore[arg-type]

    monkeypatch.setattr(staging_module, "commit_frame_set", commit)

    stage_corpus(_CORPUS, data_root)

    assert held == [True]
