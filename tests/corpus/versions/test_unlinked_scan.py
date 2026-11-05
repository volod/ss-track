"""A build names every corpus manifest it cannot compare, and still succeeds."""

import json
from pathlib import Path

import pytest

from ss_track.corpus import ImportResult
from ss_track.corpus.records.projections import OTHER_SCHEMA
from ss_track.corpus.versions.unlinked import UNREADABLE
from tests.corpus.conftest import WriteCorpus, reseal, single_group, stream_of
from tests.corpus.versions._lineage_build import build_version
from tests.corpus.versions._unlinked import place, plant


@pytest.mark.parametrize("major", [1, 4, 1.0], ids=["older", "newer", "unstated"])
def test_an_unprojected_predecessor_stays_on_lineage_and_is_not_listed(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path, major: object
) -> None:
    stream = stream_of(first)
    earlier = build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    reseal(earlier.manifest_path, schema_version=major)

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream)],
        supersedes="pilot-v1",
    )

    lineage = built.to_record()["lineage"]
    assert isinstance(lineage, dict)
    assert lineage["not_compared"] == [
        {"corpus_id": "pilot-v1", "reason": OTHER_SCHEMA, "stream_ids": []}
    ]
    assert built.unlinked.to_record() == {}


@pytest.mark.parametrize("major", [1, 4], ids=["older", "newer"])
def test_a_major_with_no_projection_is_named_and_not_compared(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path, major: int
) -> None:
    stream = stream_of(first)
    earlier = build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    reseal(earlier.manifest_path, schema_version=major)

    built = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [single_group("held-out", "locked", stream)]
    )

    assert built.status == "built"
    assert built.unlinked.to_record() == {
        "not_compared": [{"corpus_id": "pilot-v1", "reason": OTHER_SCHEMA}]
    }


def test_a_projected_older_major_is_compared(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    earlier = build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    reseal(earlier.manifest_path, schema_version=2)

    built = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [single_group("held-out", "locked", stream)]
    )

    assert built.unlinked.to_record() == {
        "placements": [
            place(first, "pilot-v1", "site-a", "development", "pilot-v2", "held-out", "locked")
        ]
    }


@pytest.mark.parametrize("damage", ["json", "seal", "shape", "denied"])
def test_an_unreadable_manifest_is_named_and_the_build_succeeds(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path, damage: str
) -> None:
    stream = stream_of(first)
    locked = [single_group("held-out", "locked", stream)]
    if damage == "json":
        plant(data_root, "a-broken", "{")
        plant(data_root, "m-broken", "not json")
        expected = [
            {"corpus_id": "a-broken", "reason": UNREADABLE},
            {"corpus_id": "m-broken", "reason": UNREADABLE},
        ]
        built = build_version(write_grouped_corpus, data_root, "pilot-v2", locked)
    else:
        earlier = build_version(
            write_grouped_corpus,
            data_root,
            "broken",
            [single_group("site-a", "development", stream)],
        )
        path = earlier.manifest_path
        if damage == "seal":
            record = json.loads(path.read_text(encoding="ascii"))
            record["manifest_sha256"] = "0" * 64
            path.chmod(0o644)
            path.write_text(json.dumps(record), encoding="ascii")
        elif damage == "denied":
            path.chmod(0)
        else:
            reseal(path, streams=[{}])
        expected = [{"corpus_id": "broken", "reason": UNREADABLE}]
        try:
            built = build_version(write_grouped_corpus, data_root, "pilot-v2", locked)
        finally:
            if damage == "denied":
                path.chmod(0o644)

    assert built.status == "built"
    assert built.unlinked.to_record() == {"not_compared": expected}
