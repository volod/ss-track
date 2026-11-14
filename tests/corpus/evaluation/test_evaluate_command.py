"""`discover evaluate` logs a comparison the newest command result accepts."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.cli import main
from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.discovery.reader import read_discovery
from ss_track.corpus.review.queue import ReviewQueue, review_queue
from ss_track.corpus.review.selection_pass import expected_windows
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.registry.store import load_contract_set
from ss_track.schema.validation.strict import violations
from tests.corpus.conftest import (
    WriteCorpus,
    encounter_of,
    group_of,
    last_record,
    stream_of,
)
from tests.corpus.discovery._plan import plan_document, worker_environ
from tests.corpus.siblings._fake_sibling import Caches

# Six windows tile the two clips. Both methods then select the whole pool, so the audit
# overlap and the offered queues match. A smaller budget can select equal counts with
# different overlap, which is not a matched review budget.
DIVERSE = {"method": "ssl-diverse", "budget": 6, "score_ids": ["clip-b16.deviation", "motion"]}
UNIFORM = {"method": "uniform", "budget": 6, "seed": 11}
_LIMITS = [
    "observations are not labels",
    "compute cost was not recorded by discovery",
    "recorded blinding is a declaration, and pictures may show the source",
    "unrecorded review minutes are unmeasured, not zero",
    "a source without a reviewed sample is not zero, "
    "and a per-source estimate is not field prevalence",
]


@pytest.fixture
def environ(caches: Caches, sibling_python: Path) -> dict[str, str]:
    return worker_environ(caches, sibling_python)


def _plan(media: Path, caches: Caches, run_id: str, selection: dict[str, object]) -> Path:
    document = plan_document(caches, run_id=run_id)
    document.pop("hints")
    document["selection"] = selection
    path = media / f"{run_id}.yaml"
    path.write_text(yaml.safe_dump(document), encoding="ascii")
    return path


def _queue(data_root: Path, run_id: str) -> ReviewQueue:
    corpus = load_corpus_manifest("pilot-v1", data_root)
    return review_queue(read_discovery(data_root, run_id), corpus)


def _object(record: dict[str, object], key: str) -> dict[str, Any]:
    value = record[key]
    assert isinstance(value, dict)
    return value


def _review(
    path: Path, run_id: str, queue: ReviewQueue, observation: str, **provenance: object
) -> None:
    decisions = [
        {
            "stream_id": key[0],
            "candidate_id": key[1],
            "decision": "include",
            "observation": observation,
        }
        for key in sorted(queue.offered)
    ]
    document: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "reviewer": "fixture reviewer",
        "decisions": decisions,
    }
    document.update(provenance)
    path.write_text(yaml.safe_dump(document), encoding="ascii")


def _evaluate(diverse: Path, uniform: Path) -> list[str]:
    return [
        "discover",
        "evaluate",
        "--diverse-run",
        "diverse",
        "--uniform-run",
        "uniform",
        "--diverse-review",
        str(diverse),
        "--uniform-review",
        str(uniform),
    ]


def _require_estimated(record: dict[str, object], blinding: str) -> None:
    assert "blind" not in record
    assert record["status"] == "estimated"
    assert record["review_blinding"] == blinding
    assert record["review_independence"] == "declared"
    assert record["review_effort_minutes"] == [12, 15]
    assert record["limits"] == _LIMITS
    assert _object(_object(record, "runs"), "diverse")["compute_cost"] is None
    budget = _object(record, "review_budget")
    assert budget["status"] == "matched"
    assert budget["protocol"] == "per_run"
    assert budget["recorded_effort"] == "unequal"
    diverse = _object(_object(record, "runs"), "diverse")
    uniform = _object(_object(record, "runs"), "uniform")
    assert diverse["offered_windows"] == uniform["offered_windows"]
    assert diverse["sibling_offers"] == uniform["sibling_offers"] == 0
    assert diverse["selected"] == uniform["selected"]
    audit = _object(record, "audit")
    assert audit["status"] == "estimated"
    assert audit["recall"] is not None
    _require_source_exposure(record)


def _require_inconclusive(record: dict[str, object]) -> None:
    audit = _object(record, "audit")
    reasons = audit["reasons"]
    assert isinstance(reasons, list)
    assert record["status"] == "inconclusive"
    assert record["review_blinding"] == "unrecorded"
    assert record["review_independence"] == "unrecorded"
    assert record["review_effort_minutes"] == [None, None]
    budget = _object(record, "review_budget")
    assert budget["status"] == "matched"
    assert budget["recorded_effort"] == "unmeasured"
    assert audit["recall"] is None
    assert any("unknown audit observations" in reason for reason in reasons)
    _require_source_exposure(record)


def _require_source_exposure(record: dict[str, object]) -> None:
    by_source = _object(record, "by_source")
    assert by_source["weighting"] == "stratum_design"
    assert by_source["provenance"] == "incomplete"
    assert by_source["collections"] == []
    assert by_source["reasons"] == []
    incomplete = _object(by_source, "incomplete")
    assert incomplete["pool_windows"] == 6
    assert incomplete["reasons"] == ["source record has no origin"]


def test_evaluate_logs_estimated_and_inconclusive_comparisons(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    media: Path,
    caches: Caches,
    environ: dict[str, str],
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in environ.items():
        monkeypatch.setenv(key, value)
    groups = [
        group_of(
            "group-one",
            "development",
            encounter_of("enc-one", stream_of(first, stream_id="one")),
            encounter_of("enc-two", stream_of(second, stream_id="two")),
        )
    ]
    build_corpus(write_grouped_corpus(groups), data_root)
    stage_corpus("pilot-v1", data_root)
    assert main(["discover", "run", "--plan", str(_plan(media, caches, "diverse", DIVERSE))]) == 0
    assert main(["discover", "run", "--plan", str(_plan(media, caches, "uniform", UNIFORM))]) == 0
    queues = {name: _queue(data_root, name) for name in ("diverse", "uniform")}
    known = {
        "diverse": media / "diverse-known.yaml",
        "uniform": media / "uniform-known.yaml",
    }
    _review(
        known["diverse"],
        "diverse",
        queues["diverse"],
        "target_present",
        independence="declared",
        blinding="declared",
        reviewer_minutes=12,
    )
    _review(
        known["uniform"],
        "uniform",
        queues["uniform"],
        "target_present",
        independence="declared",
        blinding="declared",
        reviewer_minutes=15,
    )

    assert main(_evaluate(known["diverse"], known["uniform"])) == 0
    estimated = last_record(caplog)
    for name in ("diverse", "uniform"):
        reported = _object(_object(estimated, "runs"), name)
        assert reported["offered_windows"] == len(queues[name].offered)
        assert reported["withheld_windows"] == len(queues[name].withheld)
    offered = set(queues["diverse"].offered) | set(queues["uniform"].offered)
    assert estimated["unique_offered_windows"] == len(offered)

    unknown = {name: media / f"{name}-unknown.yaml" for name in ("diverse", "uniform")}
    for name in ("diverse", "uniform"):
        _review(unknown[name], name, queues[name], "unknown")
    assert main(_evaluate(unknown["diverse"], unknown["uniform"])) == 0
    inconclusive = last_record(caplog)

    mixed = media / "uniform-mixed.yaml"
    _review(
        mixed,
        "uniform",
        queues["uniform"],
        "target_present",
        independence="declared",
        blinding="not_declared",
        reviewer_minutes=15,
    )
    assert main(_evaluate(known["diverse"], mixed)) == 0

    _require_estimated(estimated, "declared")
    _require_previous_minor(estimated)
    _require_inconclusive(inconclusive)
    _require_estimated(last_record(caplog), "mixed")

    passed = {name: media / f"{name}-pass.yaml" for name in ("diverse", "uniform")}
    for name in ("diverse", "uniform"):
        _review(
            passed[name],
            name,
            queues[name],
            "target_present",
            audit_id="audit-1",
            selection_pass=_selection_pass(queues[name]),
        )
    assert main(_evaluate(passed["diverse"], passed["uniform"])) == 0
    _require_selection_pass(last_record(caplog), queues)


def _require_previous_minor(record: dict[str, object]) -> None:
    """A comparison without a selection pass is still a result/command 1.24.0 record."""
    contracts = load_contract_set()
    contract = contracts.named("result/command")
    previous = next(item for item in contract.versions if str(item.version) == "1.24.0")
    schema = contracts.frozen_schema(contract, previous)
    assert violations(record, schema, contracts.schema_registry()) == []


def _selection_pass(queue: ReviewQueue) -> dict[str, object]:
    windows = [
        {"stream_id": key[0], "candidate_id": key[1], "observation": "target_present"}
        for key in sorted(expected_windows(queue))
    ]
    return {"reviewer": "pass reviewer", "reviewer_minutes": 4, "windows": windows}


def _require_selection_pass(record: dict[str, object], queues: dict[str, ReviewQueue]) -> None:
    budget = _object(record, "review_budget")
    passes = _object(budget, "selection_pass")
    assert budget["protocol"] == "selection_pass"
    assert budget["status"] == "matched"
    assert budget["comparable_windows"] == {"diverse": 6, "uniform": 6}
    assert passes["disagreements"] == []
    for name in ("diverse", "uniform"):
        account = _object(passes, name)
        assert account["reviewed_windows"] == len(expected_windows(queues[name])) == 6
        assert account["reviewer_minutes"] == 4
    assert passes["review_exposures"] == budget["shared_audit_windows"] + 12
