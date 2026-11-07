"""`discover links` over staged versions: known leakage refuses, uncertain links are written."""

import json
from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult, build_corpus, import_source, stage_corpus
from ss_track.corpus.links.records import read_links
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.records.kinds import CORPUS_LINKS
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.storage.layout import discovery_run_directory, frame_set_path
from tests.corpus._media import write_clip
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    encounter_of,
    group_of,
    last_record,
    reseal,
    stream_of,
)
from tests.corpus.links._links import decided, write_decisions

CORPUS = "pilot-v1"


def _other_scene(index: int, width: int, height: int) -> bytes:
    """Frames that share nothing with the stock pattern: rows change, not columns."""
    return b"".join(
        bytes(
            value
            for _ in range(width)
            for value in ((y * 9 + index * 13) % 256, 40, (255 - y * 4) % 256)
        )
        for y in range(height)
    )


@pytest.fixture
def unrelated(media: Path, write_recording: WriteRecording, data_root: Path) -> ImportResult:
    write_clip(media / "other.mkv", content=_other_scene)
    return import_source(write_recording("other.mkv"), data_root)


def _single(group_id: str, split: str, result: ImportResult, stream_id: str) -> dict[str, object]:
    return group_of(
        group_id, split, encounter_of(f"enc-{stream_id}", stream_of(result, stream_id=stream_id))
    )


@pytest.fixture
def staged(
    first: ImportResult,
    second: ImportResult,
    unrelated: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> tuple[ImportResult, ImportResult]:
    """A lookalike pair across splits, and an unrelated scene in a third group."""
    groups = [
        _single("site-a", "development", first, "one"),
        _single("held", "locked", second, "two"),
        _single("site-b", "development", unrelated, "other"),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)
    stage_corpus(CORPUS, data_root)
    return first, second


def test_a_lookalike_across_splits_is_written_unresolved_and_an_unrelated_scene_is_not_linked(
    staged: tuple[ImportResult, ImportResult], data_root: Path
) -> None:
    first, second = staged

    result = write_links(LinkRequest("links-1", CORPUS), data_root)

    record: Any = read_sealed(result.path, CORPUS_LINKS)
    assert record["status"] == "unresolved"
    (link,) = record["links"]
    sources = sorted([first.source_sha256, second.source_sha256])
    assert [source["source_sha256"] for source in link["sources"]] == sources
    assert link["cross_split"] is True
    assert [flag["method"] for flag in link["evidence"]] == ["luma-grid-16"]
    assert "decision" not in link
    assert record["shared_frames"] == {
        "min_shared_frames": 8,
        "compared_versions": [],
        "not_compared": [],
    }
    assert result.to_record()["links"] == {
        "status": "unresolved",
        "count": 1,
        "states": [{"status": "unresolved", "count": 1}],
        "unresolved_cross_split": 1,
        "flagged": [{"method": "luma-grid-16", "count": 1}],
        "not_compared": 0,
    }


def test_the_same_review_again_is_unchanged_and_another_under_its_run_id_conflicts(
    staged: tuple[ImportResult, ImportResult], data_root: Path, tmp_path: Path
) -> None:
    first, second = staged
    written = write_links(LinkRequest("links-1", CORPUS), data_root)
    again = write_links(LinkRequest("links-1", CORPUS), data_root)
    decisions = write_decisions(
        tmp_path / "decisions.yaml", decided(first.source_sha256, second.source_sha256, "unrelated")
    )

    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("links-1", CORPUS, decisions_path=decisions), data_root)

    assert (written.status, again.status) == ("written", "unchanged")
    assert again.to_record() == written.to_record() | {"status": "unchanged"}
    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def test_an_unrelated_decision_clears_the_review(
    staged: tuple[ImportResult, ImportResult], data_root: Path, tmp_path: Path
) -> None:
    first, second = staged
    decisions = write_decisions(
        tmp_path / "decisions.yaml",
        decided(second.source_sha256, first.source_sha256, "unrelated", note="other site"),
        decided(first.source_sha256, "e" * 64, "related"),
    )

    result = write_links(LinkRequest("links-2", CORPUS, decisions_path=decisions), data_root)

    record: Any = read_sealed(result.path, CORPUS_LINKS)
    assert record["status"] == "clear"
    assert record["review"] == {"reviewer": "reviewer", "decision_count": 2}
    assert [link["status"] for link in record["links"]] == ["unrelated"]
    assert [item["reason"] for item in record["decisions_outside_links"]] == ["not_in_corpus"]
    summary: Any = result.to_record()["links"]
    assert summary["decisions_outside_links"] == 1


