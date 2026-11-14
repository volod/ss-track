"""`import --redecode` decodes an imported source's stored bytes again, under the installed policy.

A plain `--redecode` carries the existing terms forward unchanged; `--amend-terms` given alongside
it takes them from the declaration instead, which is the only route for a record too old for either
flag alone. `tests/corpus/kept_records/` holds the real schema 1 records these cases replay.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ss_track.cli import build_parser, main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    amend_source_terms,
    build_corpus,
    redecode_source,
    verify_corpus_frames,
)
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from tests.corpus._amending import (
    CORPUS,
    read_source,
    refused,
    rights_with,
    staged,
    stored_source,
)
from tests.corpus._historic import place_record
from tests.corpus.conftest import WriteCorpus, WriteRecording, last_record, stream_of

_UPGRADED = DecodePolicy(decoder="pyav", decoder_version="99", ffmpeg_version="99")


def _install_upgraded_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a newer decode policy wherever `corpus build` and `--redecode` read it."""
    monkeypatch.setattr("ss_track.corpus.sources.redecode.current_decode_policy", lambda: _UPGRADED)
    monkeypatch.setattr("ss_track.corpus.versions.builder.current_decode_policy", lambda: _UPGRADED)


def _older_record(name: str, path: Path) -> None:
    """Replace a real record with one the kept major wrote, over the real stored bytes at `path`."""
    path.chmod(0o644)
    place_record(name, path)


