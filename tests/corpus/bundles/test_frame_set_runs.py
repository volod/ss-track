"""A failed, killed, repeated or concurrent staging leaves one whole frame set or none."""

import fcntl
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.bundles import staging as staging_module
from ss_track.corpus.bundles.frame_set import commit_frame_set
from ss_track.corpus.bundles.stage_report import FramesResult
from tests.corpus.bundles._frame_set import (
    CORPUS,
    SHAKE,
    Refused,
    bundle_path,
    frame_set_path,
    refused_by,
    stage_two_streams,
)
from tests.corpus.conftest import (
    WriteCorpus,
    case_of,
    stream_of,
)


@pytest.fixture
def staged(
    first: ImportResult, second: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> FramesResult:
    return stage_two_streams(first, second, write_corpus, data_root)


@pytest.fixture
def verify_refuses(data_root: Path) -> Refused:
    return refused_by(verify_corpus_frames, data_root)


@pytest.fixture
def stage_refuses(data_root: Path) -> Refused:
    return refused_by(stage_corpus, data_root)


def test_a_second_process_writes_identical_bytes(
    staged: FramesResult, data_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(data_root, copy)
    frame_set_path(copy).unlink()
    for name in ("one", "two", "shaken"):
        directory = copy / "corpus" / CORPUS / "frames" / name
        directory.chmod(0o755)
        shutil.rmtree(directory)

    subprocess.run(
        [sys.executable, "-m", "ss_track.cli", "corpus", "stage", "--corpus", CORPUS],
        check=True,
        capture_output=True,
        env={"DATA_DIR": str(copy), "PATH": ""},
    )

    assert frame_set_path(copy).read_bytes() == frame_set_path(data_root).read_bytes()


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

    assert bundle_path(data_root, "one").is_dir()
    assert not frame_set_path(data_root).exists()

    stored.write_bytes(held)
    result = stage_corpus(CORPUS, data_root)
    assert result.status == "staged"
    assert frame_set_path(data_root).is_file()


def test_a_case_that_fails_after_every_stream_leaves_no_frame_set(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage_refuses: Refused,
) -> None:
    cases = [case_of("shaken", "camera_shake", 1, SHAKE)]
    build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    def fail(*_: object) -> None:
        raise CorpusRefusal(RefusalCode.CASE_INVALID, "injected", {})

    monkeypatch.setattr(staging_module, "write_case_bundle", fail)

    stage_refuses(RefusalCode.CASE_INVALID)

    assert bundle_path(data_root, "one").is_dir()
    assert not frame_set_path(data_root).exists()


def test_verify_refuses_a_fully_staged_corpus_with_no_frame_set(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    frame_set_path(data_root).unlink()

    refusal = verify_refuses(RefusalCode.FRAME_SET_NOT_STAGED)

    assert refusal.details == {"corpus_id": CORPUS}


def test_a_stage_over_finished_bundles_writes_the_missing_record(
    staged: FramesResult, data_root: Path
) -> None:
    frame_set_path(data_root).unlink()

    result = stage_corpus(CORPUS, data_root)

    assert result.status == "staged"
    assert {bundle.status for bundle in result.bundles} == {"unchanged"}
    assert result.frame_set_sha256 == staged.frame_set_sha256


def test_a_killed_run_leaves_no_partial_record_after_the_next_run(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    partial = data_root / "corpus" / CORPUS / ".incoming-killed"
    partial.write_text("{", encoding="ascii")

    stage_corpus(CORPUS, data_root)

    assert not partial.exists()
    assert frame_set_path(data_root).is_file()


def test_the_record_is_written_while_the_staging_lock_is_held(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    lock_path = bundle_path(data_root, "one").parent / ".staging.lock"
    held: list[bool] = []

    def commit(*arguments: object) -> tuple[str, bool]:
        with lock_path.open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                held.append(True)
        return commit_frame_set(*arguments)  # type: ignore[arg-type]

    monkeypatch.setattr(staging_module, "commit_frame_set", commit)

    stage_corpus(CORPUS, data_root)

    assert held == [True]
