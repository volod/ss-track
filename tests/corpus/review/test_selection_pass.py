"""A review's selection pass: offered by the template, bounded by selection, carried by freeze."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.discovery.reader import read_discovery
from ss_track.corpus.evaluation.inputs import read_evidence
from ss_track.corpus.review.decisions import read_review
from ss_track.corpus.review.export import export_review
from ss_track.corpus.review.freeze import freeze_corpus
from ss_track.corpus.review.queue import CandidateKey, review_queue
from ss_track.corpus.review.selection_pass import expected_windows
from ss_track.corpus.review.template import queue_review
from ss_track.corpus.storage.layout import freeze_path
from ss_track.corpus.versions.manifests import load_corpus_manifest
from tests.corpus.conftest import reseal
from tests.corpus.review._review import (
    FROZEN,
    POOL,
    RUN_ID,
    STOCK_DECISIONS,
    review_links,
    staged,
    write_review,
)


def _selected(data_root: Path) -> list[CandidateKey]:
    queue = review_queue(read_discovery(data_root, RUN_ID), load_corpus_manifest(POOL, data_root))
    return sorted(expected_windows(queue))


def _window(key: CandidateKey, observation: str = "target_absent") -> dict[str, str]:
    return {"stream_id": key[0], "candidate_id": key[1], "observation": observation}


def _with_pass(path: Path, windows: list[dict[str, str]], **fields: object) -> Path:
    document = yaml.safe_load(path.read_text(encoding="ascii"))
    document["selection_pass"] = {"reviewer": "second reviewer", "windows": windows} | fields
    path.write_text(yaml.safe_dump(document), encoding="ascii")
    return path


def test_the_template_offers_a_commented_pass_of_every_selected_window(
    pool: Any, data_root: Path, media: Path
) -> None:
    template = media / "review.yaml"
    queue_review(RUN_ID, data_root, template)
    text = template.read_text(encoding="ascii")
    selected = _selected(data_root)

    assert len(selected) == 2  # the stock plan selects two windows
    assert "# selection_pass:" in text
    for stream_id, candidate_id in selected:
        assert f'#   - {{stream_id: "{stream_id}", candidate_id: "{candidate_id}"' in text
    uncommented = text.replace("# selection_pass:", "selection_pass:").replace("#   ", "  ")
    uncommented = uncommented.replace('reviewer: ""  #', 'reviewer: "site lead"  #')
    blank = media / "blank.yaml"
    blank.write_text(uncommented, encoding="ascii")
    with pytest.raises(CorpusRefusal) as caught:
        read_review(blank)  # an unnamed pass reviewer and blank observations do not pass
    assert caught.value.code is RefusalCode.MANIFEST_INVALID

    filled = uncommented.replace('reviewer: ""', 'reviewer: "second reviewer"')
    filled = filled.replace('observation: ""', "observation: unknown")
    blank.write_text(filled, encoding="ascii")
    review = read_review(blank)
    assert review.selection_pass is not None
    assert sorted(review.selection_pass.observations) == selected


def test_freezing_carries_the_pass_and_evaluation_keeps_it_apart_from_observations(
    pool: Any, data_root: Path, media: Path
) -> None:
    review = staged(media, data_root)
    selected = _selected(data_root)
    windows = [_window(key, "target_present") for key in reversed(selected)]
    _with_pass(review, windows, reviewer_minutes=7)
    record: Any = freeze_corpus(FROZEN, review, review_links(data_root), data_root).record

    carried = record["review"]["selection_pass"]
    assert carried == {
        "reviewer": "second reviewer",
        "reviewer_minutes": 7,
        "windows": [_window(key, "target_present") for key in selected],
    }
    from_review = read_evidence(data_root, RUN_ID, review, None)
    from_freeze = read_evidence(data_root, RUN_ID, None, FROZEN)
    assert from_review.selection_pass == from_freeze.selection_pass
    assert from_freeze.observations == from_review.observations
    stock = {(item["stream_id"], item["candidate_id"]) for item in STOCK_DECISIONS}
    assert set(from_freeze.observations) == stock  # the pass adds no observation


def test_a_review_without_a_pass_freezes_as_before(pool: Any, data_root: Path, media: Path) -> None:
    review = staged(media, data_root)
    record: Any = freeze_corpus(FROZEN, review, review_links(data_root), data_root).record
    assert "selection_pass" not in record["review"]
    assert read_evidence(data_root, RUN_ID, None, FROZEN).selection_pass is None


def test_a_pass_names_only_selected_offered_windows(
    pool: Any, data_root: Path, media: Path
) -> None:
    selected = set(_selected(data_root))
    queue = review_queue(read_discovery(data_root, RUN_ID), load_corpus_manifest(POOL, data_root))
    unselected = min(key for key in queue.offered if key not in selected)
    locked = min(queue.withheld)
    review = write_review(media / "review.yaml", *STOCK_DECISIONS)
    _with_pass(review, [_window(unselected), _window(locked)])

    with pytest.raises(CorpusRefusal) as caught:
        export_review(review, FROZEN, media / "out.yaml", data_root)
    with pytest.raises(CorpusRefusal) as evaluated:
        read_evidence(data_root, RUN_ID, review, None)

    details: Any = caught.value.details
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert details["not_selected"] == [{"stream_id": unselected[0], "candidate_id": unselected[1]}]
    assert details["locked_without_policy"] == [{"stream_id": locked[0], "candidate_id": locked[1]}]
    assert evaluated.value.code is RefusalCode.MANIFEST_INVALID


def test_a_window_listed_twice_in_a_pass_is_refused(
    pool: Any, data_root: Path, media: Path
) -> None:
    key = _selected(data_root)[0]
    review = _with_pass(
        write_review(media / "review.yaml", *STOCK_DECISIONS),
        [_window(key), _window(key, "confuser")],
    )
    with pytest.raises(CorpusRefusal) as caught:
        read_review(review)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "twice" in caught.value.message


def test_an_altered_pass_in_a_freeze_record_is_refused(
    pool: Any, data_root: Path, media: Path
) -> None:
    review = staged(media, data_root)
    selected = _selected(data_root)
    _with_pass(review, [_window(key) for key in selected])
    links = review_links(data_root)
    record: Any = freeze_corpus(FROZEN, review, links, data_root).record
    path = freeze_path(data_root, FROZEN)

    edited = json.loads(path.read_text(encoding="ascii"))
    edited["review"]["selection_pass"]["windows"][0]["observation"] = "target_present"
    path.chmod(0o644)
    path.write_text(json.dumps(edited), encoding="ascii")
    with pytest.raises(CorpusRefusal) as tampered:
        read_evidence(data_root, RUN_ID, None, FROZEN)
    assert tampered.value.code is RefusalCode.RECORD_TAMPERED

    forged = dict(record["review"])
    forged["selection_pass"] = dict(forged["selection_pass"])
    forged["selection_pass"]["windows"] = list(reversed(forged["selection_pass"]["windows"]))
    reseal(path, review=forged)
    with pytest.raises(CorpusRefusal) as unordered:
        read_evidence(data_root, RUN_ID, None, FROZEN)
    assert unordered.value.code is RefusalCode.RECORD_INVALID