def test_a_related_decision_across_groups_refuses_and_writes_nothing(
    staged: tuple[ImportResult, ImportResult],
    unrelated: ImportResult,
    data_root: Path,
    tmp_path: Path,
) -> None:
    first, _ = staged
    decisions = write_decisions(
        tmp_path / "decisions.yaml",
        decided(first.source_sha256, unrelated.source_sha256, "related", note="one flight"),
    )

    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("links-3", CORPUS, decisions_path=decisions), data_root)

    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    details: Any = caught.value.details
    (link,) = details["links"]
    assert link["cross_split"] is False and link["evidence"] == []
    assert not discovery_run_directory(data_root, "links-3").exists()


def test_a_remux_in_another_group_is_refused_as_known_leakage(
    original: ImportResult,
    copy: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    groups = [
        _single("site-a", "development", original, "original"),
        _single("held", "locked", copy, "copy"),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)
    with pytest.raises(CorpusRefusal):
        stage_corpus(CORPUS, data_root)

    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("links-1", CORPUS), data_root)

    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    assert "shared_runs" in caught.value.details


def test_a_version_never_staged_is_refused(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_grouped_corpus([_single("site-a", "development", first, "one")]), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("links-1", CORPUS), data_root)

    assert caught.value.code is RefusalCode.BUNDLE_NOT_STAGED


def test_a_version_whose_staging_never_finished_is_refused(
    staged: tuple[ImportResult, ImportResult], data_root: Path
) -> None:
    frame_set_path(data_root, CORPUS).unlink()

    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("links-1", CORPUS), data_root)

    assert caught.value.code is RefusalCode.FRAME_SET_NOT_STAGED


@pytest.mark.parametrize("run_id", ["../escape", "Upper"])
def test_a_run_id_that_is_not_an_identifier_is_refused(
    staged: tuple[ImportResult, ImportResult], data_root: Path, run_id: str
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest(run_id, CORPUS), data_root)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_run_id_another_run_holds_conflicts(
    staged: tuple[ImportResult, ImportResult], data_root: Path
) -> None:
    discovery_run_directory(data_root, "discovery-1").mkdir(parents=True)

    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("discovery-1", CORPUS), data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert "another run" in caught.value.message


def test_the_command_reports_the_review(
    staged: tuple[ImportResult, ImportResult],
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    code = main(["discover", "links", "--corpus", CORPUS, "--run-id", "links-1"])

    record: Any = last_record(caplog)
    assert code == 0
    assert record["status"] == "written"
    assert record["links"]["unresolved_cross_split"] == 1
    assert json.loads(Path(str(record["manifest_path"])).read_text())["status"] == "unresolved"


def test_a_written_review_reads_back_and_a_forged_one_is_refused(
    staged: tuple[ImportResult, ImportResult], data_root: Path
) -> None:
    result = write_links(LinkRequest("links-1", CORPUS), data_root)
    record: Any = read_links(data_root, "links-1")
    assert record == read_sealed(result.path, CORPUS_LINKS)

    reseal(result.path, status="clear")

    with pytest.raises(CorpusRefusal) as caught:
        read_links(data_root, "links-1")
    assert caught.value.code is RefusalCode.RECORD_INVALID
    assert caught.value.details["findings"] == ["status is clear against its links"]
    with pytest.raises(CorpusRefusal) as again:
        write_links(LinkRequest("links-1", CORPUS), data_root)
    assert again.value.code is RefusalCode.RECORD_INVALID


@pytest.mark.parametrize(
    ("change", "finding"),
    [
        (
            {"status": "unrelated"},
            [
                "links[0] has status unrelated against its decision",
                "status is unresolved against its links",
            ],
        ),
        ({"cross_split": False}, ["links[0] states cross_split against its splits"]),
    ],
)
def test_a_link_that_breaks_its_rules_is_refused(
    staged: tuple[ImportResult, ImportResult],
    data_root: Path,
    change: dict[str, object],
    finding: list[str],
) -> None:
    result = write_links(LinkRequest("links-1", CORPUS), data_root)
    record: Any = read_sealed(result.path, CORPUS_LINKS)
    links = [record["links"][0] | change]

    reseal(result.path, links=links)

    with pytest.raises(CorpusRefusal) as caught:
        read_links(data_root, "links-1")
    assert caught.value.details["findings"] == finding


def test_a_missing_review_is_refused(data_root: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_links(data_root, "links-9")

    assert caught.value.code is RefusalCode.RECORD_TAMPERED
