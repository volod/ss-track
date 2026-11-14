"""`discover queue` offers a bounded set of windows; `discover export` writes their declaration."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult, amend_source_terms, build_corpus, stage_corpus
from ss_track.corpus.declarations.declaration import load_corpus_declaration
from ss_track.corpus.review.decisions import read_review
from ss_track.corpus.review.export import export_review
from ss_track.corpus.review.template import queue_review
from tests.corpus._amending import rights_with
from tests.corpus.conftest import WriteRecording, import_clip, last_record
from tests.corpus.review._review import (
    FROZEN,
    RUN_ID,
    STOCK_DECISIONS,
    export_stock,
    stage_pool,
    write_review,
)


def test_the_queue_offers_every_sampled_and_selected_window_and_withholds_the_locked_ones(
    pool: Any, data_root: Path
) -> None:
    result = queue_review(RUN_ID, data_root)

    record: Any = result.to_record()
    assert record["status"] == "listed" and record["corpus_id"] == "pilot-v1"
    assert record["queue"]["offered"] == 6
    assert record["queue"]["offers"] == [
        {"offer": "audit_sample", "count": 6},
        {"offer": "selected", "count": 2},
    ]
    assert record["queue"]["withheld"] == [
        {"stream_id": "three", "reason": "locked_without_policy", "count": 3}
    ]
    assert {stream_id for stream_id, _ in result.queue.offered} == {"one", "two"}


def test_the_template_lists_each_offered_window_undecided_and_needs_a_reviewer(
    pool: Any, data_root: Path, media: Path
) -> None:
    template = media / "review.yaml"
    queue_review(RUN_ID, data_root, template)
    text = template.read_text(encoding="ascii")

    with pytest.raises(CorpusRefusal) as blank:
        read_review(template)
    template.write_text(text.replace('reviewer: ""', 'reviewer: "site lead"'), encoding="ascii")
    review = read_review(template)

    assert blank.value.code is RefusalCode.MANIFEST_INVALID
    assert "Withheld: 3 window(s) of three, locked_without_policy." in text
    assert "# frames [16, 24); offered as audit_sample, selected; selection selected" in text
    assert {item.decision for item in review.decisions.values()} == {"unreviewed"}
    assert len(review.decisions) == 6
    with pytest.raises(CorpusRefusal) as empty:
        export_review(template, FROZEN, media / "out.yaml", data_root)
    assert empty.value.code is RefusalCode.MANIFEST_INVALID
    assert "includes no window" in empty.value.message


def test_the_template_never_replaces_a_review_in_progress(
    pool: Any, data_root: Path, media: Path
) -> None:
    template = media / "review.yaml"
    queue_review(RUN_ID, data_root, template)
    queue_review(RUN_ID, data_root, template)  # the same bytes again
    template.write_text("edited", encoding="ascii")

    with pytest.raises(CorpusRefusal) as caught:
        queue_review(RUN_ID, data_root, template)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT
    assert template.read_text(encoding="ascii") == "edited"


def test_the_export_writes_one_declaration_and_the_same_review_again_writes_the_same_bytes(
    pool: Any, data_root: Path, media: Path
) -> None:
    out, first = export_stock(media, data_root)
    written = out.read_bytes()
    _, again = export_stock(media, data_root)

    declaration = load_corpus_declaration(out)
    assert (first.status, again.status) == ("exported", "unchanged")
    assert out.read_bytes() == written
    assert first.to_record()["review"] == {
        "offered": 6,
        "included": 3,
        "excluded": 1,
        "unreviewed": 2,
        "withheld": 3,
        "stream_count": 2,
        "frame_count": 24,
    }
    placed = [
        (group.group_id, group.split, stream.stream_id, stream.selection)
        for group, _, stream in declaration.members()
    ]
    assert [item[:3] for item in placed] == [
        ("site-a", "development", "one.0-16"),
        ("site-b", "calibration", "two.16-24"),
    ]
    assert [(item[3].start_frame, item[3].end_frame) for item in placed if item[3]] == [
        (0, 16),
        (16, 24),
    ]


def test_an_export_never_replaces_another_declaration(
    pool: Any, data_root: Path, media: Path
) -> None:
    (media / f"{FROZEN}.yaml").write_text("other", encoding="ascii")

    with pytest.raises(CorpusRefusal) as caught:
        export_stock(media, data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def test_withdrawn_rights_after_the_run_refuse_the_export(
    pool: tuple[ImportResult, ...], data_root: Path, media: Path, write_recording: WriteRecording
) -> None:
    amend_source_terms(
        write_recording("clip-2.mkv", rights=rights_with(sharing="public")), data_root
    )

    with pytest.raises(CorpusRefusal) as caught:
        export_stock(media, data_root)

    assert caught.value.code is RefusalCode.SOURCE_RECORD_CHANGED
    assert caught.value.details["changed_terms"] == ["rights.sharing"]
    assert not (media / f"{FROZEN}.yaml").exists()


def test_retention_that_ended_refuses_the_export(
    media: Path, data_root: Path, write_recording: WriteRecording, third: ImportResult
) -> None:
    ending = rights_with(retain_until="2026-12-31")
    first = import_clip(media, write_recording, data_root, 2, rights=ending)
    second = import_clip(media, write_recording, data_root, 4, rights=ending)
    stage_pool(media, data_root, first, second, third)

    exported = export_stock(media, data_root, today=date(2026, 12, 31))[1]
    with pytest.raises(CorpusRefusal) as caught:
        export_stock(media, data_root, corpus_id="frozen-v2", today=date(2027, 1, 1))

    assert exported.status == "exported"
    assert caught.value.code is RefusalCode.RETENTION_EXPIRED


def test_the_commands_report_one_record_each(
    pool: Any, cli_root: Path, media: Path, caplog: Any
) -> None:
    review = write_review(media / "review.yaml", *STOCK_DECISIONS)
    out = media / "declaration.yaml"

    queued = main(["discover", "queue", "--run-id", RUN_ID, "--out", str(media / "t.yaml")])
    queue_record = last_record(caplog)
    exported = main(
        ["discover", "export", "--review", str(review), "--corpus-id", FROZEN, "--out", str(out)]
    )

    assert (queued, exported) == (0, 0)
    assert queue_record["declaration_path"] == str(media / "t.yaml")
    record: Any = last_record(caplog)
    assert record["status"] == "exported" and record["declaration_path"] == str(out)
    assert record["review"]["stream_count"] == 2


def test_a_declaration_built_from_the_export_is_the_pool_s_groups_and_splits(
    pool: Any, data_root: Path, media: Path
) -> None:
    out, _ = export_stock(media, data_root)

    built = build_corpus(out, data_root)
    stage_corpus(FROZEN, data_root)

    assert built.to_record()["splits"] == {
        "calibration": {
            "group_count": 1,
            "encounter_count": 1,
            "stream_count": 1,
            "generated_case_count": 0,
        },
        "development": {
            "group_count": 1,
            "encounter_count": 1,
            "stream_count": 1,
            "generated_case_count": 0,
        },
    }
    assert yaml.safe_load(out.read_text(encoding="ascii"))["scenario_rights"] == {
        "max_sensitivity": "high",
        "sharing": "restricted",
    }
