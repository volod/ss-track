"""How a damaged, unstaged or stale generated case is refused, before anything is written."""

import shutil
from pathlib import Path

import pytest

from ss_track.core.evidence.sealed import read_sealed
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    open_frame_bundle,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from tests.corpus.cases._staged_cases import CORPUS, SHAKE, case_frames_root, stage_cases
from tests.corpus.conftest import (
    WriteCorpus,
    bundle_identity,
    case_of,
    reseal,
    reseal_bundle,
    stream_of,
)


def test_a_corrupted_case_frame_fails_verification_by_name(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, SHAKE)
    )
    frame = root / "shaken" / "00000004.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"\0" + frame.read_bytes()[1:])

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(CORPUS, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert caught.value.details["frames"] == [
        {"stream_id": "shaken", "frame": "00000004.rgb24", "reason": "hash_mismatch"}
    ]
    with pytest.raises(CorpusRefusal) as again:
        stage_corpus(CORPUS, data_root)
    assert again.value.code is RefusalCode.FRAME_CORRUPTED


def test_a_case_made_from_a_corrupted_parent_is_refused_and_leaves_nothing(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(
        write_corpus(
            [
                stream_of(
                    imported,
                    generated_cases=[case_of("shaken", "camera_shake", 1, SHAKE)],
                )
            ]
        ),
        data_root,
    )
    stage_corpus(CORPUS, data_root)
    root = case_frames_root(data_root)
    (root / "shaken").chmod(0o755)
    shutil.rmtree(root / "shaken")
    frame = root / "one" / "00000005.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"\0" + frame.read_bytes()[1:])

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert not (root / "shaken").exists()
    assert list(root.glob(".incoming-*")) == []


def test_verify_requires_every_case_to_be_staged(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, SHAKE)
    )
    (root / "shaken").chmod(0o755)
    shutil.rmtree(root / "shaken")

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(CORPUS, data_root)

    assert caught.value.code is RefusalCode.BUNDLE_NOT_STAGED
    assert caught.value.details == {"stream_id": "shaken"}


def test_verify_reports_each_case_with_its_transform(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    stage_cases(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, SHAKE))

    result = verify_corpus_frames(CORPUS, data_root)

    assert {item.stream_id: item.transform for item in result.bundles} == {
        "one": "identity",
        "shaken": "camera_shake",
    }


def _repoint_parent(bundle: Path, parent_bundle_sha256: str) -> None:
    """Make a self-consistent case record that names other parent frames."""
    reseal_bundle(bundle, bundle_identity(bundle) | {"parent_bundle_sha256": parent_bundle_sha256})


def test_a_case_from_other_parent_frames_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, SHAKE)
    )
    _repoint_parent(root / "shaken", "e" * 64)

    for action in (stage_corpus, verify_corpus_frames):
        with pytest.raises(CorpusRefusal) as caught:
            action(CORPUS, data_root)
        assert caught.value.code is RefusalCode.BUNDLE_CONFLICT
        assert caught.value.details["parent_stream_id"] == "one"


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param({"transform_revision": 99}, id="other-revision"),
        pytest.param({"transform": "removed_transform"}, id="unknown-transform"),
    ],
)
def test_a_stored_case_this_code_cannot_reproduce_refuses_before_any_write(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    stored: dict[str, object],
) -> None:
    cases = [case_of("shaken", "camera_shake", 1, SHAKE)]
    result = build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)
    manifest = read_sealed(result.manifest_path, CORPUS_MANIFEST)
    reseal(result.manifest_path, generated_cases=[manifest["generated_cases"][0] | stored])

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.TRANSFORM_REVISION_MISMATCH
    assert not case_frames_root(data_root).exists()


def test_a_bundle_with_a_broken_generated_record_is_tampered(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, SHAKE)
    )
    identity = bundle_identity(root / "shaken")
    reseal_bundle(
        root / "shaken", {key: value for key, value in identity.items() if key != "recipe"}
    )

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(root / "shaken")

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
