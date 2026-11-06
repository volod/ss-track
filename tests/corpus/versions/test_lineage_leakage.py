"""A linked corpus version may not move material its declared predecessors placed."""

import logging
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.corpus import ImportResult, RefusalCode
from tests.corpus.conftest import (
    WriteCorpus,
    last_record,
    place_of,
    reseal,
    single_group,
    stream_of,
)
from tests.corpus.versions._lineage_build import build_version, refused_build, source_of


def test_a_source_moved_from_development_to_locked_is_leakage(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream)],
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
    v1 = [single_group("site-a", "development", stream)]
    assert main(["corpus", "build", "--manifest", str(write_grouped_corpus(v1))]) == EXIT_OK
    v2 = write_grouped_corpus(
        [single_group("site-a", "locked", stream)], corpus_id="pilot-v2", supersedes="pilot-v1"
    )

    with caplog.at_level(logging.INFO):
        status = main(["corpus", "build", "--manifest", str(v2)])

    assert status == EXIT_REFUSED
    assert last_record(caplog)["code"] == "SPLIT_LEAKAGE"


def test_a_chain_refuses_a_source_dropped_by_the_version_between(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    seen = single_group("site-a", "development", stream_of(first, stream_id="seen"))
    other = single_group("site-b", "development", stream_of(second, stream_id="other"))
    build_version(write_grouped_corpus, data_root, "pilot-v1", [seen, other])
    v2 = build_version(write_grouped_corpus, data_root, "pilot-v2", [other], supersedes="pilot-v1")
    assert v2.to_record()["lineage"]["removed"] == [  # type: ignore[index,call-overload]
        source_of(first) | {"group_id": "site-a", "split": "development"}
    ]

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v3",
        [other, single_group("held-out", "locked", stream_of(first, stream_id="seen"))],
        RefusalCode.SPLIT_LEAKAGE,
        supersedes="pilot-v2",
    )

    moved = refusal.details["moved_sources"]
    assert isinstance(moved, list) and isinstance(moved[0], dict)
    assert moved[0]["from"] == place_of("pilot-v1", "site-a", "development")


def test_a_group_changing_split_with_new_sources_is_leakage(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(first))],
    )

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("site-a", "locked", stream_of(second))],
        RefusalCode.SPLIT_LEAKAGE,
        supersedes="pilot-v1",
    )

    assert refusal.details["moved_groups"] == [
        {
            "from": place_of("pilot-v1", "site-a", "development"),
            "to": place_of("pilot-v2", "site-a", "locked"),
        }
    ]


def test_a_move_from_a_predecessor_of_another_major_is_leakage_not_a_schema_refusal(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    v1 = build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    reseal(v1.manifest_path, schema_version=2)

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream)],
        RefusalCode.SPLIT_LEAKAGE,
        supersedes="pilot-v1",
    )

    assert refusal.details["moved_sources"] == [
        {
            "source_sha256": first.source_sha256,
            "from": place_of("pilot-v1", "site-a", "development"),
            "to": place_of("pilot-v2", "held-out", "locked"),
        }
    ]
