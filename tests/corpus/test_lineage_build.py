"""Linked corpus versions built from imported sources, from declaration to exit status."""

import json
import logging
import shutil
from pathlib import Path

import pytest
import yaml

from ss_track.cli import EXIT_OK, EXIT_REFUSED, main
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.builder import BuildResult
from ss_track.corpus.sealed import read_sealed
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    corpus_declaration,
    encounter_of,
    group_of,
    place_of,
    reseal,
    stream_of,
)

_CORPUS_KIND = "ss-track.corpus-manifest"
_HEAD = {"start_frame": 0, "end_frame": 4}
_TAIL = {"start_frame": 4, "end_frame": 8}
type Group = dict[str, object]


def _single(group: str, split: str, stream: dict[str, object]) -> Group:
    return group_of(group, split, encounter_of(f"enc-{stream['stream_id']}", stream))


def _built(
    write: WriteCorpus, data_root: Path, version: str, groups: list[Group], **fields: object
) -> BuildResult:
    return build_corpus(write(groups, corpus_id=version, **fields), data_root)


def _refused(
    write: WriteCorpus,
    data_root: Path,
    version: str,
    groups: list[Group],
    code: RefusalCode,
    **fields: object,
) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        _built(write, data_root, version, groups, **fields)
    assert caught.value.code is code
    assert not (data_root / "corpus" / version).exists()
    return caught.value


def _source_of(imported: ImportResult) -> dict[str, str]:
    return {"source_sha256": imported.source_sha256}


def test_a_source_moved_from_development_to_locked_is_leakage(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    _built(write_grouped_corpus, data_root, "pilot-v1", [_single("site-a", "development", stream)])

    refusal = _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [_single("held-out", "locked", stream)],
        RefusalCode.SPLIT_LEAKAGE,
        supersedes="pilot-v1",
    )

    assert "pilot-v2" in refusal.message
    assert refusal.details == {
        "corpus_id": "pilot-v2",
        "moved_sources": [
            {
                "source_sha256": first.source_sha256,
                "from": place_of("pilot-v1", "site-a", "development"),
                "to": place_of("pilot-v2", "held-out", "locked"),
            }
        ],
        "moved_groups": [],
    }


def test_a_refused_move_exits_one_with_the_code_in_its_record(
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_root))
    stream = stream_of(first)
    v1 = [_single("site-a", "development", stream)]
    assert main(["corpus", "build", "--manifest", str(write_grouped_corpus(v1))]) == EXIT_OK
    v2 = write_grouped_corpus(
        [_single("site-a", "locked", stream)], corpus_id="pilot-v2", supersedes="pilot-v1"
    )

    with caplog.at_level(logging.INFO):
        status = main(["corpus", "build", "--manifest", str(v2)])

    assert status == EXIT_REFUSED
    assert json.loads(caplog.messages[-1])["code"] == "SPLIT_LEAKAGE"


