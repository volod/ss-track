"""What an amendment keeps: the replaced record, one whole record, and older majors."""

import json
import stat
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    amend_source_terms,
    import_source,
    verify_corpus_frames,
)
from ss_track.corpus.amendment import replaced_record_path
from ss_track.corpus.importer import SEQUENCE_KEYS
from ss_track.corpus.sealed import read_sealed
from tests.corpus._amending import CORPUS, SOURCE_KIND, evidence, refused, rights_with, staged
from tests.corpus.conftest import WriteCorpus, WriteRecording, reseal


def test_a_repeat_reports_unchanged_and_keeps_one_replaced_record(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    narrowed = write_recording(sensitivity={"level": "high"})
    first = amend_source_terms(narrowed, data_root)
    before = evidence(first.manifest_path.parent)

    second = amend_source_terms(narrowed, data_root)

    assert second.status == "unchanged"
    assert second.manifest_sha256 == first.manifest_sha256
    assert (second.replaced_manifest_sha256, second.changed_terms) == (None, [])
    assert evidence(first.manifest_path.parent) == before


def test_a_replaced_record_stays_readable_under_its_own_seal(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    before = imported.manifest_path.read_bytes()

    result = amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    assert result.replaced_path == replaced_record_path(
        imported.manifest_path.parent, imported.manifest_sha256
    )
    assert result.replaced_path.read_bytes() == before
    assert stat.S_IMODE(result.replaced_path.stat().st_mode) == 0o444
    record = read_sealed(result.replaced_path, SOURCE_KIND)
    assert record["manifest_sha256"] == imported.manifest_sha256


def test_restoring_the_old_terms_restores_the_pin_and_keeps_both_records(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    staged(imported, write_corpus, data_root)
    narrowed = amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    restored = amend_source_terms(write_recording(), data_root)

    assert restored.manifest_sha256 == imported.manifest_sha256
    assert verify_corpus_frames(CORPUS, data_root).status == "verified"
    directory = imported.manifest_path.parent
    for sealed in (imported.manifest_sha256, narrowed.manifest_sha256):
        assert read_sealed(replaced_record_path(directory, sealed), SOURCE_KIND)


_KILLED_RUN = """
    import os
    import sys
    from pathlib import Path

    from ss_track.corpus import amend_source_terms

    declaration, data_root, kill_at = sys.argv[1:]
    calls = [0]

    def killed(_: int) -> None:
        calls[0] += 1
        if calls[0] == int(kill_at):
            os._exit(9)

    os.fsync = killed
    amend_source_terms(Path(declaration), Path(data_root))
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
    assert (
        read_sealed(imported.manifest_path, SOURCE_KIND)["manifest_sha256"]
        == imported.manifest_sha256
    )
    assert list(directory.rglob(".incoming-*"))
    result = amend_source_terms(narrowed, data_root)
    assert result.status == "amended"
    assert not list(directory.rglob(".incoming-*"))
    assert (
        read_sealed(result.manifest_path, SOURCE_KIND)["manifest_sha256"] == result.manifest_sha256
    )
    assert read_sealed(result.replaced_path or Path(), SOURCE_KIND)


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
        results = list(pool.map(lambda path: amend_source_terms(path, data_root), declared))

    directory = imported.manifest_path.parent
    kept = {path.stem for path in (directory / "replaced").iterdir()}
    current = read_sealed(imported.manifest_path, SOURCE_KIND)["manifest_sha256"]
    every = {result.manifest_sha256 for result in results} | {imported.manifest_sha256}
    assert kept | {current} == every
    assert current not in kept


def _older_record(name: str, data_root: Path) -> tuple[str, Path]:
    """Place a record written by the code of its own commit, under its real source hash."""
    text = (Path(__file__).parent / "records" / name).read_text(encoding="ascii")
    sha256 = json.loads(text)["source"]["sha256"]
    directory = data_root / "import" / sha256
    directory.mkdir(parents=True)
    path = directory / "manifest.json"
    path.write_text(text, encoding="ascii")
    return sha256, path


def test_a_real_record_without_terms_gains_them_and_the_current_major(
    write_recording: WriteRecording, data_root: Path
) -> None:
    sha256, path = _older_record("source-schema-1-d6b704d.json", data_root)
    old = read_sealed(path, SOURCE_KIND)
    declared = write_recording(sha256=sha256, rights=rights_with(sharing="public"))

    result = amend_source_terms(declared, data_root)

    new = read_sealed(path, SOURCE_KIND)
    assert new["schema_version"] == 2
    assert result.changed_terms == ["rights.derived_frames", "rights.retain_until"]
    assert result.decode_policy_current is False
    unchanged = {"manifest_sha256", "schema_version", "rights", "sensitivity"}
    assert {k: v for k, v in new.items() if k not in unchanged} == {
        k: v for k, v in old.items() if k not in unchanged
    }
    assert read_sealed(result.replaced_path or Path(), SOURCE_KIND) == old


def test_a_plain_import_over_a_record_without_terms_offers_the_command(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    source = import_source(write_recording(), data_root)
    rights = rights_with()
    del rights["retain_until"], rights["derived_frames"]
    reseal(source.manifest_path, schema_version=1, rights=rights)
    declared = write_recording()

    refusal = refused(lambda: import_source(declared, data_root), RefusalCode.IMPORT_CONFLICT)

    assert refusal.details["changed_terms"] == ["rights.derived_frames", "rights.retain_until"]
    assert "--amend-terms" in refusal.message


def test_a_real_record_short_of_the_current_major_is_refused_by_name(
    write_recording: WriteRecording, data_root: Path
) -> None:
    sha256, path = _older_record("source-schema-1-0238d55.json", data_root)
    before = path.read_bytes()
    declared = write_recording(sha256=sha256)

    refusal = refused(
        lambda: amend_source_terms(declared, data_root), RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    )

    assert refusal.details["missing_facts"] == [
        "sequence.color",
        "sequence.interlaced_frames",
        "sequence.source_bits_per_component",
        "decode_policy.conversion_flags",
    ]
    assert path.read_bytes() == before
    assert not (path.parent / "replaced").exists()


def test_the_sequence_keys_are_the_ones_an_import_writes(imported: ImportResult) -> None:
    sequence = read_sealed(imported.manifest_path, SOURCE_KIND)["sequence"]

    assert isinstance(sequence, dict)
    assert set(sequence) == SEQUENCE_KEYS
