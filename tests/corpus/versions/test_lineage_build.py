"""Linked corpus versions built from imported sources: links, deltas and seals."""

import json
import shutil
from pathlib import Path

import pytest

from ss_track.core.evidence.sealed import read_sealed
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from tests.corpus.conftest import (
    HEAD,
    TAIL,
    WriteCorpus,
    WriteRecording,
    reseal,
    single_group,
    stream_of,
)
from tests.corpus.versions._lineage_build import build_version, source_of


def test_added_sources_build_and_the_result_lists_every_change(
    first: ImportResult,
    second: ImportResult,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    kept = single_group("site-a", "development", stream_of(first, stream_id="kept"))
    removed = single_group("site-b", "development", stream_of(second, stream_id="removed"))
    added = single_group("site-c", "locked", stream_of(third, stream_id="added"))
    v1 = build_version(write_grouped_corpus, data_root, "pilot-v1", [kept, removed])

    v2 = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [kept, added], supersedes="pilot-v1"
    )

    assert v2.status == "built"
    assert v2.to_record()["lineage"] == {
        "status": "linked",
        "supersedes": "pilot-v1",
        "supersedes_manifest_sha256": v1.manifest_sha256,
        "compared_versions": ["pilot-v1"],
        "added": [source_of(third) | {"group_id": "site-c", "split": "locked"}],
        "removed": [source_of(second) | {"group_id": "site-b", "split": "development"}],
        "kept": [source_of(first) | {"group_id": "site-a", "split": "development"}],
    }


def test_the_manifest_seals_the_predecessor_it_was_compared_with(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    v1 = build_version(write_grouped_corpus, data_root, "pilot-v1", groups)

    v2 = build_version(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")

    manifest = read_sealed(v2.manifest_path, CORPUS_MANIFEST)
    assert manifest["supersedes"] == {
        "corpus_id": "pilot-v1",
        "manifest_sha256": v1.manifest_sha256,
    }


def test_a_version_naming_no_predecessor_says_so_and_stores_no_link(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    result = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(first))],
    )

    assert result.to_record()["lineage"] == {"status": "no_lineage"}
    assert "supersedes" not in read_sealed(result.manifest_path, CORPUS_MANIFEST)


def test_a_version_that_links_nothing_is_not_compared_with_anything(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )

    unlinked = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [single_group("held-out", "locked", stream)]
    )

    assert unlinked.status == "built"
    assert unlinked.to_record()["lineage"] == {"status": "no_lineage"}


def test_a_source_may_come_back_to_the_place_it_left(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    seen = single_group("site-a", "development", stream_of(first, stream_id="seen"))
    other = single_group("site-b", "development", stream_of(second, stream_id="other"))
    build_version(write_grouped_corpus, data_root, "pilot-v1", [seen, other])
    build_version(write_grouped_corpus, data_root, "pilot-v2", [other], supersedes="pilot-v1")

    v3 = build_version(
        write_grouped_corpus, data_root, "pilot-v3", [seen, other], supersedes="pilot-v2"
    )

    assert v3.to_record()["lineage"]["compared_versions"] == [  # type: ignore[index,call-overload]
        "pilot-v2",
        "pilot-v1",
    ]


def test_a_kept_source_may_change_its_window_and_stream_names(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(first, stream_id="a", selection=HEAD))],
    )

    v2 = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("site-a", "development", stream_of(first, stream_id="b", selection=TAIL))],
        supersedes="pilot-v1",
    )

    assert v2.to_record()["lineage"]["kept"] == [  # type: ignore[index,call-overload]
        source_of(first) | {"group_id": "site-a", "split": "development"}
    ]


def test_a_kept_source_may_change_its_terms(
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    write_recording: WriteRecording,
    data_root: Path,
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    build_version(write_grouped_corpus, data_root, "pilot-v1", groups)
    shutil.rmtree(first.manifest_path.parent)
    narrowed = write_recording("clip-2.mkv", sensitivity={"level": "high"})
    assert import_source(narrowed, data_root).manifest_sha256 != first.manifest_sha256

    v2 = build_version(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")

    assert v2.to_record()["lineage"]["kept"] == [  # type: ignore[index,call-overload]
        source_of(first) | {"group_id": "site-a", "split": "development"}
    ]


def test_stage_and_verify_do_not_need_a_versions_predecessors(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    v1 = build_version(write_grouped_corpus, data_root, "pilot-v1", groups)
    build_version(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")
    v1.manifest_path.unlink()

    assert stage_corpus("pilot-v2", data_root).status == "staged"
    assert verify_corpus_frames("pilot-v2", data_root).status == "verified"


def test_repeating_a_linked_build_changes_nothing_and_reports_the_same_lineage(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    build_version(write_grouped_corpus, data_root, "pilot-v1", groups)
    declared = write_grouped_corpus(groups, corpus_id="pilot-v2", supersedes="pilot-v1")

    built = build_corpus(declared, data_root)
    repeated = build_corpus(declared, data_root)

    assert (built.status, repeated.status) == ("built", "unchanged")
    assert repeated.manifest_sha256 == built.manifest_sha256
    assert repeated.lineage == built.lineage


def test_naming_a_predecessor_changes_a_versions_hash(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    build_version(write_grouped_corpus, data_root, "pilot-v1", groups)
    unlinked = build_version(write_grouped_corpus, data_root, "pilot-v2", groups)

    with pytest.raises(CorpusRefusal) as caught:
        build_version(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert caught.value.details["existing_manifest_sha256"] == unlinked.manifest_sha256


@pytest.mark.parametrize("major", [4, 1.0], ids=["newer", "unstated"])
def test_a_predecessor_with_no_projection_is_not_compared_and_fails_nothing(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path, major: object
) -> None:
    stream = stream_of(first)
    v1 = build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    reseal(v1.manifest_path, schema_version=major)
    resealed = json.loads(v1.manifest_path.read_text(encoding="ascii"))["manifest_sha256"]

    v2 = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream)],
        supersedes="pilot-v1",
    )

    lineage = v2.to_record()["lineage"]
    assert lineage == {
        "status": "linked",
        "supersedes": "pilot-v1",
        "supersedes_manifest_sha256": resealed,
        "compared_versions": [],
        "added": [],
        "removed": [],
        "kept": [],
        "not_compared": [{"corpus_id": "pilot-v1", "reason": "other_schema", "stream_ids": []}],
    }
