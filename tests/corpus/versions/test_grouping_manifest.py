"""What a grouped corpus manifest records: frame windows, an order-free hash and each membership."""

import json
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus
from tests.corpus.conftest import HEAD, TAIL, WriteCorpus, encounter_of, group_of, stream_of
from tests.corpus.versions._grouping import encounter_group, refused_grouping


@pytest.mark.parametrize(
    ("window_a", "window_b", "first_shared"),
    [
        pytest.param(HEAD, HEAD, 0, id="identical"),
        pytest.param(HEAD, {"start_frame": 3, "end_frame": 8}, 3, id="one-frame"),
        pytest.param(
            {"start_frame": 0, "end_frame": 8},
            {"start_frame": 2, "end_frame": 3},
            2,
            id="contained",
        ),
        pytest.param(None, TAIL, 4, id="absent-selection-means-all-frames"),
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

    refusal = refused_grouping(write_corpus, streams, data_root, RefusalCode.STREAM_OVERLAP)

    assert refusal.details == {
        "source_sha256": first.source_sha256,
        "streams": ["a", "b"],
        "first_shared_frame": first_shared,
    }


@pytest.mark.parametrize(
    ("window_a", "window_b"),
    [
        pytest.param(HEAD, TAIL, id="names-follow-frames"),
        pytest.param(TAIL, HEAD, id="names-oppose-frames"),
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
    other = encounter_group("site-b", "locked", "enc02", stream_of(third, stream_id="cam2"))

    forward = [group_of("site-a", "development", encounter_of("enc01", cam0, cam1)), other]
    backward = [other, group_of("site-a", "development", encounter_of("enc01", cam1, cam0))]

    one = build_corpus(write_grouped_corpus(forward), data_root)
    two = build_corpus(write_grouped_corpus(backward), data_root)

    assert one.manifest_sha256 == two.manifest_sha256


def test_moving_a_stream_to_another_split_is_a_new_corpus_version(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(first)
    build_corpus(
        write_grouped_corpus([encounter_group("g", "development", "e", stream)]), data_root
    )

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_grouped_corpus([encounter_group("g", "locked", "e", stream)]), data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def test_a_built_manifest_states_each_membership_once_per_stream(
    first: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    result = build_corpus(write_corpus([stream_of(first)]), data_root)

    record = json.loads(result.manifest_path.read_text(encoding="ascii"))

    assert "sequences" not in record
    assert record["schema_version"] == 3
    assert [stream["modality"] for stream in record["streams"]] == ["camera"]
