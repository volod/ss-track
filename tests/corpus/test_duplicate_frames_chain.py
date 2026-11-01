"""Remuxed copies across a declared chain, and what a chain that cannot be read leaves unknown."""

import json
import shutil
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus._shared_frames import (
    V0,
    V1,
    V2,
    check_of,
    frame_set,
    named,
    not_compared,
    remove_bundle,
    single,
    stage_refused,
)
from tests.corpus.conftest import WriteCorpus, reseal, stream_of

type Group = dict[str, object]


def _seen_stream(source: ImportResult) -> Group:
    return single("site-a", "development", stream_of(source, stream_id="seen"))


def _pretend_another_decoder(manifest_path: Path, data_root: Path) -> None:
    """Leave a staged version as one built under another policy, with its bundles still its own."""
    reseal(manifest_path, decode_policy_sha256="0" * 64)
    seal = json.loads(manifest_path.read_text(encoding="ascii"))["manifest_sha256"]
    bundle = data_root / "corpus" / V1 / "frames" / "seen"
    bundle.chmod(0o755)
    reseal(bundle / "manifest.json", corpus_manifest_sha256=seal)


def test_a_remux_a_linked_version_places_elsewhere_is_leakage_naming_both_versions(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single("site-a", "development", stream_of(original, stream_id="kept"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    v2 = [*v1, single("site-b", "locked", stream_of(copy, stream_id="held-out"))]
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
    v1 = [single("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    v2 = [single("site-b", "development", stream_of(copy, stream_id="moved"))]
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
    v0 = [single("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v0, corpus_id=V0), data_root)
    stage_corpus(V0, data_root)
    v1 = [single("site-c", "development", stream_of(first, stream_id="other"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1, supersedes=V0), data_root)
    assert check_of(stage_corpus(V1, data_root))["compared_versions"] == [V0]
    v2 = [*v1, single("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    refusal = stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert named(refusal, "corpus_id") == [V0, V2]


def test_a_copy_in_its_originals_group_across_versions_stages_normally(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single("site-a", "development", stream_of(original, stream_id="a"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    v2 = [single("site-a", "development", stream_of(copy, stream_id="b"))]
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
    kept = single("site-a", "development", stream_of(original, stream_id="kept"))
    refused = [kept, single("site-b", "locked", stream_of(copy, stream_id="copy"))]
    build_corpus(write_grouped_corpus(refused, corpus_id=V1), data_root)
    stage_refused(V1, data_root, RefusalCode.SPLIT_LEAKAGE)
    build_corpus(write_grouped_corpus([kept], corpus_id=V2, supersedes=V1), data_root)

    result = stage_corpus(V2, data_root)

    assert not_compared(result) == [(V1, "no_frame_set", [])]
    assert verify_corpus_frames(V2, data_root).status == "verified"


def test_a_never_staged_predecessor_is_named_and_checked_once_it_is_staged(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    v2 = [single("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    staged = stage_corpus(V2, data_root)
    sealed = frame_set(data_root, V2).read_bytes()

    assert not_compared(staged) == [(V1, "no_frame_set", [])]
    assert not_compared(verify_corpus_frames(V2, data_root)) == [(V1, "no_frame_set", [])]

    stage_corpus(V1, data_root)

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(V2, data_root)
    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    assert named(stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE), "corpus_id") == [V1, V2]
    assert frame_set(data_root, V2).read_bytes() == sealed


def test_a_predecessor_with_no_staged_bundles_is_named_asnot_compared(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [single("site-a", "development", stream_of(original, stream_id="seen"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    remove_bundle(data_root, V1, "seen")
    v2 = [single("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    result = stage_corpus(V2, data_root)

    assert check_of(result)["compared_versions"] == []
    assert not_compared(result) == [(V1, "bundles_removed", ["seen"])]


def test_a_predecessor_missing_one_bundle_is_compared_on_the_rest(
    copy: ImportResult,
    original: ImportResult,
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [
        single("site-a", "development", stream_of(original, stream_id="seen")),
        single("site-c", "development", stream_of(first, stream_id="gone")),
    ]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    remove_bundle(data_root, V1, "gone")
    v2 = [single("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    assert named(stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE), "stream_id") == [
        "seen",
        "moved",
    ]


def test_a_removed_manifest_ends_the_chain_and_isnamed(
    first: ImportResult, second: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    v0 = [single("site-a", "development", stream_of(first, stream_id="a"))]
    built = build_corpus(write_grouped_corpus(v0, corpus_id=V0), data_root)
    v1 = [single("site-b", "development", stream_of(second, stream_id="b"))]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1, supersedes=V0), data_root)
    stage_corpus(V1, data_root)
    v2 = v1
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)
    built.manifest_path.unlink()

    result = stage_corpus(V2, data_root)

    assert check_of(result)["compared_versions"] == [V1]
    assert not_compared(result) == [(V0, "manifest_removed", [])]


def test_a_rebuilt_predecessor_is_refused_rather_than_compared(
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    groups = [single("site-a", "development", stream_of(first, stream_id="a"))]
    v1 = build_corpus(write_grouped_corpus(groups, corpus_id=V1), data_root)
    build_corpus(write_grouped_corpus(groups, corpus_id=V2, supersedes=V1), data_root)
    reseal(v1.manifest_path, scenario_rights={"sharing": "public", "max_sensitivity": "low"})

    refusal = stage_refused(V2, data_root, RefusalCode.CORPUS_CONFLICT)

    assert refusal.details["successor_corpus_id"] == V2


def test_a_predecessor_bundle_from_another_stream_is_refused_rather_than_compared(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [
        single("site-a", "development", stream_of(first, stream_id="a")),
        single("site-b", "development", stream_of(second, stream_id="b")),
    ]
    build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    frames = data_root / "corpus" / V1 / "frames"
    remove_bundle(data_root, V1, "b")
    shutil.copytree(frames / "a", frames / "b")
    build_corpus(write_grouped_corpus(v1, corpus_id=V2, supersedes=V1), data_root)

    refusal = stage_refused(V2, data_root, RefusalCode.BUNDLE_CONFLICT)

    assert refusal.details == {"stream_id": "b", "bundle_stream_id": "a"}


def test_a_damaged_predecessor_record_is_refused_rather_than_read_as_clear(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single("site-a", "development", stream_of(first, stream_id="a"))]
    build_corpus(write_grouped_corpus(groups, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    build_corpus(write_grouped_corpus(groups, corpus_id=V2, supersedes=V1), data_root)
    record = data_root / "corpus" / V1 / "frames" / "a" / "manifest.json"
    record.parent.chmod(0o755)
    record.chmod(0o644)
    record.write_text("{}", encoding="ascii")

    stage_refused(V2, data_root, RefusalCode.RECORD_TAMPERED)


def test_a_version_of_another_decode_policy_is_compared_but_proves_nothing_clear(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [_seen_stream(first)]
    built = build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    _pretend_another_decoder(built.manifest_path, data_root)
    v2 = [*v1, single("site-b", "locked", stream_of(second, stream_id="new"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    result = stage_corpus(V2, data_root)

    assert check_of(result)["compared_versions"] == [V1]
    assert not_compared(result) == [(V1, "other_decode_policy", [])]


def test_a_match_under_another_decode_policy_still_refuses(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [_seen_stream(original)]
    built = build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    _pretend_another_decoder(built.manifest_path, data_root)
    v2 = [single("site-b", "locked", stream_of(copy, stream_id="moved"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    assert named(stage_refused(V2, data_root, RefusalCode.SPLIT_LEAKAGE), "corpus_id") == [V1, V2]


def test_a_version_of_another_decode_policy_with_no_bundles_says_only_that(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    v1 = [_seen_stream(first)]
    built = build_corpus(write_grouped_corpus(v1, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    _pretend_another_decoder(built.manifest_path, data_root)
    remove_bundle(data_root, V1, "seen")
    v2 = [*v1, single("site-b", "locked", stream_of(second, stream_id="new"))]
    build_corpus(write_grouped_corpus(v2, corpus_id=V2, supersedes=V1), data_root)

    assert not_compared(stage_corpus(V2, data_root)) == [(V1, "bundles_removed", ["seen"])]
