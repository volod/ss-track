"""`ss-track data clean`: plan by default, remove only named reproducible bytes, keep every record."""

import fcntl
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.storage.layout import (
    corpus_manifest_path,
    discovery_run_directory,
    frame_set_path,
    frames_root,
)
from tests.corpus.conftest import WriteCorpus, last_record, stream_of

CORPUS = "pilot-v1"


@pytest.fixture
def staged(
    first: ImportResult, second: ImportResult, write_corpus: WriteCorpus, cli_root: Path
) -> str:
    streams = [stream_of(first, stream_id="one"), stream_of(second, stream_id="two")]
    build_corpus(write_corpus(streams), cli_root)
    return stage_corpus(CORPUS, cli_root).frame_set_sha256


def _clean(caplog: pytest.LogCaptureFixture, *arguments: str) -> tuple[int, dict[str, object]]:
    status = main(["data", "clean", *arguments])
    return status, last_record(caplog)


def _bundles(data_root: Path) -> list[Path]:
    return sorted(p for p in frames_root(data_root, CORPUS).iterdir() if not p.name.startswith("."))


def test_frames_are_planned_released_and_staged_again_to_the_same_frame_set(
    staged: str, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    bundles = _bundles(cli_root)
    status, planned = _clean(caplog, "--kind", "staged-frames", "--corpus", CORPUS)

    assert status == EXIT_OK
    assert planned["status"] == "planned"
    clean = planned["clean"]
    assert isinstance(clean, dict) and clean["applied"] is False and clean["total_bytes"] > 0
    assert _bundles(cli_root) == bundles

    status, cleaned = _clean(caplog, "--kind", "staged-frames", "--corpus", CORPUS, "--apply")

    assert status == EXIT_OK and cleaned["status"] == "cleaned"
    assert _bundles(cli_root) == []
    assert corpus_manifest_path(cli_root, CORPUS).is_file()
    assert frame_set_path(cli_root, CORPUS).is_file()
    assert main(["corpus", "verify", "--corpus", CORPUS]) == EXIT_REFUSED
    assert stage_corpus(CORPUS, cli_root).frame_set_sha256 == staged
    assert main(["corpus", "verify", "--corpus", CORPUS]) == EXIT_OK


def test_an_unknown_corpus_refuses_without_creating_folders(
    cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    status, refused = _clean(caplog, "--kind", "staged-frames", "--corpus", "absent", "--apply")

    assert status == EXIT_REFUSED and refused["code"] == "CORPUS_NOT_BUILT"
    assert not (cli_root / "corpus" / "absent").exists()


def test_a_held_staging_lock_refuses_and_keeps_the_frames(
    staged: str, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    lock = frames_root(cli_root, CORPUS) / ".staging.lock"
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        status, refused = _clean(caplog, "--kind", "staged-frames", "--corpus", CORPUS, "--apply")

    assert status == EXIT_REFUSED and refused["code"] == "STAGING_IN_PROGRESS"
    assert _bundles(cli_root)


def test_scratch_is_removed_only_when_no_lock_is_held(
    staged: str, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    leftover = cli_root / "corpus" / ".incoming-killed"
    leftover.mkdir()
    (leftover / "partial").write_bytes(b"x" * 10)
    acquisition = discovery_run_directory(cli_root, "acq-1")
    (acquisition / "scratch").mkdir(parents=True)
    (acquisition / "acquisition.json").write_text("{}", encoding="ascii")
    (acquisition / "scratch" / "part.zip").write_bytes(b"y" * 5)

    with (frames_root(cli_root, CORPUS) / ".staging.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        status, refused = _clean(caplog, "--kind", "scratch", "--apply")
    assert status == EXIT_REFUSED and refused["code"] == "DATA_ROOT_BUSY"
    assert leftover.exists()

    status, cleaned = _clean(caplog, "--kind", "scratch", "--apply")
    assert status == EXIT_OK
    clean = cleaned["clean"]
    assert isinstance(clean, dict) and clean["total_bytes"] == 15
    assert not leftover.exists() and not (acquisition / "scratch" / "part.zip").exists()
    assert (acquisition / "acquisition.json").is_file()
    assert _bundles(cli_root)


def test_an_acquisition_cache_is_removed_and_its_record_kept(
    cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    acquisition = discovery_run_directory(cli_root, "acq-1")
    (acquisition / "cache").mkdir(parents=True)
    (acquisition / "acquisition.json").write_text("{}", encoding="ascii")
    (acquisition / "cache" / "source.zip").write_bytes(b"z" * 7)

    status, cleaned = _clean(caplog, "--kind", "acquisition-cache", "--run-id", "acq-1", "--apply")

    assert status == EXIT_OK and cleaned["clean"] == {
        "applied": True,
        "total_bytes": 7,
        "kinds": [
            {
                "kind": "acquisition-cache",
                "target": "acq-1",
                "restore": cleaned["clean"]["kinds"][0]["restore"],  # type: ignore[index]
                "bytes": 7,
                "entries": [{"path": "self-supervised-corpus/acq-1/cache/source.zip", "bytes": 7}],
            }
        ],
    }
    assert not (acquisition / "cache" / "source.zip").exists()
    assert (acquisition / "acquisition.json").is_file()
    status, refused = _clean(caplog, "--kind", "acquisition-cache", "--run-id", "not-acq")
    assert status == EXIT_REFUSED and refused["code"] == "MANIFEST_INVALID"


def test_tool_caches_leave_environments_and_other_caches(
    cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (cli_root / "cache" / "mypy").mkdir(parents=True)
    (cli_root / "cache" / "mypy" / "a.json").write_bytes(b"m")
    (cli_root / "cache" / "sibling-env" / "bin").mkdir(parents=True)

    status, _cleaned = _clean(caplog, "--kind", "tool-caches", "--apply")

    assert status == EXIT_OK
    assert not (cli_root / "cache" / "mypy").exists()
    assert (cli_root / "cache" / "sibling-env" / "bin").is_dir()


@pytest.mark.parametrize(
    "arguments",
    [
        ("--kind", "staged-frames"),
        ("--kind", "tool-caches", "--corpus", CORPUS),
        ("--kind", "scratch", "--kind", "tool-caches"),
    ],
)
def test_a_request_without_its_target_or_with_a_stray_one_is_refused(
    cli_root: Path, caplog: pytest.LogCaptureFixture, arguments: tuple[str, ...]
) -> None:
    status, refused = _clean(caplog, *arguments)
    assert status == EXIT_REFUSED and refused["code"] == "MANIFEST_INVALID"
