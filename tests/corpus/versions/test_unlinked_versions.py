"""A build lists sources placed elsewhere by versions no declaration links, and refuses nothing."""

import logging
import shutil
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK
from ss_track.corpus import ImportResult, build_corpus
from ss_track.corpus.versions.scan import UNREADABLE
from tests.corpus.conftest import (
    WriteCorpus,
    encounter_of,
    group_of,
    last_record,
    single_group,
    stream_of,
)
from tests.corpus.versions._lineage_build import build_version
from tests.corpus.versions._unlinked import place, plant


def _order(item: dict[str, object]) -> tuple[str, str]:
    other = item["from"]
    source = item["source_sha256"]
    assert isinstance(other, dict)
    name = other["corpus_id"]
    assert isinstance(source, str) and isinstance(name, str)
    return source, name


def _both(
    first: ImportResult, second: ImportResult, group: str, split: str
) -> list[dict[str, object]]:
    encounter = encounter_of(
        "enc", stream_of(first, stream_id="a"), stream_of(second, stream_id="b")
    )
    return [group_of(group, split, encounter)]


def test_an_unlinked_version_placing_a_source_in_locked_is_listed_and_builds(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )

    built = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [single_group("held-out", "locked", stream)]
    )

    assert built.status == "built"
    assert built.to_record()["lineage"] == {"status": "no_lineage"}
    assert built.unlinked.to_record() == {
        "placements": [
            place(first, "pilot-v1", "site-a", "development", "pilot-v2", "held-out", "locked")
        ]
    }


def test_a_sibling_branch_placing_a_source_in_locked_is_listed_and_builds(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    shared = single_group("site-b", "development", stream_of(second, stream_id="shared"))
    moved = stream_of(first, stream_id="moved")
    build_version(write_grouped_corpus, data_root, "pilot-root", [shared])
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-left",
        [shared, single_group("site-a", "development", moved)],
        supersedes="pilot-root",
    )

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-right",
        [shared, single_group("held-out", "locked", moved)],
        supersedes="pilot-root",
    )

    assert built.status == "built"
    assert built.to_record()["lineage"]["status"] == "linked"  # type: ignore[index]
    assert built.unlinked.to_record() == {
        "placements": [
            place(first, "pilot-left", "site-a", "development", "pilot-right", "held-out", "locked")
        ]
    }


def test_one_state_lists_every_displaced_source_in_one_order(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    build_version(
        write_grouped_corpus, data_root, "beta", _both(first, second, "site-a", "calibration")
    )
    build_version(
        write_grouped_corpus, data_root, "alpha", _both(first, second, "site-a", "development")
    )

    built = build_version(
        write_grouped_corpus, data_root, "pilot", _both(first, second, "held-out", "locked")
    )

    expected = [
        place(source, version, "site-a", split, "pilot", "held-out", "locked")
        for source in (first, second)
        for version, split in (("alpha", "development"), ("beta", "calibration"))
    ]
    placements = built.unlinked.to_record()["placements"]
    assert placements == sorted(expected, key=_order)


def test_a_version_in_the_declared_chain_is_never_listed(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    same = [single_group("site-a", "development", stream)]
    build_version(write_grouped_corpus, data_root, "pilot-v1", same)
    build_version(write_grouped_corpus, data_root, "pilot-v2", same, supersedes="pilot-v1")
    build_version(
        write_grouped_corpus, data_root, "pilot-other", [single_group("held-out", "locked", stream)]
    )

    declared = write_grouped_corpus(same, corpus_id="pilot-v2", supersedes="pilot-v1")
    built = build_corpus(declared, data_root)

    assert built.status == "unchanged"
    assert built.unlinked.to_record() == {
        "placements": [
            place(first, "pilot-other", "held-out", "locked", "pilot-v2", "site-a", "development")
        ]
    }


def test_the_same_placement_and_another_groups_new_source_are_not_listed(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    stream = stream_of(first)
    build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )

    same = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [single_group("site-a", "development", stream)]
    )
    other_source = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v3",
        [single_group("site-a", "locked", stream_of(second))],
    )

    assert same.status == "built" and same.unlinked.to_record() == {}
    assert other_source.status == "built" and other_source.unlinked.to_record() == {}


def test_a_source_moved_to_another_group_in_one_split_is_listed(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )

    built = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [single_group("site-b", "development", stream)]
    )

    assert built.unlinked.to_record()["placements"] == [
        place(first, "pilot-v1", "site-a", "development", "pilot-v2", "site-b", "development")
    ]


def test_the_listing_is_not_sealed_and_a_repeat_matches(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    declared = write_grouped_corpus(
        [single_group("held-out", "locked", stream)], corpus_id="pilot-v2"
    )
    declaration = declared.read_text(encoding="utf-8")
    first_build = build_corpus(declared, data_root)
    sealed = first_build.manifest_path.read_bytes()
    build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    declared.write_text(declaration, encoding="utf-8")

    again = build_corpus(declared, data_root)
    repeated = build_corpus(declared, data_root)

    assert first_build.status == "built"
    assert first_build.unlinked.to_record() == {}
    assert (again.status, repeated.status) == ("unchanged", "unchanged")
    assert again.manifest_path.read_bytes() == sealed
    assert again.manifest_sha256 == first_build.manifest_sha256
    assert again.unlinked == repeated.unlinked
    assert again.unlinked.to_record()["placements"] == [
        place(first, "pilot-v1", "site-a", "development", "pilot-v2", "held-out", "locked")
    ]


def test_a_manifest_outside_the_corpus_directory_is_not_listed(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    earlier = build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    outside = data_root / "other" / "pilot-v1"
    outside.parent.mkdir()
    shutil.move(earlier.manifest_path.parent, outside)

    built = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [single_group("held-out", "locked", stream)]
    )

    assert built.unlinked.to_record() == {}


def test_the_command_lists_a_displaced_source_and_an_unreadable_manifest(
    first: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_root))
    caplog.set_level(logging.INFO)
    stream = stream_of(first)
    v1 = write_grouped_corpus([single_group("site-a", "development", stream)], corpus_id="pilot-v1")
    assert main(["corpus", "build", "--manifest", str(v1)]) == EXIT_OK
    plant(data_root, "broken", "{")
    v2 = write_grouped_corpus([single_group("held-out", "locked", stream)], corpus_id="pilot-v2")

    assert main(["corpus", "build", "--manifest", str(v2)]) == EXIT_OK

    reported = last_record(caplog)
    assert reported["status"] == "built"
    assert reported["unlinked"] == {
        "not_compared": [{"corpus_id": "broken", "reason": UNREADABLE}],
        "placements": [
            place(first, "pilot-v1", "site-a", "development", "pilot-v2", "held-out", "locked")
        ],
    }
