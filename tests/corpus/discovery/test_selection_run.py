"""A plan's selection scores every candidate, ranks pool windows, and `verify` recomputes it."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.cli import main
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.discovery.plan import read_discovery_plan
from ss_track.corpus.discovery.records import DiscoveryRecords, seal_discovery, write_discovery
from ss_track.corpus.discovery.result import DiscoveryResult
from ss_track.corpus.discovery.run import build_discovery, run_discovery, verify_discovery_run
from tests.corpus.conftest import (
    WriteCorpus,
    encounter_of,
    group_of,
    last_record,
    stream_of,
)
from tests.corpus.discovery._plan import plan_document, worker_environ, write_hints, write_plan
from tests.corpus.siblings._fake_sibling import Caches

DIVERSE = {"method": "ssl-diverse", "budget": 3, "score_ids": ["clip-b16.deviation", "motion"]}
UNIFORM = {"method": "uniform", "budget": 3, "seed": 7}  # the audit's seed, on purpose
TILES = {"columns": 2, "rows": 1}
_STAMP = ("kind", "schema_version", "manifest_sha256")


@pytest.fixture
def media_plan(
    first: ImportResult,
    second: ImportResult,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    media: Path,
) -> Path:
    """Streams one and two in a development group, three in a locked one, and a hint file."""
    groups = [
        group_of(
            "group-one",
            "development",
            encounter_of("enc-one", stream_of(first, stream_id="one")),
            encounter_of("enc-two", stream_of(second, stream_id="two")),
        ),
        group_of(
            "group-held", "locked", encounter_of("enc-three", stream_of(third, stream_id="three"))
        ),
    ]
    build_corpus(write_grouped_corpus(groups), data_root)
    stage_corpus("pilot-v1", data_root)
    write_hints(media, first.source_sha256, 0.6)
    return media


@pytest.fixture
def environ(caches: Caches, sibling_python: Path) -> dict[str, str]:
    return worker_environ(caches, sibling_python)


def _plan(media: Path, caches: Caches, selection: dict[str, Any] | None, **changes: Any) -> Path:
    document = plan_document(caches, **changes)
    document["embedding"]["extractors"][0]["tiles"] = TILES
    if selection is not None:
        document["selection"] = selection
    return write_plan(media, document)


def _candidates(records: DiscoveryRecords) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (stream_id, item["candidate_id"]): item
        for stream_id, inventory in records.inventories.items()
        for item in inventory["candidates"]  # type: ignore[union-attr]
    }


@pytest.fixture
def diverse(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> DiscoveryResult:
    return run_discovery(_plan(media_plan, caches, DIVERSE), data_root, environ=environ)


def test_a_tiled_extractor_is_one_run_extractor_per_tile(diverse: DiscoveryResult) -> None:
    run: Any = diverse.records.run

    assert [item["extractor_id"] for item in run["extractors"]] == [
        "clip-b16.r0c0",
        "clip-b16.r0c1",
    ]
    assert run["extractors"][1]["preprocessing"]["crop"] == "tiled"
    assert run["extractors"][1]["preprocessing"]["tile"] == {
        "columns": 2,
        "rows": 1,
        "column": 1,
        "row": 0,
    }
    assert [score["score_id"] for score in run["scores"]] == [
        "clip-b16.deviation",
        "clip-b16.instability",
        "motion",
    ]
    assert diverse.to_record()["coverage"] == [
        {"extractor_id": "clip-b16.r0c0", "covered_fraction": 0.685714, "scale": 4.666667},
        {"extractor_id": "clip-b16.r0c1", "covered_fraction": 0.685714, "scale": 4.666667},
    ]


def test_a_diverse_plan_ranks_pool_windows_outside_the_locked_split(
    diverse: DiscoveryResult,
) -> None:
    assert diverse.records.run["selection"] == {
        "method": "ssl-diverse",
        "revision": 1,
        "seed": None,
        "budget": 3,
        "score_ids": ["clip-b16.deviation", "motion"],
    }
    candidates = _candidates(diverse.records)
    selected = {
        key: item for key, item in candidates.items() if item["selection"]["status"] == "selected"
    }
    assert sorted(item["selection"]["rank"] for item in selected.values()) == [1, 2, 3]
    assert "three" not in {stream for stream, _ in selected}
    held = [item for key, item in candidates.items() if key[0] == "three"]
    assert all(
        item["selection"] == {"status": "excluded", "reason": "operator_excluded"} for item in held
    )
    assert {item["audit"]["status"] for item in held} <= {"sampled", "not_sampled"}
    sibling = [item for item in candidates.values() if item["origin"]["source"] != "pool"]
    assert [item["selection"] for item in sibling] == [{"status": "not_selected", "probability": 0}]


def test_the_result_counts_decisions_and_missing_scores_and_verify_agrees(
    diverse: DiscoveryResult, data_root: Path
) -> None:
    report = diverse.to_record()

    assert report["selection"] == {
        "method": "ssl-diverse",
        "budget": 3,
        "selected": 3,
        "excluded": [{"reason": "operator_excluded", "count": 3}],
    }
    # The sibling window, frames 13 to 17, holds one frame embedded at a stride of 4.
    assert report["unavailable_scores"] == [
        {"score_id": "clip-b16.instability", "reason": "window_too_short", "count": 1}
    ]
    assert verify_discovery_run("discovery-1", data_root).records == diverse.records


def test_selection_leaves_the_audit_sample_where_the_unranked_run_drew_it(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> None:
    runs = {
        name: run_discovery(
            _plan(media_plan, caches, selection, run_id=name), data_root, environ=environ
        ).records
        for name, selection in (("unranked", None), ("uniform", UNIFORM), ("diverse", DIVERSE))
    }

    audits = {
        name: {key: item["audit"] for key, item in _candidates(records).items()}
        for name, records in runs.items()
    }
    assert audits["uniform"] == audits["unranked"] == audits["diverse"]
    for records in runs.values():
        statuses = {
            item["selection"]["status"]
            for item in _candidates(records).values()
            if item["audit"]["status"] == "sampled"
        }
        assert statuses - {"selected"}, "unselected and excluded windows stay in the audit sample"


def test_a_uniform_draw_states_its_probability_and_repeats_on_retry(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> None:
    plan = _plan(media_plan, caches, UNIFORM)
    first = run_discovery(plan, data_root, environ=environ)

    again = run_discovery(plan, data_root, environ=environ)

    assert again.status == "unchanged" and again.records == first.records
    pool = [
        item["selection"]
        for key, item in _candidates(first.records).items()
        if item["origin"]["source"] == "pool" and key[0] != "three"
    ]
    assert len(pool) == 6
    assert {item["probability"] for item in pool} == {0.5}
    assert sum(item["status"] == "selected" for item in pool) == 3
    assert first.records.run["scores"] != []  # recorded for every window, read by none


def _bodies(records: DiscoveryRecords) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run = {
        key: value
        for key, value in records.run.items()
        if key not in (*_STAMP, "inventories", "feature_rows")
    }
    inventories = [
        json.loads(json.dumps({key: value for key, value in item.items() if key not in _STAMP}))
        for item in records.inventories.values()
    ]
    return run, inventories


def _swap_first_pick(inventories: list[dict[str, Any]]) -> None:
    """Give rank 1 to an unpicked window, a decision the method did not make."""
    candidates = [item for inventory in inventories for item in inventory["candidates"]]
    first = next(item for item in candidates if item["selection"].get("rank") == 1)
    other = next(
        item
        for item in candidates
        if item["selection"]["status"] == "not_selected" and item["origin"]["source"] == "pool"
    )
    first["selection"], other["selection"] = other["selection"], first["selection"]


def _raise_a_score(inventories: list[dict[str, Any]]) -> None:
    inventories[0]["candidates"][0]["scores"][-1]["value"] += 1.0


@pytest.mark.parametrize("damage", [_swap_first_pick, _raise_a_score])
def test_a_decision_or_score_the_methods_do_not_give_fails_verification(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str], damage: Any
) -> None:
    plan = read_discovery_plan(_plan(media_plan, caches, DIVERSE))
    records = build_discovery(plan, data_root, environ=environ)
    run, inventories = _bodies(records)
    damage(inventories)
    write_discovery(data_root, seal_discovery(run, inventories, records.features.values()))

    with pytest.raises(CorpusRefusal) as caught:
        verify_discovery_run("discovery-1", data_root)

    assert caught.value.code is RefusalCode.RECORD_INVALID
    findings: Any = caught.value.details["findings"]
    assert {item["rule"] for item in findings} == {"selection"}


def test_a_seed_a_deterministic_method_does_not_use_fails_verification(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> None:
    records = build_discovery(
        read_discovery_plan(_plan(media_plan, caches, DIVERSE)), data_root, environ=environ
    )
    run, inventories = _bodies(records)
    run["selection"]["seed"] = 5
    write_discovery(data_root, seal_discovery(run, inventories, records.features.values()))

    with pytest.raises(CorpusRefusal) as caught:
        verify_discovery_run("discovery-1", data_root)

    findings: Any = caught.value.details["findings"]
    assert [(item["record"], item["pointer"]) for item in findings] == [("run", "/selection")]


def test_a_method_this_ss_track_does_not_know_cannot_be_verified(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> None:
    records = build_discovery(
        read_discovery_plan(_plan(media_plan, caches, DIVERSE)), data_root, environ=environ
    )
    run, inventories = _bodies(records)
    run["selection"]["revision"] = 2
    write_discovery(data_root, seal_discovery(run, inventories, records.features.values()))

    with pytest.raises(CorpusRefusal) as caught:
        verify_discovery_run("discovery-1", data_root)

    assert caught.value.code is RefusalCode.RECORD_INVALID
    assert "cannot reproduce" in caught.value.message


def test_the_command_reports_the_selection_it_verified(
    media_plan: Path,
    caches: Caches,
    environ: dict[str, str],
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in environ.items():
        monkeypatch.setenv(key, value)
    plan = _plan(media_plan, caches, UNIFORM)

    assert main(["discover", "run", "--plan", str(plan)]) == 0
    written = last_record(caplog)
    assert main(["discover", "verify", "--run-id", "discovery-1"]) == 0
    verified = last_record(caplog)

    assert written["selection"] == verified["selection"]
    assert verified["selection"] == {
        "method": "uniform",
        "budget": 3,
        "selected": 3,
        "excluded": [{"reason": "operator_excluded", "count": 3}],
    }
    assert written["coverage"] == verified["coverage"]


def test_a_grid_whose_tiles_do_not_fit_the_frames_is_refused_before_anything_is_written(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> None:
    plan = _plan(media_plan, caches, DIVERSE)
    document: Any = json.loads(json.dumps(read_plan_document(plan)))
    document["embedding"]["extractors"][0]["tiles"] = {"columns": 1, "rows": 1}

    with pytest.raises(CorpusRefusal) as caught:
        run_discovery(write_plan(media_plan, document), data_root, environ=environ)

    assert caught.value.code is RefusalCode.EXTRACTOR_INCOMPATIBLE
    assert not (data_root / "self-supervised-corpus" / "discovery-1").exists()


def read_plan_document(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="ascii"))
    return loaded


def test_evaluation_reads_paired_reviews_and_withheld_audit_is_inconclusive(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> None:
    from ss_track.corpus.evaluation.report import evaluate
    from ss_track.corpus.review.queue import review_queue
    from ss_track.corpus.versions.manifests import load_corpus_manifest

    records = {
        name: run_discovery(
            _plan(media_plan, caches, selection, run_id=name), data_root, environ=environ
        ).records
        for name, selection in (("uniform", UNIFORM), ("diverse", DIVERSE))
    }
    pool = load_corpus_manifest("pilot-v1", data_root)
    paths = {}
    for name, run in records.items():
        queue = review_queue(run, pool)
        decisions = [
            {
                "stream_id": key[0],
                "candidate_id": key[1],
                "decision": "include",
                "observation": "target_present" if key[0] == "one" else "confuser",
            }
            for key in queue.offered
        ]
        paths[name] = media_plan / f"{name}-review.yaml"
        paths[name].write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "run_id": name,
                    "reviewer": "fixture reviewer",
                    "decisions": decisions,
                }
            ),
            encoding="ascii",
        )
    report = evaluate(
        data_root, "diverse", "uniform", paths["diverse"], paths["uniform"], None, None
    ).to_record()
    assert report["status"] == "inconclusive"
    assert "one" in report["whole_stream_target_observed"]
    assert any(
        item["observation"] == "confuser" and item["motion"] is not None
        for item in report["observations"]
    )
    assert any("unknown audit observations" in reason for reason in report["audit"]["reasons"])

    document = yaml.safe_load(paths["uniform"].read_text(encoding="ascii"))
    for decision in document["decisions"]:
        if decision["stream_id"] == "one":
            decision["observation"] = "target_absent"
    paths["uniform"].write_text(yaml.safe_dump(document), encoding="ascii")
    with pytest.raises(CorpusRefusal, match="conflicting observations"):
        evaluate(data_root, "diverse", "uniform", paths["diverse"], paths["uniform"], None, None)


def test_evaluation_refuses_different_budgets_and_audit_designs(
    media_plan: Path, caches: Caches, data_root: Path, environ: dict[str, str]
) -> None:
    from copy import deepcopy

    from ss_track.corpus.evaluation.inputs import Evidence, match

    runs = {
        name: run_discovery(
            _plan(media_plan, caches, selection, run_id=name), data_root, environ=environ
        ).records
        for name, selection in (("uniform", UNIFORM), ("diverse", DIVERSE))
    }
    diverse = Evidence(runs["diverse"], {}, "reviewer", "hash")
    changed = deepcopy(runs["uniform"])
    selection: Any = changed.run["selection"]
    selection["budget"] += 1
    with pytest.raises(CorpusRefusal, match="different selection budgets"):
        match(diverse, Evidence(changed, {}, "reviewer", "hash"))
    changed = deepcopy(runs["uniform"])
    audit: Any = changed.run["audit"]
    audit["seed"] += 1
    with pytest.raises(CorpusRefusal, match="audit design"):
        match(diverse, Evidence(changed, {}, "reviewer", "hash"))

    from ss_track.corpus.evaluation.report import compare

    changed = deepcopy(runs["uniform"])
    for inventory in changed.inventories.values():
        items: Any = inventory["candidates"]
        for item in items:
            if item["selection"]["status"] == "selected":
                item["selection"] = {"status": "not_selected", "probability": 0}
                break
        else:
            continue
        break
    result = compare(diverse, Evidence(changed, {}, "reviewer", "hash")).to_record()
    assert result["status"] == "inconclusive"
    assert "actual selected counts differ" in result["audit"]["reasons"]
