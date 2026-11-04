"""Remuxed copies across a declared chain: where a copy may sit and where it is leakage."""

from pathlib import Path

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus._shared_frames import V0, V1, V2, check_of, named, not_compared, stage_refused
from tests.corpus.conftest import WriteCorpus, single_group, stream_of


def test_a_remux_a_linked_version_places_elsewhere_is_leakage_naming_both_versions(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single_group("site-a", "development", stream_of(original, stream_id="kept"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    v2 = [*v1, single_group("site-b", "locked", stream_of(copy, stream_id="held-out"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    refusal = stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE)

    # The kept stream is in v2 as well, so v2 holds the pair by itself and with v1.
    assert refusal.details["corpus_id"] == V2
    runs = refusal.details["shared_runs"]
    assert isinstance(runs, list)
    named = {
        tuple((side["corpus_id"], side["stream_id"]) for side in run["streams"])  # type: ignore[call-overload,index]
        for run in runs
    }
    assert named == {
        ((V1, "kept"), (V2, "held-out")),
        ((V2, "held-out"), (V2, "kept")),
    }


def test_a_version_that_keeps_only_the_copy_elsewhere_is_refused_by_its_predecessor(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    """Nothing in the new version shows the conflict: only the version behind it can."""
    v1 = [single_group("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    v2 = [single_group("site-b", "development", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    refusal = stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert named(refusal, "corpus_id") == [V1, V2]
    assert named(refusal, "group_id") == ["site-a", "site-b"]
    assert named(refusal, "split") == ["development", "development"]


def test_a_copy_is_compared_with_the_whole_declared_chain(
    copy: ImportResult,
    original: ImportResult,
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v0 = [single_group("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v0, corpus_id=V0), data_root)
    stage_corpus(V0, data_root)
    v1 = [single_group("site-c", "development", stream_of(first, stream_id="other"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1, supersedes=V0), data_root)
    assert check_of(stage_corpus(V1, data_root))["compared_versions"] == [V0]
    v2 = [*v1, single_group("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    refusal = stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert named(refusal, "corpus_id") == [V0, V2]


def test_a_copy_in_its_originals_group_across_versions_stages_normally(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single_group("site-a", "development", stream_of(original, stream_id="a"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    v2 = [single_group("site-a", "development", stream_of(copy, stream_id="b"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    assert check_of(stage_corpus(V2, data_root)) == {
        "min_shared_frames": 8,
        "compared_versions": [V1],
        "not_compared": [],
    }


def test_a_version_repaired_by_dropping_its_copy_stages_normally(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    """A refused version has no frame set, so it was never evidence and cannot block its repair."""
    kept = single_group("site-a", "development", stream_of(original, stream_id="kept"))
    refused = [kept, single_group("site-b", "locked", stream_of(copy, stream_id="copy"))]
    build_corpus(write_grouped_corpus(refused, corpus_id=V1), data_root)
    stage_refused(V1, data_root, RefusalCode.SPLIT_LEAKAGE)
    build_corpus(write_grouped_corpus([kept], corpus_id=V2, supersedes=V1), data_root)

    result = stage_corpus(V2, data_root)

    assert not_compared(result) == [(V1, "no_frame_set", [])]
    assert verify_corpus_frames(V2, data_root).status == "verified"
