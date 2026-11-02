import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus
from ss_track.corpus.sealed import read_sealed
from tests.corpus.conftest import WriteCorpus, encounter_of, group_of, stream_of

_CORPUS_KIND = "ss-track.corpus-manifest"
_HEAD = {"start_frame": 0, "end_frame": 4}
_TAIL = {"start_frame": 4, "end_frame": 8}
type Group = dict[str, object]


def _refused(
    write: WriteCorpus,
    groups: Sequence[Group],
    data_root: Path,
    code: RefusalCode,
    **overrides: object,
) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write(list(groups), **overrides), data_root)
    assert caught.value.code is code
    assert not (data_root / "corpus").exists()
    return caught.value


def _single(group_id: str, split: str, encounter: str, stream: dict[str, object]) -> Group:
    return group_of(group_id, split, encounter_of(encounter, stream))


def _streams(path: Path) -> dict[str, dict[str, object]]:
    records = read_sealed(path, _CORPUS_KIND)["streams"]
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
        _single("site-b", "calibration", "enc02", stream_of(third, stream_id="enc02-cam0")),
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
            encounter_of("enc01", stream_of(first, stream_id="a", selection=_HEAD)),
            encounter_of("enc02", stream_of(first, stream_id="b", selection=_TAIL)),
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
        _single("site-a", split_a, "enc01", stream_of(first, stream_id="a")),
        _single("site-b", split_b, "enc01", stream_of(second, stream_id="b")),
    ]

    refusal = _refused(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {"encounter_id": "enc01", "splits": sorted((split_a, split_b))}


def test_a_stream_cannot_cross_a_split(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    groups = [
        _single("site-a", "development", "enc01", stream_of(first)),
        _single("site-b", "locked", "enc02", stream_of(second)),
    ]

    refusal = _refused(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {"stream_id": "one", "splits": ["development", "locked"]}


def test_a_group_cannot_cross_a_split(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    groups = [
        _single("site-a", "development", "enc01", stream_of(first, stream_id="a")),
        _single("site-a", "calibration", "enc02", stream_of(second, stream_id="b")),
    ]

    refusal = _refused(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {"group_id": "site-a", "splits": ["calibration", "development"]}


def test_a_recording_cannot_reach_two_splits_under_two_names(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [
        _single("site-a", "development", "enc01", stream_of(first, stream_id="a", selection=_HEAD)),
        _single("site-b", "locked", "enc02", stream_of(first, stream_id="b", selection=_TAIL)),
    ]

    refusal = _refused(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details == {
        "source_sha256": first.source_sha256,
        "groups": ["site-a", "site-b"],
        "splits": ["development", "locked"],
    }


def test_two_groups_that_share_a_recording_are_not_independent(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [
        _single("site-a", "development", "enc01", stream_of(first, stream_id="a", selection=_HEAD)),
        _single("site-b", "development", "enc02", stream_of(first, stream_id="b", selection=_TAIL)),
    ]

    refusal = _refused(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

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
        _single(g1, "development", e1, stream_of(first, stream_id=s1)),
        _single(g2, "development", e2, stream_of(second, stream_id=s2)),
    ]

    refusal = _refused(write_grouped_corpus, groups, data_root, RefusalCode.MANIFEST_INVALID)

    assert "repeats" in refusal.message


@pytest.mark.parametrize(
    ("window_a", "window_b", "first_shared"),
    [
        pytest.param(_HEAD, _HEAD, 0, id="identical"),
        pytest.param(_HEAD, {"start_frame": 3, "end_frame": 8}, 3, id="one-frame"),
        pytest.param(
            {"start_frame": 0, "end_frame": 8},
            {"start_frame": 2, "end_frame": 3},
            2,
            id="contained",
        ),
        pytest.param(None, _TAIL, 4, id="absent-selection-means-all-frames"),
    ],
)
def test_two_streams_cannot_share_a_frame(
    first: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    window_a: dict[str, int] | None,
    window_b: dict[str, int],
    first_shared: int,
) -> None:
    whole = {} if window_a is None else {"selection": window_a}
    streams = [
        stream_of(first, stream_id="a", **whole),
        stream_of(first, stream_id="b", selection=window_b),
    ]

    refusal = _refused(write_corpus, streams, data_root, RefusalCode.STREAM_OVERLAP)

    assert refusal.details == {
        "source_sha256": first.source_sha256,
        "streams": ["a", "b"],
        "first_shared_frame": first_shared,
    }


@pytest.mark.parametrize(
    ("window_a", "window_b"),
    [
        pytest.param(_HEAD, _TAIL, id="names-follow-frames"),
        pytest.param(_TAIL, _HEAD, id="names-oppose-frames"),
    ],
)
def test_adjacent_windows_share_no_frame(
    first: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    window_a: dict[str, int],
    window_b: dict[str, int],
) -> None:
    streams = [
        stream_of(first, stream_id="a", selection=window_a),
        stream_of(first, stream_id="b", selection=window_b),
    ]

    assert build_corpus(write_corpus(streams), data_root).stream_count == 2


def test_declaration_order_at_every_level_does_not_change_the_corpus_hash(
    first: ImportResult,
    second: ImportResult,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    cam0 = stream_of(first, stream_id="cam0")
    cam1 = stream_of(second, stream_id="cam1")
    other = _single("site-b", "locked", "enc02", stream_of(third, stream_id="cam2"))

    forward = [group_of("site-a", "development", encounter_of("enc01", cam0, cam1)), other]
    backward = [other, group_of("site-a", "development", encounter_of("enc01", cam1, cam0))]

    one = build_corpus(write_grouped_corpus(forward), data_root)
    two = build_corpus(write_grouped_corpus(backward), data_root)

    assert one.manifest_sha256 == two.manifest_sha256


def test_moving_a_stream_to_another_split_is_a_new_corpus_version(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    build_corpus(write_grouped_corpus([_single("g", "development", "e", stream)]), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_grouped_corpus([_single("g", "locked", "e", stream)]), data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def test_a_built_manifest_states_each_membership_once_per_stream(
    first: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    result = build_corpus(write_corpus([stream_of(first)]), data_root)

    record = json.loads(result.manifest_path.read_text(encoding="ascii"))

    assert "sequences" not in record
    assert record["schema_version"] == 3
    assert [stream["modality"] for stream in record["streams"]] == ["camera"]
