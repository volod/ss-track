"""An amendment changes terms alone: anything else it is asked to do records nothing."""

from pathlib import Path

import pytest

from ss_track.corpus import ImportResult, RefusalCode, amend_source_terms
from ss_track.corpus.records.sealing import sha256_file
from tests.corpus._amending import evidence, read_source, refused
from tests.corpus._media import write_clip
from tests.corpus.conftest import WriteRecording, reseal


@pytest.mark.parametrize(
    ("declared", "facts"),
    [
        ({"capture": {"camera": "bench camera"}}, ["capture"]),
        ({"timestamps": {"capture_clock_evidence": "clock"}}, ["sequence.capture_clock_evidence"]),
        ({"color": {"matrix": "bt709"}}, ["sequence.declared_color"]),
    ],
)
def test_an_amendment_that_changes_capture_facts_records_nothing(
    imported: ImportResult,
    write_recording: WriteRecording,
    data_root: Path,
    declared: dict[str, object],
    facts: list[str],
) -> None:
    directory = imported.manifest_path.parent
    before = evidence(directory)
    changed = write_recording(sensitivity={"level": "high"}, **declared)

    refusal = refused(lambda: amend_source_terms(changed, data_root), RefusalCode.IMPORT_CONFLICT)

    assert refusal.details == {"source_sha256": imported.source_sha256, "changed_facts": facts}
    assert evidence(directory) == before


def test_an_amendment_cannot_change_or_import_a_file(
    imported: ImportResult, write_recording: WriteRecording, media: Path, data_root: Path
) -> None:
    write_clip(media / "other.mkv", frames=12)
    other = write_recording("other.mkv", sensitivity={"level": "high"})
    directory = imported.manifest_path.parent
    before = evidence(directory)

    refusal = refused(lambda: amend_source_terms(other, data_root), RefusalCode.IMPORT_CONFLICT)

    assert refusal.details == {"source_sha256": sha256_file(media / "other.mkv")}
    assert [path.name for path in (data_root / "import").iterdir()] == [imported.source_sha256]
    assert evidence(directory) == before


def test_an_amendment_on_an_empty_data_root_writes_nothing(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    declared = write_recording()

    refused(lambda: amend_source_terms(declared, data_root), RefusalCode.IMPORT_CONFLICT)

    assert not data_root.exists()


def test_a_declared_hash_finds_the_source_after_the_original_is_gone(
    clip: Path, imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    clip.unlink()
    named = write_recording(sha256=imported.source_sha256, sensitivity={"level": "high"})

    result = amend_source_terms(named, data_root)

    record = read_source(result.manifest_path)
    assert isinstance(record["source"], dict)
    assert record["source"]["sha256_declared"] is False


def test_with_neither_the_original_nor_a_declared_hash_the_source_cannot_be_named(
    clip: Path, imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    clip.unlink()
    declared = write_recording()

    refused(lambda: amend_source_terms(declared, data_root), RefusalCode.SOURCE_NOT_FOUND)


def test_a_file_that_contradicts_its_declared_hash_isrefused(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    declared = write_recording(sha256="0" * 64)

    refused(lambda: amend_source_terms(declared, data_root), RefusalCode.SOURCE_HASH_MISMATCH)


def test_an_unreadable_source_is_refused(
    imported: ImportResult,
    write_recording: WriteRecording,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny(_: Path) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("ss_track.corpus.sources.amendment.sha256_file", deny)
    declared = write_recording()

    refused(lambda: amend_source_terms(declared, data_root), RefusalCode.SOURCE_UNREADABLE)


def test_a_newer_record_is_refused_and_left_alone(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    reseal(imported.manifest_path, schema_version=3)
    before = imported.manifest_path.read_bytes()
    declared = write_recording(sensitivity={"level": "high"})

    refused(lambda: amend_source_terms(declared, data_root), RefusalCode.RECORD_SCHEMA_UNSUPPORTED)

    assert imported.manifest_path.read_bytes() == before


def test_a_tampered_record_isrefused(
    imported: ImportResult, write_recording: WriteRecording, data_root: Path
) -> None:
    imported.manifest_path.chmod(0o644)
    imported.manifest_path.write_text("{}", encoding="ascii")
    declared = write_recording(sensitivity={"level": "high"})

    refused(lambda: amend_source_terms(declared, data_root), RefusalCode.RECORD_TAMPERED)
