from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    FrameBundle,
    ImportResult,
    RefusalCode,
    build_corpus,
    open_frame_bundle,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus.conftest import (
    WriteCorpus,
    encounter_of,
    group_of,
    reseal,
    stream_of,
)

_PUBLIC = {
    "holder": "Project Contributors",
    "basis": "owned",
    "retention": "project duration",
    "sharing": "public",
}


def _staged_bundles(data_root: Path) -> dict[str, FrameBundle]:
    root = data_root / "corpus" / "pilot-v1" / "frames"
    return {path.name: open_frame_bundle(path) for path in root.iterdir() if path.is_dir()}


def test_each_stream_of_an_encounter_stages_its_own_bundle_and_frame_identity(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    encounter = encounter_of(
        "enc01",
        stream_of(first, stream_id="enc01-cam0"),
        stream_of(second, stream_id="enc01-cam1"),
    )
    build_corpus(write_grouped_corpus([group_of("g", "development", encounter)]), data_root)

    stage_corpus("pilot-v1", data_root)

    bundles = _staged_bundles(data_root)
    assert sorted(bundles) == ["enc01-cam0", "enc01-cam1"]
    assert bundles["enc01-cam0"].frame_ref(0).stream_id == "enc01-cam0"
    assert bundles["enc01-cam1"].frame_ref(0).stream_id == "enc01-cam1"
    assert bundles["enc01-cam0"].frame_ref(0).source_sha256 == first.source_sha256
    assert verify_corpus_frames("pilot-v1", data_root).status == "verified"


def _swap(one: Path, two: Path) -> None:
    one.parent.chmod(0o755)
    one.chmod(0o755)
    two.chmod(0o755)
    held = one.with_name("held")
    one.rename(held)
    two.rename(one)
    held.rename(two)


def _staged_across_two_splits(
    first: ImportResult, second: ImportResult, write: WriteCorpus, data_root: Path
) -> Path:
    groups = [
        group_of("site-a", "development", encounter_of("e1", stream_of(first, stream_id="dev"))),
        group_of("site-b", "locked", encounter_of("e2", stream_of(second, stream_id="held-out"))),
    ]
    build_corpus(write(groups), data_root)
    stage_corpus("pilot-v1", data_root)
    return data_root / "corpus" / "pilot-v1" / "frames"


def test_a_bundle_moved_to_another_stream_cannot_cross_a_split(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    root = _staged_across_two_splits(first, second, write_grouped_corpus, data_root)
    _swap(root / "dev", root / "held-out")

    for action in (verify_corpus_frames, stage_corpus):
        with pytest.raises(CorpusRefusal) as caught:
            action("pilot-v1", data_root)
        assert caught.value.code is RefusalCode.BUNDLE_CONFLICT
        assert caught.value.details == {"stream_id": "dev", "bundle_stream_id": "held-out"}


def test_staging_refuses_a_source_whose_rights_changed_after_the_build(
    first: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(first)]), data_root)
    reseal(first.manifest_path, rights=_PUBLIC)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus("pilot-v1", data_root)

    assert caught.value.code is RefusalCode.SOURCE_RECORD_CHANGED
    assert caught.value.details["stream_id"] == "one"
    assert caught.value.details["corpus_source_manifest_sha256"] == first.manifest_sha256
    assert not (data_root / "corpus" / "pilot-v1" / "frames" / "one").exists()


def test_repeating_a_stage_notices_rights_that_changed_after_staging(
    first: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(first)]), data_root)
    stage_corpus("pilot-v1", data_root)
    reseal(first.manifest_path, rights=_PUBLIC)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus("pilot-v1", data_root)

    assert caught.value.code is RefusalCode.SOURCE_RECORD_CHANGED


def test_staging_refuses_a_corpus_whose_source_record_is_gone(
    first: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(first)]), data_root)
    first.manifest_path.unlink()

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus("pilot-v1", data_root)

    assert caught.value.code is RefusalCode.SOURCE_NOT_IMPORTED
