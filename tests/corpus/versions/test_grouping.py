"""Encounter groups and splits: membership is inherited, and nothing crosses a split."""

from pathlib import Path

import pytest

from ss_track.corpus import ImportResult, RefusalCode, build_corpus
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.records.sealed import read_sealed
from tests.corpus.conftest import HEAD, TAIL, WriteCorpus, encounter_of, group_of, stream_of
from tests.corpus.versions._grouping import encounter_group, refused_grouping


def _streams(path: Path) -> dict[str, dict[str, object]]:
    records = read_sealed(path, CORPUS_MANIFEST)["streams"]
    assert isinstance(records, list)
    return {str(item["stream_id"]): item for item in records}  # type: ignore[call-overload,index,misc]


def test_every_stream_of_an_encounter_inherits_its_group_and_split(
    first: ImportResult,
    second: ImportResult,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    multi_stream = encounter_of(
        "enc01",
        stream_of(first, stream_id="enc01-cam0"),
        stream_of(second, stream_id="enc01-cam1"),
    )
    groups = [
        group_of("site-a", "development", multi_stream),
        encounter_group("site-b", "calibration", "enc02", stream_of(third, stream_id="enc02-cam0")),
    ]

    result = build_corpus(write_grouped_corpus(groups), data_root)

    streams = _streams(result.manifest_path)
    placed = {
        name: (stream["encounter_id"], stream["group_id"], stream["split"])
        for name, stream in streams.items()
    }
    assert placed == {
        "enc01-cam0": ("enc01", "site-a", "development"),
        "enc01-cam1": ("enc01", "site-a", "development"),
        "enc02-cam0": ("enc02", "site-b", "calibration"),
    }
    assert {split: summary.to_record() for split, summary in result.splits.items()} == {
        "calibration": {
            "group_count": 1,
            "encounter_count": 1,
            "stream_count": 1,
            "generated_case_count": 0,
        },
        "development": {
            "group_count": 1,
            "encounter_count": 1,
            "stream_count": 2,
            "generated_case_count": 0,
        },
    }


def test_a_group_may_hold_several_encounters_of_one_recording(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [
        group_of(
            "long-pass",
            "development",
            encounter_of("enc01", stream_of(first, stream_id="a", selection=HEAD)),
            encounter_of("enc02", stream_of(first, stream_id="b", selection=TAIL)),
        )
    ]

    result = build_corpus(write_grouped_corpus(groups), data_root)

    assert result.splits["development"].encounter_count == 2
    assert result.splits["development"].group_count == 1


@pytest.mark.parametrize(
    ("split_a", "split_b"),
    [
        ("development", "calibration"),
        ("development", "locked"),
        ("calibration", "locked"),
    ],
)
def test_an_encounter_cannot_cross_a_split(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    split_a: str,
    split_b: str,
) -> None:
    groups = [
        encounter_group("site-a", split_a, "enc01", stream_of(first, stream_id="a")),
        encounter_group("site-b", split_b, "enc01", stream_of(second, stream_id="b")),
    ]

    refusal = refused_grouping(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {"encounter_id": "enc01", "splits": sorted((split_a, split_b))}


def test_a_stream_cannot_cross_a_split(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    groups = [
        encounter_group("site-a", "development", "enc01", stream_of(first)),
        encounter_group("site-b", "locked", "enc02", stream_of(second)),
    ]

    refusal = refused_grouping(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {"stream_id": "one", "splits": ["development", "locked"]}


def test_a_group_cannot_cross_a_split(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    groups = [
        encounter_group("site-a", "development", "enc01", stream_of(first, stream_id="a")),
        encounter_group("site-a", "calibration", "enc02", stream_of(second, stream_id="b")),
    ]

    refusal = refused_grouping(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {"group_id": "site-a", "splits": ["calibration", "development"]}


def test_a_recording_cannot_reach_two_splits_under_two_names(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [
        encounter_group(
            "site-a", "development", "enc01", stream_of(first, stream_id="a", selection=HEAD)
        ),
        encounter_group(
            "site-b", "locked", "enc02", stream_of(first, stream_id="b", selection=TAIL)
        ),
    ]

    refusal = refused_grouping(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {
        "source_sha256": first.source_sha256,
        "groups": ["site-a", "site-b"],
        "splits": ["development", "locked"],
    }


def test_two_groups_that_share_a_recording_are_not_independent(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [
        encounter_group(
            "site-a", "development", "enc01", stream_of(first, stream_id="a", selection=HEAD)
        ),
        encounter_group(
            "site-b", "development", "enc02", stream_of(first, stream_id="b", selection=TAIL)
        ),
    ]

    refusal = refused_grouping(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details["splits"] == ["development"]


@pytest.mark.parametrize(
    "field_groups",
    [
        pytest.param(("g", "g", "e1", "e2", "s1", "s2"), id="group"),
        pytest.param(("g1", "g2", "e", "e", "s1", "s2"), id="encounter"),
        pytest.param(("g1", "g2", "e1", "e2", "s", "s"), id="stream"),
    ],
)
def test_an_identifier_repeated_inside_one_split_is_a_malformed_declaration(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    field_groups: tuple[str, ...],
) -> None:
    g1, g2, e1, e2, s1, s2 = field_groups
    groups = [
        encounter_group(g1, "development", e1, stream_of(first, stream_id=s1)),
        encounter_group(g2, "development", e2, stream_of(second, stream_id=s2)),
    ]

    refusal = refused_grouping(
        write_grouped_corpus, groups, data_root, RefusalCode.MANIFEST_INVALID
    )

    assert "repeats" in refusal.message
