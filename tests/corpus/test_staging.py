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
    import_source,
    stage_corpus,
)
from tests.corpus._media import FRAME_COUNT, write_clip
from tests.corpus.conftest import WriteCorpus, WriteRecording, reseal, sequence_of

_CORPUS = "pilot-v1"


def _bundle_path(data_root: Path, sequence: str = "one", corpus: str = _CORPUS) -> Path:
    return data_root / "corpus" / corpus / "frames" / sequence


def _refused(data_root: Path, code: RefusalCode, corpus: str = _CORPUS) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(corpus, data_root)
    assert caught.value.code is code
    return caught.value


def _scratch(data_root: Path) -> list[Path]:
    return list(_bundle_path(data_root).parent.glob(".incoming-*"))


@pytest.fixture
def built(imported: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> ImportResult:
    build_corpus(write_corpus([sequence_of(imported)]), data_root)
    return imported


def test_two_stagings_of_one_source_give_one_bundle_hash(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, tmp_path: Path
) -> None:
    hashes = []
    for root, corpus, sequence in (("a", "first", "one"), ("b", "second", "renamed")):
        imported = import_source(write_recording(), tmp_path / root)
        build_corpus(
            write_corpus([sequence_of(imported, sequence_id=sequence)], corpus_id=corpus),
            tmp_path / root,
        )
        hashes.append(stage_corpus(corpus, tmp_path / root).bundles[0].bundle_sha256)

    assert hashes[0] == hashes[1]


def test_a_second_process_stages_identical_bytes(
    built: ImportResult, data_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(data_root, copy)
    for root in (data_root, copy):
        subprocess.run(
            [sys.executable, "-m", "ss_track.cli", "corpus", "stage", "--corpus", _CORPUS],
            check=True,
            capture_output=True,
            env={"DATA_DIR": str(root), "PATH": ""},
        )

    first, second = _bundle_path(data_root), _bundle_path(copy)
    assert sorted(path.name for path in first.iterdir()) == sorted(
        path.name for path in second.iterdir()
    )
    assert all(path.read_bytes() == (second / path.name).read_bytes() for path in first.iterdir())


def test_a_different_source_gives_a_different_bundle_hash(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    write_clip(media / "clip.mkv")
    first = import_source(write_recording(), data_root)
    write_clip(media / "other.mkv", frames=FRAME_COUNT - 1)
    second = import_source(write_recording("other.mkv"), data_root)
    sequences = [
        sequence_of(first, sequence_id="one"),
        sequence_of(second, sequence_id="two"),
    ]
    build_corpus(write_corpus(sequences), data_root)

    one, two = stage_corpus(_CORPUS, data_root).bundles

    assert one.bundle_sha256 != two.bundle_sha256


def test_repeating_a_stage_changes_nothing(built: ImportResult, data_root: Path) -> None:
    first = stage_corpus(_CORPUS, data_root)
    second = stage_corpus(_CORPUS, data_root)

    assert (first.status, second.status) == ("staged", "unchanged")
    assert second.bundles[0].status == "unchanged"
    assert first.bundles[0].bundle_sha256 == second.bundles[0].bundle_sha256


def test_sequences_of_one_source_and_window_share_a_bundle_hash(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    sequences = [
        sequence_of(imported, sequence_id="one"),
        sequence_of(imported, sequence_id="two"),
    ]
    build_corpus(write_corpus(sequences), data_root)

    one, two = stage_corpus(_CORPUS, data_root).bundles

    assert one.bundle_sha256 == two.bundle_sha256


@pytest.mark.parametrize("corpus", ["never-built", "", "UPPER"])
def test_a_corpus_that_does_not_exist_is_refused(data_root: Path, corpus: str) -> None:
    _refused(data_root, RefusalCode.CORPUS_NOT_BUILT, corpus)


def test_an_identifier_cannot_reach_a_real_corpus_by_another_path(
    built: ImportResult, data_root: Path
) -> None:
    _refused(data_root, RefusalCode.CORPUS_NOT_BUILT, f"../corpus/{_CORPUS}")

    assert not _bundle_path(data_root).exists()


def test_a_corpus_from_another_decoder_is_refused(built: ImportResult, data_root: Path) -> None:
    corpus_manifest = data_root / "corpus" / _CORPUS / "manifest.json"
    reseal(corpus_manifest, decode_policy_sha256="d" * 64)

    _refused(data_root, RefusalCode.DECODE_POLICY_MISMATCH)


def test_a_bundle_of_another_corpus_version_is_refused(
    built: ImportResult, data_root: Path
) -> None:
    stage_corpus(_CORPUS, data_root)
    reseal(data_root / "corpus" / _CORPUS / "manifest.json", corpus_id="rebuilt")

    _refused(data_root, RefusalCode.BUNDLE_CONFLICT)


def test_a_concurrent_run_is_refused(built: ImportResult, data_root: Path) -> None:
    root = _bundle_path(data_root).parent
    root.mkdir(parents=True)
    with (root / ".staging.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        _refused(data_root, RefusalCode.STAGING_IN_PROGRESS)

    assert stage_corpus(_CORPUS, data_root).status == "staged"


def test_a_killed_run_leaves_no_scratch_after_the_next_run(
    built: ImportResult, data_root: Path
) -> None:
    leftover = _bundle_path(data_root).parent / ".incoming-killed" / "staged"
    leftover.mkdir(parents=True)
    (leftover / "00000000.rgb24").write_bytes(b"partial")
    (leftover / "00000000.rgb24").chmod(0o444)

    result = stage_corpus(_CORPUS, data_root)

    assert result.status == "staged"
    assert not _scratch(data_root)
