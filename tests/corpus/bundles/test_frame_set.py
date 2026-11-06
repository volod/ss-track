"""The frame set: staging writes one sealed hash for everything a corpus version staged."""

from pathlib import Path

import pytest

from ss_track.corpus import (
    ImportResult,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.bundles.stage_report import FramesResult
from ss_track.schema import validate_file
from tests.corpus.bundles._frame_set import (
    CORPUS,
    SHAKE,
    bundle_hashes,
    frame_set_path,
    read_record,
    stage_two_streams,
)
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    stream_of,
)


@pytest.fixture
def staged(
    first: ImportResult, second: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> FramesResult:
    return stage_two_streams(first, second, write_corpus, data_root)


def test_staging_names_every_bundle_and_the_source_record_it_rests_on(
    staged: FramesResult, first: ImportResult, second: ImportResult, data_root: Path
) -> None:
    record = read_record(frame_set_path(data_root))
    hashes = bundle_hashes(staged)
    corpus = read_record(data_root / "corpus" / CORPUS / "manifest.json")

    assert record == {
        "kind": "ss-track.frame-set",
        "schema_version": 1,
        "corpus_id": CORPUS,
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
    assert verify_corpus_frames(CORPUS, data_root).frame_set_sha256 == staged.frame_set_sha256
    assert stage_corpus(CORPUS, data_root).frame_set_sha256 == staged.frame_set_sha256


def test_a_staged_record_conforms_to_its_contract_case_lines_included(
    staged: FramesResult, data_root: Path
) -> None:
    path = frame_set_path(data_root)
    before = path.read_bytes()

    result = validate_file(path)

    assert result.contract == "record/frame-set"
    assert result.seal_checked
    assert path.read_bytes() == before
    lines = read_record(path)["bundles"]
    assert isinstance(lines, list)
    assert {line["stream_id"]: line["parent_stream_id"] for line in lines} == {
        "one": None,
        "shaken": "one",
        "two": None,
    }


def test_the_record_is_read_only(staged: FramesResult, data_root: Path) -> None:
    assert frame_set_path(data_root).stat().st_mode & 0o777 == 0o444


def test_two_stagings_give_one_hash_across_data_roots(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, tmp_path: Path
) -> None:
    records = []
    for name in ("a", "b/nested/deeper"):
        root = tmp_path / name
        imported = import_source(write_recording(), root)
        cases = [case_of("shaken", "camera_shake", 1, SHAKE)]
        build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), root)
        stage_corpus(CORPUS, root)
        records.append(frame_set_path(root).read_bytes())

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


def test_a_repeated_stage_leaves_the_record_alone(staged: FramesResult, data_root: Path) -> None:
    before = frame_set_path(data_root).stat()

    repeated = stage_corpus(CORPUS, data_root)

    after = frame_set_path(data_root).stat()
    assert repeated.status == "unchanged"
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