def test_added_sources_build_and_the_result_lists_every_change(
    first: ImportResult,
    second: ImportResult,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    kept = _single("site-a", "development", stream_of(first, stream_id="kept"))
    removed = _single("site-b", "development", stream_of(second, stream_id="removed"))
    added = _single("site-c", "locked", stream_of(third, stream_id="added"))
    v1 = _built(write_grouped_corpus, data_root, "pilot-v1", [kept, removed])

    v2 = _built(write_grouped_corpus, data_root, "pilot-v2", [kept, added], supersedes="pilot-v1")

    assert v2.status == "built"
    assert v2.to_record()["lineage"] == {
        "status": "linked",
        "supersedes": "pilot-v1",
        "supersedes_manifest_sha256": v1.manifest_sha256,
        "compared_versions": ["pilot-v1"],
        "added": [_source_of(third) | {"group_id": "site-c", "split": "locked"}],
        "removed": [_source_of(second) | {"group_id": "site-b", "split": "development"}],
        "kept": [_source_of(first) | {"group_id": "site-a", "split": "development"}],
    }


def test_the_manifest_seals_the_predecessor_it_was_compared_with(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    v1 = _built(write_grouped_corpus, data_root, "pilot-v1", groups)

    v2 = _built(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")

    manifest = read_sealed(v2.manifest_path, _CORPUS_KIND)
    assert manifest["supersedes"] == {
        "corpus_id": "pilot-v1",
        "manifest_sha256": v1.manifest_sha256,
    }


def test_a_version_naming_no_predecessor_says_so_and_stores_no_link(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    result = _built(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [_single("site-a", "development", stream_of(first))],
    )

    assert result.to_record()["lineage"] == {"status": "no_lineage"}
    assert "supersedes" not in read_sealed(result.manifest_path, _CORPUS_KIND)


def test_a_version_that_links_nothing_is_not_compared_with_anything(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    _built(write_grouped_corpus, data_root, "pilot-v1", [_single("site-a", "development", stream)])

    unlinked = _built(
        write_grouped_corpus, data_root, "pilot-v2", [_single("held-out", "locked", stream)]
    )

    assert unlinked.status == "built"
    assert unlinked.to_record()["lineage"] == {"status": "no_lineage"}


def test_a_missing_predecessor_is_not_built_and_reads_no_source(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    (first.manifest_path.parent / "source.mkv").unlink()
    groups = [_single("site-a", "development", stream_of(first))]

    refusal = _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        groups,
        RefusalCode.CORPUS_NOT_BUILT,
        supersedes="pilot-v1",
    )

    assert refusal.details == {"corpus_id": "pilot-v1"}


def test_a_missing_older_version_of_the_chain_is_not_built(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    v1 = _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    _built(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")
    v1.manifest_path.unlink()

    refusal = _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v3",
        groups,
        RefusalCode.CORPUS_NOT_BUILT,
        supersedes="pilot-v2",
    )

    assert refusal.details == {"corpus_id": "pilot-v1"}


def test_a_chain_refuses_a_source_dropped_by_the_version_between(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    seen = _single("site-a", "development", stream_of(first, stream_id="seen"))
    other = _single("site-b", "development", stream_of(second, stream_id="other"))
    _built(write_grouped_corpus, data_root, "pilot-v1", [seen, other])
    v2 = _built(write_grouped_corpus, data_root, "pilot-v2", [other], supersedes="pilot-v1")
    assert v2.to_record()["lineage"]["removed"] == [  # type: ignore[index,call-overload]
        _source_of(first) | {"group_id": "site-a", "split": "development"}
    ]

    refusal = _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v3",
        [other, _single("held-out", "locked", stream_of(first, stream_id="seen"))],
        RefusalCode.SPLIT_LEAKAGE,
        supersedes="pilot-v2",
    )

    moved = refusal.details["moved_sources"]
    assert isinstance(moved, list) and isinstance(moved[0], dict)
    assert moved[0]["from"] == place_of("pilot-v1", "site-a", "development")


def test_a_source_may_come_back_to_the_place_it_left(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    seen = _single("site-a", "development", stream_of(first, stream_id="seen"))
    other = _single("site-b", "development", stream_of(second, stream_id="other"))
    _built(write_grouped_corpus, data_root, "pilot-v1", [seen, other])
    _built(write_grouped_corpus, data_root, "pilot-v2", [other], supersedes="pilot-v1")

    v3 = _built(write_grouped_corpus, data_root, "pilot-v3", [seen, other], supersedes="pilot-v2")

    assert v3.to_record()["lineage"]["compared_versions"] == [  # type: ignore[index,call-overload]
        "pilot-v2",
        "pilot-v1",
    ]


def test_a_group_changing_split_with_new_sources_is_leakage(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    _built(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [_single("site-a", "development", stream_of(first))],
    )

    refusal = _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [_single("site-a", "locked", stream_of(second))],
        RefusalCode.SPLIT_LEAKAGE,
        supersedes="pilot-v1",
    )

    assert refusal.details["moved_groups"] == [
        {
            "from": place_of("pilot-v1", "site-a", "development"),
            "to": place_of("pilot-v2", "site-a", "locked"),
        }
    ]


def test_a_kept_source_may_change_its_window_and_stream_names(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    _built(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [_single("site-a", "development", stream_of(first, stream_id="a", selection=_HEAD))],
    )

    v2 = _built(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [_single("site-a", "development", stream_of(first, stream_id="b", selection=_TAIL))],
        supersedes="pilot-v1",
    )

    assert v2.to_record()["lineage"]["kept"] == [  # type: ignore[index,call-overload]
        _source_of(first) | {"group_id": "site-a", "split": "development"}
    ]


def test_a_kept_source_may_change_its_terms(
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    write_recording: WriteRecording,
    data_root: Path,
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    shutil.rmtree(first.manifest_path.parent)
    narrowed = write_recording("clip-2.mkv", sensitivity={"level": "high"})
    assert import_source(narrowed, data_root).manifest_sha256 != first.manifest_sha256

    v2 = _built(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")

    assert v2.to_record()["lineage"]["kept"] == [  # type: ignore[index,call-overload]
        _source_of(first) | {"group_id": "site-a", "split": "development"}
    ]


def test_stage_and_verify_do_not_need_a_versions_predecessors(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    v1 = _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    _built(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")
    v1.manifest_path.unlink()

    assert stage_corpus("pilot-v2", data_root).status == "staged"
    assert verify_corpus_frames("pilot-v2", data_root).status == "verified"


def test_repeating_a_linked_build_changes_nothing_and_reports_the_same_lineage(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    declared = write_grouped_corpus(groups, corpus_id="pilot-v2", supersedes="pilot-v1")

    built = build_corpus(declared, data_root)
    repeated = build_corpus(declared, data_root)

    assert (built.status, repeated.status) == ("built", "unchanged")
    assert repeated.manifest_sha256 == built.manifest_sha256
    assert repeated.lineage == built.lineage


def test_naming_a_predecessor_changes_a_versions_hash(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    unlinked = _built(write_grouped_corpus, data_root, "pilot-v2", groups)

    with pytest.raises(CorpusRefusal) as caught:
        _built(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert caught.value.details["existing_manifest_sha256"] == unlinked.manifest_sha256


def test_a_rebuilt_predecessor_is_refused_when_its_successor_is_named(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    v1 = _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    _built(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")
    v1.manifest_path.chmod(0o644)
    v1.manifest_path.unlink()
    window = stream_of(first, selection=_HEAD)
    _built(write_grouped_corpus, data_root, "pilot-v1", [_single("site-a", "development", window)])

    refusal = _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v3",
        groups,
        RefusalCode.CORPUS_CONFLICT,
        supersedes="pilot-v2",
    )

    assert refusal.details["pinned_manifest_sha256"] == v1.manifest_sha256


def test_a_damaged_predecessor_is_refused(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    v1 = _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    v1.manifest_path.chmod(0o644)
    v1.manifest_path.write_text("{}", encoding="ascii")

    _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        groups,
        RefusalCode.RECORD_TAMPERED,
        supersedes="pilot-v1",
    )


def test_a_predecessor_from_another_schema_is_refused_by_name(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [_single("site-a", "development", stream_of(first))]
    v1 = _built(write_grouped_corpus, data_root, "pilot-v1", groups)
    reseal(v1.manifest_path, schema_version=2)

    _refused(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        groups,
        RefusalCode.RECORD_SCHEMA_UNSUPPORTED,
        supersedes="pilot-v1",
    )


@pytest.mark.parametrize(
    ("value", "words"),
    [
        pytest.param("pilot-v1", "supersede itself", id="itself"),
        pytest.param("Not A Name", "must match", id="not-an-identifier"),
        pytest.param(None, "non-empty string", id="null"),
        pytest.param(7, "non-empty string", id="number"),
    ],
)
def test_a_malformed_supersedes_is_refused(
    media: Path, data_root: Path, value: object, words: str
) -> None:
    declared = media / "corpus.yaml"
    body = corpus_declaration([], supersedes=value)
    declared.write_text(yaml.safe_dump(body), encoding="utf-8")

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(declared, data_root)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert words in caught.value.message
