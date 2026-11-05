"""The frame set refuses a bundle or a record that changed after staging, naming each one."""

from pathlib import Path

import pytest

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.bundles.staging import FramesResult
from tests.corpus.bundles._frame_set import (
    CORPUS,
    Refused,
    bundle_hashes,
    bundle_path,
    frame_set_path,
    read_record,
    refused_by,
    remove_bundle,
    replace_bundle,
    stage_two_streams,
)
from tests.corpus.conftest import (
    WriteCorpus,
    reseal,
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


def test_a_replaced_bundle_fails_verify_by_name(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    hashes = bundle_hashes(staged)
    replace_bundle(data_root, "two", "one")

    refusal = verify_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == [
        {
            "stream_id": "two",
            "reason": "replaced",
            "frame_set_bundle_sha256": hashes["two"],
            "bundle_sha256": hashes["one"],
        }
    ]
    assert refusal.details["corpus_id"] == CORPUS
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
    stage_corpus(CORPUS, data_root)
    replace_bundle(data_root, "one", "three")
    replace_bundle(data_root, "two", "three")

    bundles = verify_refuses(RefusalCode.FRAME_SET_MISMATCH).details["bundles"]

    assert isinstance(bundles, list)
    assert [entry["stream_id"] for entry in bundles] == ["one", "two"]  # type: ignore[index,call-overload]


def test_a_replaced_parent_of_a_case_is_named(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    replace_bundle(data_root, "one", "two")

    refusal = verify_refuses(RefusalCode.BUNDLE_CONFLICT)

    assert refusal.details["stream_id"] == "shaken"
    assert refusal.details["parent_stream_id"] == "one"


def test_a_stage_cannot_carry_the_record_along_with_a_replaced_bundle(
    staged: FramesResult, data_root: Path, stage_refuses: Refused
) -> None:
    pinned = frame_set_path(data_root).read_bytes()
    replace_bundle(data_root, "two", "one")

    refusal = stage_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert frame_set_path(data_root).read_bytes() == pinned
    assert refusal.details["frame_set_sha256"] == staged.frame_set_sha256


def test_a_missing_bundle_fails_verify_by_name_and_staging_restores_one_hash(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    remove_bundle(data_root, "two")

    refusal = verify_refuses(RefusalCode.BUNDLE_NOT_STAGED)

    assert refusal.details == {"stream_id": "two"}
    assert stage_corpus(CORPUS, data_root).frame_set_sha256 == staged.frame_set_sha256
    assert verify_corpus_frames(CORPUS, data_root).status == "verified"


def test_a_directory_no_frame_set_names_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused, stage_refuses: Refused
) -> None:
    stray = bundle_path(data_root, "stray")
    stray.mkdir()

    for refused in (verify_refuses, stage_refuses):
        refusal = refused(RefusalCode.FRAME_SET_MISMATCH)
        assert refusal.details["bundles"] == [{"stream_id": "stray", "reason": "unnamed"}]

    stray.rmdir()
    assert verify_corpus_frames(CORPUS, data_root).status == "verified"


def test_a_first_stage_writes_no_record_beside_a_stray_directory(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path, stage_refuses: Refused
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)
    bundle_path(data_root, "stray").mkdir(parents=True)

    refusal = stage_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == [{"stream_id": "stray", "reason": "unnamed"}]
    assert not frame_set_path(data_root).exists()


def test_a_record_of_another_corpus_state_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    reseal(frame_set_path(data_root), corpus_manifest_sha256="c" * 64)

    refusal = verify_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == []
    assert refusal.details["frame_set_corpus_manifest_sha256"] == "c" * 64


def test_lines_on_one_side_only_are_named(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    record = read_record(frame_set_path(data_root))
    lines = record["bundles"]
    assert isinstance(lines, list)
    gone = {**lines[-1], "stream_id": "gone"}
    reseal(frame_set_path(data_root), bundles=[*lines[:-1], gone])

    refusal = verify_refuses(RefusalCode.FRAME_SET_MISMATCH)

    assert refusal.details["bundles"] == [
        {"stream_id": "gone", "reason": "missing"},
        {"stream_id": "two", "reason": "unnamed"},
    ]


def test_a_damaged_record_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    path = frame_set_path(data_root)
    path.chmod(0o644)
    path.write_text(path.read_text(encoding="ascii").replace("one", "eno"), encoding="ascii")

    verify_refuses(RefusalCode.RECORD_TAMPERED)


def test_a_record_of_another_schema_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    reseal(frame_set_path(data_root), schema_version=99)

    verify_refuses(RefusalCode.RECORD_SCHEMA_UNSUPPORTED)


@pytest.mark.parametrize(
    "bundles", [[{"stream_id": "one"}, 3], [{}], [{"stream_id": []}], "no", None]
)
def test_a_malformed_list_of_bundles_is_refused(
    staged: FramesResult, data_root: Path, verify_refuses: Refused, bundles: object
) -> None:
    reseal(frame_set_path(data_root), bundles=bundles)

    verify_refuses(RefusalCode.RECORD_TAMPERED)


def test_a_damaged_frame_is_still_named(
    staged: FramesResult, data_root: Path, verify_refuses: Refused
) -> None:
    parent = bundle_path(data_root, "one")
    case = bundle_path(data_root, "shaken")
    # A frame the case left unchanged is one inode with two names, so it would be named twice.
    frame = next(
        path
        for path in sorted(parent.glob("*.rgb24"))
        if path.stat().st_ino != (case / path.name).stat().st_ino
    )
    frame.chmod(0o644)
    frame.write_bytes(b"x" * frame.stat().st_size)

    refusal = verify_refuses(RefusalCode.FRAME_CORRUPTED)

    assert refusal.details == {
        "damaged_count": 1,
        "frames": [{"stream_id": "one", "frame": frame.name, "reason": "hash_mismatch"}],
    }
