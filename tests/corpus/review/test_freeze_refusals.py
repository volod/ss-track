"""`corpus freeze` refuses what a review cannot vouch for: another version, links, terms or record."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult, amend_source_terms, build_corpus, stage_corpus
from ss_track.corpus.review.export import export_review
from ss_track.corpus.review.freeze import freeze_corpus
from ss_track.corpus.storage.layout import freeze_path
from tests.corpus._amending import rights_with
from tests.corpus.conftest import WriteRecording, import_clip, reseal
from tests.corpus.links._links import decided, write_decisions
from tests.corpus.review._review import (
    FROZEN,
    POOL,
    export_stock,
    include,
    review_links,
    stage_pool,
    staged,
    write_review,
)


def test_a_version_built_from_another_declaration_is_refused(
    pool: Any, data_root: Path, media: Path
) -> None:
    out, _ = export_stock(media, data_root)
    edited = out.read_text(encoding="ascii").replace("end_frame: 16", "end_frame: 12")
    out.write_text(edited, encoding="ascii")
    build_corpus(out, data_root)
    stage_corpus(FROZEN, data_root)

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus(FROZEN, media / "review.yaml", review_links(data_root), data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert caught.value.details["missing"] == []
    assert caught.value.details["changed"] == ["one.0-16"]
    assert not freeze_path(data_root, FROZEN).exists()


def test_a_link_review_of_another_version_is_refused(
    pool: Any, data_root: Path, media: Path
) -> None:
    review = staged(media, data_root)

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus(FROZEN, review, review_links(data_root, POOL, "pool-links"), data_root)

    assert caught.value.code is RefusalCode.FRAME_SET_MISMATCH


def _lookalikes(media: Path, data_root: Path) -> Path:
    """Include windows of one and two that show the same pattern, in two splits."""
    review = write_review(
        media / "review.yaml", include("one", "pool-000"), include("two", "pool-000")
    )
    out = media / "lookalike.yaml"
    export_review(review, FROZEN, out, data_root)
    build_corpus(out, data_root)
    stage_corpus(FROZEN, data_root)
    return review


def test_an_undecided_link_across_splits_refuses_and_a_decision_clears_it(
    pool: tuple[ImportResult, ...], data_root: Path, media: Path
) -> None:
    first, second, _ = pool
    review = _lookalikes(media, data_root)

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus(FROZEN, review, review_links(data_root), data_root)
    decisions = write_decisions(
        media / "decisions.yaml", decided(first.source_sha256, second.source_sha256, "unrelated")
    )
    links = review_links(data_root, run_id="links-2", decisions_path=decisions)
    frozen = freeze_corpus(FROZEN, review, links, data_root)

    assert caught.value.code is RefusalCode.LINKS_UNRESOLVED
    details: Any = caught.value.details
    (link,) = details["links"]
    assert link["cross_split"] is True
    assert frozen.record["links"]["status"] == "clear"


def test_a_related_recording_a_superseded_version_held_in_another_split_refuses(
    pool: tuple[ImportResult, ...], data_root: Path, media: Path
) -> None:
    first, second, _ = pool
    review = write_review(media / "review.yaml", include("one", "pool-000"))
    out = media / "v2.yaml"
    export_review(review, "frozen-v2", out, data_root, supersedes=POOL)
    build_corpus(out, data_root)
    stage_corpus("frozen-v2", data_root)
    related = write_decisions(
        media / "related.yaml", decided(first.source_sha256, second.source_sha256, "related")
    )
    clear = freeze_corpus("frozen-v2", review, review_links(data_root, "frozen-v2"), data_root)
    links = review_links(data_root, "frozen-v2", "links-2", decisions_path=related)

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus("frozen-v2", review, links, data_root)

    assert clear.record["superseded"] == {"compared_versions": [POOL], "not_compared": []}
    assert caught.value.code is RefusalCode.SPLIT_LEAKAGE
    details: Any = caught.value.details
    (apart,) = details["related_apart"]
    assert apart["source_sha256"] == first.source_sha256
    assert apart["related_place"] == {
        "corpus_id": POOL,
        "group_id": "site-b",
        "split": "calibration",
    }


def test_terms_that_no_longer_hold_refuse_the_freeze(
    pool: Any, data_root: Path, media: Path, write_recording: WriteRecording
) -> None:
    review = staged(media, data_root)
    links = review_links(data_root)
    amend_source_terms(
        write_recording("clip-2.mkv", rights=rights_with(sharing="public")), data_root
    )

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus(FROZEN, review, links, data_root)

    assert caught.value.code is RefusalCode.SOURCE_RECORD_CHANGED


def test_retention_that_ended_refuses_the_freeze(
    media: Path, data_root: Path, write_recording: WriteRecording, third: ImportResult
) -> None:
    ending = rights_with(retain_until="2026-12-31")
    first = import_clip(media, write_recording, data_root, 2, rights=ending)
    second = import_clip(media, write_recording, data_root, 4, rights=ending)
    stage_pool(media, data_root, first, second, third)
    review = staged(media, data_root, today=date(2026, 12, 1))

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus(FROZEN, review, review_links(data_root), data_root, today=date(2027, 1, 1))

    assert caught.value.code is RefusalCode.RETENTION_EXPIRED


def _shorter_member(record: Any) -> dict[str, Any]:
    members = json.loads(json.dumps(record["members"]))
    members[0]["window"]["end_frame"] = 12
    return {"members": members}


def _more_offered(record: Any) -> dict[str, Any]:
    return {"review": record["review"] | {"offered_count": 7}}


@pytest.mark.parametrize("forge", [_shorter_member, _more_offered])
def test_a_forged_freeze_record_is_refused(
    pool: Any, data_root: Path, media: Path, forge: Any
) -> None:
    review = staged(media, data_root)
    links = review_links(data_root)
    record: Any = freeze_corpus(FROZEN, review, links, data_root).record
    reseal(freeze_path(data_root, FROZEN), **forge(record))

    with pytest.raises(CorpusRefusal) as caught:
        freeze_corpus(FROZEN, review, links, data_root)

    assert caught.value.code is RefusalCode.RECORD_INVALID
    details: Any = caught.value.details
    assert len(details["findings"]) == 1
