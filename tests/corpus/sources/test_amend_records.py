"""What an amendment keeps: the replaced record and one whole record."""

import stat
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ss_track.corpus import ImportResult, amend_source, verify_corpus_frames
from ss_track.corpus.storage.layout import replaced_record_path
from tests.corpus._amending import CORPUS, evidence, read_source, staged
from tests.corpus.conftest import WriteCorpus, WriteRecording


def test_a_repeat_reports_unchanged_and_keeps_one_replaced_record(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    narrowed = write_recording(sensitivity={"level": "high"})
    first = amend_source(narrowed, data_root)
    before = evidence(first.manifest_path.parent)

    second = amend_source(narrowed, data_root)

    assert second.status == "unchanged"
    assert second.manifest_sha256 == first.manifest_sha256
    assert (second.replaced_manifest_sha256, second.changed_terms) == (None, [])
    assert evidence(first.manifest_path.parent) == before


def test_a_replaced_record_stays_readable_under_its_own_seal(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    before = imported.manifest_path.read_bytes()

    result = amend_source(write_recording(sensitivity={"level": "high"}), data_root)

    assert result.replaced_path == replaced_record_path(
        imported.manifest_path.parent, imported.manifest_sha256
    )
    assert result.replaced_path.read_bytes() == before
    assert stat.S_IMODE(result.replaced_path.stat().st_mode) == 0o444
    record = read_source(result.replaced_path)
    assert record["manifest_sha256"] == imported.manifest_sha256


def test_restoring_the_old_terms_restores_the_pin_and_keeps_both_records(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    staged(imported, write_corpus, data_root)
    narrowed = amend_source(write_recording(sensitivity={"level": "high"}), data_root)

    restored = amend_source(write_recording(), data_root)

    assert restored.manifest_sha256 == imported.manifest_sha256
    assert verify_corpus_frames(CORPUS, data_root).status == "verified"
    directory = imported.manifest_path.parent
    for sealed in (imported.manifest_sha256, narrowed.manifest_sha256):
        assert read_source(replaced_record_path(directory, sealed))


_KILLED_RUN = """
    import os
    import sys
    from pathlib import Path

    from ss_track.corpus import amend_source

    declaration, data_root, kill_at = sys.argv[1:]
    calls = [0]

    def killed(_: int) -> None:
        calls[0] += 1
        if calls[0] == int(kill_at):
            os._exit(9)

    os.fsync = killed
    amend_source(Path(declaration), Path(data_root))
"""


@pytest.mark.parametrize("kill_at", [1, 2], ids=["keeping-the-old-record", "writing-the-new-one"])
def test_a_killed_amendment_leaves_one_whole_record_and_a_rerun_finishes_it(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path, kill_at: int
) -> None:
    narrowed = write_recording(sensitivity={"level": "high"})
    command = [sys.executable, "-c", textwrap.dedent(_KILLED_RUN), str(narrowed), str(data_root)]

    run = subprocess.run([*command, str(kill_at)], check=False, capture_output=True)

    assert run.returncode == 9
    directory = imported.manifest_path.parent
    assert read_source(imported.manifest_path)["manifest_sha256"] == imported.manifest_sha256
    assert list(directory.rglob(".incoming-*"))
    result = amend_source(narrowed, data_root)
    assert result.status == "amended"
    assert not list(directory.rglob(".incoming-*"))
    assert read_source(result.manifest_path)["manifest_sha256"] == result.manifest_sha256
    assert read_source(result.replaced_path or Path())


def test_concurrent_amendments_lose_no_record(
    imported: ImportResult, media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    declared = [
        write_recording(sensitivity={"level": "high", "notes": str(index)}).rename(
            media / f"recording-{index}.yaml"
        )
        for index in range(8)
    ]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda path: amend_source(path, data_root), declared))

    directory = imported.manifest_path.parent
    kept = {path.stem for path in (directory / "replaced").iterdir()}
    current = read_source(imported.manifest_path)["manifest_sha256"]
    every = {result.manifest_sha256 for result in results} | {imported.manifest_sha256}
    assert kept | {current} == every
    assert current not in kept
