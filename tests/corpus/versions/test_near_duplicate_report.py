"""Windows the build report names, and the ones it leaves out."""

from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult
from ss_track.corpus.versions.near_duplicates import report_near_duplicates
from tests.corpus.conftest import reseal


def _stream(
    imported: ImportResult, stream_id: str, group_id: str, end_frame: int
) -> dict[str, object]:
    return {
        "stream_id": stream_id,
        "group_id": group_id,
        "split": "development",
        "source_sha256": imported.source_sha256,
        "selection": {"start_frame": 0, "end_frame": end_frame},
    }


def test_a_copy_in_the_same_group_is_not_paired_with_its_neighbour(
    imported: ImportResult, data_root: Path
) -> None:
    report = report_near_duplicates(
        "pilot-v1",
        [
            _stream(imported, "left", "site-a", imported.frame_count),
            _stream(imported, "right", "site-a", imported.frame_count),
            _stream(imported, "other", "held-out", imported.frame_count),
        ],
        [],
        data_root,
        lambda _corpus_id: {},
    )

    pairs = report.to_record()["pairs"]
    assert isinstance(pairs, list)
    paired = {tuple(item["stream_id"] for item in pair["streams"]) for pair in pairs}
    assert paired == {("left", "other"), ("other", "right")}


def test_a_predecessor_without_a_readable_window_is_named(
    imported: ImportResult, data_root: Path
) -> None:
    def load(corpus_id: str) -> dict[str, object]:
        if corpus_id == "no-window":
            return {"streams": [{"stream_id": "old", "group_id": "held-out"}]}
        raise CorpusRefusal(RefusalCode.RECORD_TAMPERED, "unreadable")

    report = report_near_duplicates(
        "pilot-v1",
        [_stream(imported, "now", "site-a", 1)],
        [
            {"corpus_id": "unreadable-other", "streams": None},
            {"corpus_id": "unreadable-same", "streams": [{"stream_id": "x", "group_id": "site-a"}]},
            {"corpus_id": "no-window"},
        ],
        data_root,
        load,
    )

    assert report.to_record()["not_compared"] == [
        {"corpus_id": "unreadable-other", "reason": "window_unknown", "stream_ids": []},
        {"corpus_id": "no-window", "reason": "window_unknown", "stream_ids": ["old"]},
    ]


def test_a_source_that_cannot_supply_its_samples_is_named(
    imported: ImportResult, data_root: Path
) -> None:
    past_the_end = report_near_duplicates(
        "pilot-v1",
        [
            _stream(imported, "a", "site-a", 10_000),
            _stream(imported, "b", "held-out", 10_000),
        ],
        [],
        data_root,
        lambda _corpus_id: {},
    )
    reseal(imported.manifest_path, sequence="broken")
    broken = report_near_duplicates(
        "pilot-v1",
        [
            _stream(imported, "a", "site-a", imported.frame_count),
            _stream(imported, "b", "held-out", imported.frame_count),
        ],
        [],
        data_root,
        lambda _corpus_id: {},
    )

    named = {"corpus_id": "pilot-v1", "reason": "source_unreadable", "stream_ids": ["a", "b"]}
    assert past_the_end.to_record()["not_compared"] == [named]
    assert broken.to_record()["not_compared"] == [named]


def test_an_empty_window_is_not_a_near_duplicate(imported: ImportResult, data_root: Path) -> None:
    report = report_near_duplicates(
        "pilot-v1",
        [_stream(imported, "a", "site-a", 0), _stream(imported, "b", "held-out", 0)],
        [],
        data_root,
        lambda _corpus_id: {},
    )
    assert report.when_present() == {}
