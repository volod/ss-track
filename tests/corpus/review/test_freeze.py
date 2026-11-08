"""`corpus freeze` seals the version a review makes, and refuses what the review cannot vouch for."""

from pathlib import Path
from typing import Any

import pytest

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import (
    ImportResult,
    import_source,
)
from ss_track.corpus.records.kinds import CORPUS_FREEZE
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.review.freeze import freeze_corpus
from ss_track.corpus.storage.layout import freeze_path
from tests.corpus.conftest import WriteRecording, last_record
from tests.corpus.review._review import (
    FROZEN,
    POOL,
    STOCK_DECISIONS,
    review_links,
    stage_pool,
    staged,
    write_review,
)


def test_freezing_seals_membership_exclusions_and_decision_provenance(
    pool: tuple[ImportResult, ...], data_root: Path, media: Path
) -> None:
    review = staged(media, data_root)

    result = freeze_corpus(FROZEN, review, review_links(data_root), data_root)

    record: Any = read_sealed(freeze_path(data_root, FROZEN), CORPUS_FREEZE)
    assert result.status == "frozen" and record == result.record
    assert record["label_revision"] is None
    assert record["discovery"]["run_id"] == "discovery-1"
    assert record["discovery"]["corpus_id"] == POOL
    assert record["links"]["status"] == "clear"
    assert record["review"]["reviewer"] == "site lead"
    assert (record["review"]["offered_count"], record["review"]["decision_count"]) == (6, 4)
    joined, single = record["members"]
    assert (joined["stream_id"], joined["window"]) == (
        "one.0-16",
        {"start_frame": 0, "end_frame": 16},
    )
    assert [(c["candidate_id"], c["observation"]) for c in joined["candidates"]] == [
        ("pool-000", "target_present"),
        ("pool-001", "unknown"),
    ]
    assert (single["split"], single["candidates"][0]["observation"]) == ("calibration", "confuser")
    (excluded,) = record["exclusions"]
    assert (excluded["candidate_id"], excluded["reason"], excluded["note"]) == (
        "pool-002",
        "quality",
        "blurred",
    )
    assert [(i["stream_id"], i["candidate_id"]) for i in record["unreviewed"]] == [
        ("two", "pool-000"),
        ("two", "pool-001"),
    ]
    assert record["withheld"] == [
        {"stream_id": "three", "reason": "locked_without_policy", "count": 3}
    ]
    sources = record["sources"]
    assert [source["source_sha256"] for source in sources] == sorted(
        [pool[0].source_sha256, pool[1].source_sha256]
    )
    assert {(source["group_id"], source["split"]) for source in sources} == {
        ("site-a", "development"),
        ("site-b", "calibration"),
    }
    assert all(source["rights"]["retain_until"] is None for source in record["sources"])
    assert record["superseded"] == {"compared_versions": [], "not_compared": []}


def test_no_observation_reaches_the_frozen_manifest(
    pool: Any, data_root: Path, media: Path
) -> None:
    review = staged(media, data_root)
    freeze_corpus(FROZEN, review, review_links(data_root), data_root)

    manifest = (data_root / "corpus" / FROZEN / "manifest.json").read_text(encoding="ascii")

    for word in ("observation", "target_present", "confuser", "unreviewed", "label"):
        assert word not in manifest


def test_a_retry_is_unchanged_and_other_decisions_for_a_frozen_version_conflict(
    pool: Any, data_root: Path, media: Path
) -> None:
    review = staged(media, data_root)
    links = review_links(data_root)
    first = freeze_corpus(FROZEN, review, links, data_root)
    again = freeze_corpus(FROZEN, review, links, data_root)
    other = write_review(
        media / "other.yaml", *[item | {"note": "seen again"} for item in STOCK_DECISIONS]
    )

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus(FROZEN, other, links, data_root)

    assert again.status == "unchanged"
    assert again.to_record() == first.to_record() | {"status": "unchanged"}
    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def _replay(media: Path, data_root: Path) -> Any:
    review = staged(media, data_root)
    return freeze_corpus(FROZEN, review, review_links(data_root), data_root).record


def test_replaying_the_review_on_another_data_root_gives_the_same_hashes(
    pool: Any, data_root: Path, media: Path, tmp_path: Path, write_recording: WriteRecording
) -> None:
    record = _replay(media, data_root)
    other_root = tmp_path / "replay"
    # The same media bytes: encoding a clip again would give other bytes and other sources.
    imported = [
        import_source(write_recording(f"clip-{extra}.mkv"), other_root) for extra in (2, 4, 6)
    ]
    stage_pool(media, other_root, *imported)
    (media / f"{FROZEN}.yaml").unlink()

    replayed = _replay(media, other_root)

    assert replayed == record


def test_the_command_reports_the_frozen_version(
    pool: Any, cli_root: Path, media: Path, caplog: Any
) -> None:
    review = staged(media, cli_root)
    links = review_links(cli_root)

    status = main(
        ["corpus", "freeze", "--corpus", FROZEN, "--review", str(review), "--links", links]
    )

    record: Any = last_record(caplog)
    assert status == 0 and record["status"] == "frozen"
    assert record["review"]["included"] == 3
    assert record["manifest_path"] == str(freeze_path(cli_root, FROZEN))


def test_evaluation_reads_freeze_observations_like_the_review(
    pool: Any, data_root: Path, media: Path
) -> None:
    from ss_track.corpus.evaluation.inputs import read_evidence

    review = staged(media, data_root)
    freeze_corpus(FROZEN, review, review_links(data_root), data_root)
    from_review = read_evidence(data_root, "discovery-1", review, None)
    from_freeze = read_evidence(data_root, "discovery-1", None, FROZEN)
    assert from_review.observations == from_freeze.observations
    assert from_freeze.observations[("one", "pool-001")] == "unknown"
    assert ("two", "pool-000") not in from_freeze.observations
