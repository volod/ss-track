"""`discover evaluate` logs a comparison the newest command result accepts."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from ss_track.cli import main
from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.discovery.reader import read_discovery
from ss_track.corpus.review.queue import ReviewQueue, review_queue
from ss_track.corpus.versions.manifests import load_corpus_manifest
from tests.corpus.conftest import (
    WriteCorpus,
    encounter_of,
    group_of,
    last_record,
    stream_of,
)
from tests.corpus.discovery._plan import plan_document, worker_environ
from tests.corpus.siblings._fake_sibling import Caches

DIVERSE = {"method": "ssl-diverse", "budget": 2, "score_ids": ["clip-b16.deviation", "motion"]}
UNIFORM = {"method": "uniform", "budget": 2, "seed": 11}
_LIMITS = [
    "observations are not labels",
    "compute cost was not recorded by discovery",
    "recorded blinding is a declaration, and pictures may show the source",
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
    audit = _object(record, "audit")
    assert audit["status"] == "estimated"
    assert audit["recall"] is not None


def _require_inconclusive(record: dict[str, object]) -> None:
    audit = _object(record, "audit")
    reasons = audit["reasons"]
    assert isinstance(reasons, list)
    assert record["status"] == "inconclusive"
    assert record["review_blinding"] == "unrecorded"
    assert record["review_independence"] == "unrecorded"
    assert record["review_effort_minutes"] == [None, None]
    assert audit["recall"] is None
    assert any("unknown audit observations" in reason for reason in reasons)


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
    _require_inconclusive(inconclusive)
    _require_estimated(last_record(caplog), "mixed")