def test_an_older_policy_is_replaced_and_a_new_build_accepts_it(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staged(imported, write_corpus, data_root)
    stored = stored_source(imported)
    before = stored.read_bytes()
    old = read_source(imported.manifest_path)
    _install_upgraded_policy(monkeypatch)

    result = redecode_source(write_recording(), data_root)

    assert result.status == "redecoded"
    assert result.decode_policy_current is True
    assert result.replaced_manifest_sha256 == imported.manifest_sha256
    assert stored.read_bytes() == before
    new = read_source(result.manifest_path)
    assert new["decode_policy"]["decoder_version"] == "99"
    assert (new["rights"], new["sensitivity"]) == (old["rights"], old["sensitivity"])

    declared = write_corpus([stream_of(imported)], corpus_id="pilot-v2")
    assert build_corpus(declared, data_root).status == "built"

    refusal = refused(
        lambda: verify_corpus_frames(CORPUS, data_root), RefusalCode.SOURCE_RECORD_CHANGED
    )
    assert refusal.details["source_manifest_sha256"] == result.manifest_sha256
    assert refusal.details["changed_terms"] == []


def test_a_repeat_reports_unchanged(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    first = redecode_source(write_recording(), data_root)

    second = redecode_source(write_recording(), data_root)

    assert first.status == "unchanged"
    assert second.status == "unchanged"
    assert second.manifest_sha256 == imported.manifest_sha256


def test_a_stored_source_that_no_longer_matches_its_hash_is_refused(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    stored = stored_source(imported)
    stored.chmod(0o644)
    stored.write_bytes(b"tampered")

    refusal = refused(
        lambda: redecode_source(write_recording(), data_root), RefusalCode.SOURCE_HASH_MISMATCH
    )

    assert refusal.details["source_sha256"] == imported.source_sha256


def test_a_record_with_no_terms_to_carry_is_refused_and_names_amend_terms(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    _older_record("source-schema-1-d6b704d.json", imported.manifest_path)
    before = imported.manifest_path.read_bytes()

    refusal = refused(
        lambda: redecode_source(write_recording(), data_root), RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    )

    assert set(refusal.details["missing_operations"]) == {"--amend-capture", "--amend-terms"}
    assert imported.manifest_path.read_bytes() == before
    assert not (imported.manifest_path.parent / "replaced").exists()


def test_an_older_record_is_amended_and_then_redecoded_and_builds(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _older_record("source-schema-1-d6b704d.json", imported.manifest_path)

    amended = amend_source_terms(
        write_recording(rights=rights_with()), data_root, amend_capture=True
    )
    assert amended.status == "amended"
    assert amended.decode_policy_current is False

    redecoded = redecode_source(write_recording(), data_root)
    assert redecoded.status == "redecoded"
    assert redecoded.decode_policy_current is True

    declared = write_corpus([stream_of(imported)])
    assert build_corpus(declared, data_root).status == "built"


def test_a_record_too_old_for_amend_terms_alone_builds_through_both_flags_together(
    imported: ImportResult,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _older_record("source-schema-1-0238d55.json", imported.manifest_path)

    refused(
        lambda: amend_source_terms(write_recording(rights=rights_with()), data_root),
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
    )
    refused(
        lambda: redecode_source(write_recording(), data_root),
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
    )

    result = redecode_source(
        write_recording(rights=rights_with()), data_root, amend_terms=True, amend_capture=True
    )

    assert result.status == "redecoded"
    assert result.decode_policy_current is True
    new = read_source(result.manifest_path)
    assert new["schema_version"] == 3
    assert {"color", "interlaced_frames", "source_bits_per_component"} <= new["sequence"].keys()
    declared = write_corpus([stream_of(imported)])
    assert build_corpus(declared, data_root).status == "built"


_KILLED_RUN = """
    import os
    import sys
    from pathlib import Path

    from ss_track.corpus import redecode_source

    declaration, data_root, kill_at = sys.argv[1:]
    calls = [0]

    def killed(_: int) -> None:
        calls[0] += 1
        if calls[0] == int(kill_at):
            os._exit(9)

    os.fsync = killed
    redecode_source(Path(declaration), Path(data_root), amend_terms=True, amend_capture=True)
"""


@pytest.mark.parametrize("kill_at", [1, 2], ids=["keeping-the-old-record", "writing-the-new-one"])
def test_a_killed_redecode_leaves_one_whole_record_and_a_rerun_finishes_it(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path, kill_at: int
) -> None:
    _older_record("source-schema-1-d6b704d.json", imported.manifest_path)
    declared = write_recording(rights=rights_with())
    command = [sys.executable, "-c", textwrap.dedent(_KILLED_RUN), str(declared), str(data_root)]

    run = subprocess.run([*command, str(kill_at)], check=False, capture_output=True)

    assert run.returncode == 9
    directory = imported.manifest_path.parent
    assert read_source(imported.manifest_path)["schema_version"] == 1
    assert list(directory.rglob(".incoming-*"))
    result = redecode_source(declared, data_root, amend_terms=True, amend_capture=True)
    assert result.status == "redecoded"
    assert not list(directory.rglob(".incoming-*"))
    assert read_source(result.manifest_path)["manifest_sha256"] == result.manifest_sha256
    assert read_source(result.replaced_path or Path())


def test_the_command_reports_one_record_and_its_refusal_exits_one(
    imported: ImportResult,
    write_recording: WriteRecording,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_upgraded_policy(monkeypatch)
    source = write_recording()

    assert main(["import", "--source", str(source), "--redecode"]) == EXIT_OK
    record = last_record(caplog)
    assert record["status"] == "redecoded"
    assert record["replaced_manifest_sha256"] == imported.manifest_sha256

    assert main(["import", "--source", str(source), "--redecode"]) == EXIT_OK
    assert last_record(caplog)["status"] == "unchanged"

    stored = stored_source(imported)
    stored.chmod(0o644)
    stored.write_bytes(b"tampered")
    assert main(["import", "--source", str(source), "--redecode"]) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "SOURCE_HASH_MISMATCH"


def test_the_flags_are_off_unless_given() -> None:
    plain = build_parser().parse_args(["import", "--source", "a.yaml"])
    redecoding = build_parser().parse_args(["import", "--source", "a.yaml", "--redecode"])
    both = build_parser().parse_args(
        ["import", "--source", "a.yaml", "--redecode", "--amend-terms"]
    )

    assert (plain.redecode, redecoding.redecode) == (False, True)
    assert (both.redecode, both.amend_terms) == (True, True)
