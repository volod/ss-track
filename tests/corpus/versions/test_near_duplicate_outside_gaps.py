"""Versions outside the chain that a near-duplicate report cannot read."""

import argparse
from pathlib import Path

import pytest

from ss_track.commands.corpus import _run_corpus_build
from ss_track.corpus import ImportResult, build_corpus
from ss_track.corpus.records.projections import OTHER_SCHEMA
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.versions.builder import CORPUS_MANIFEST
from ss_track.corpus.versions.unlinked import UNREADABLE
from tests.corpus.conftest import WriteCorpus, last_record, reseal, single_group, stream_of
from tests.corpus.versions._lineage_build import build_version
from tests.corpus.versions._unlinked import plant


def test_a_missing_and_an_unreadable_version_are_named(
    imported: ImportResult,
    write_grouped_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    locked = build_version(
        write_grouped_corpus,
        cli_root,
        "c-locked",
        [single_group("site-a", "development", stream_of(imported, stream_id="kept"))],
    )
    plant(cli_root, "b-broken", "{")
    (cli_root / "corpus" / "a-missing").mkdir()
    locked.manifest_path.parent.chmod(0)
    declaration = write_grouped_corpus(
        [single_group("held-out", "locked", stream_of(imported, stream_id="now"))],
        corpus_id="pilot-v2",
    )
    try:
        status = _run_corpus_build(argparse.Namespace(manifest=declaration))
    finally:
        locked.manifest_path.parent.chmod(0o755)

    reported = last_record(caplog)
    assert status == 0
    assert reported["status"] == "built"
    near = reported["near_duplicates"]
    assert isinstance(near, dict)
    assert near["not_compared"] == [
        {"corpus_id": "a-missing", "reason": UNREADABLE, "stream_ids": []},
        {"corpus_id": "b-broken", "reason": UNREADABLE, "stream_ids": []},
        {"corpus_id": "c-locked", "reason": UNREADABLE, "stream_ids": []},
    ]
    assert "near_duplicates" not in read_sealed(
        cli_root / "corpus" / "pilot-v2" / "manifest.json", CORPUS_MANIFEST
    )


def test_an_unprojected_unlinked_version_is_named(
    imported: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    earlier = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(imported))],
    )
    reseal(earlier.manifest_path, schema_version=1)

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream_of(imported))],
    )

    assert built.status == "built"
    assert built.near_duplicates.to_record()["not_compared"] == [
        {"corpus_id": "pilot-v1", "reason": OTHER_SCHEMA, "stream_ids": []}
    ]


def test_an_unreadable_corpus_directory_is_named_and_the_build_stands(
    imported: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(imported))],
    )
    corpus = data_root / "corpus"
    corpus.chmod(0o300)
    try:
        built = build_corpus(
            write_grouped_corpus(
                [single_group("held-out", "locked", stream_of(imported))], corpus_id="pilot-v2"
            ),
            data_root,
        )
    finally:
        corpus.chmod(0o755)

    assert built.status == "built"
    assert built.near_duplicates.to_record()["scan"] == UNREADABLE
    assert "pairs" not in built.near_duplicates.to_record()
    assert "near_duplicates" not in read_sealed(built.manifest_path, CORPUS_MANIFEST)


def test_a_directory_without_a_manifest_is_not_an_unlinked_placement(
    imported: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    (data_root / "corpus" / "notes").mkdir(parents=True)

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(imported))],
    )

    assert built.unlinked.when_present() == {}
    assert built.near_duplicates.to_record()["not_compared"] == [
        {"corpus_id": "notes", "reason": UNREADABLE, "stream_ids": []}
    ]
