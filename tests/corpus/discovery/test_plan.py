"""A discovery plan is read under its contract and the order rule its contract states in words."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.discovery.plan import read_discovery_plan

EXAMPLE = Path(__file__).parents[2] / "schema" / "examples" / "declaration-discovery-plan.json"


def _plan(tmp_path: Path, change: Any = None) -> Path:
    document = json.loads(EXAMPLE.read_text(encoding="ascii"))
    if change is not None:
        change(document)
    path = tmp_path / "plan.yaml"
    path.write_text(json.dumps(document), encoding="ascii")
    return path


def test_the_example_plan_reads_whole(tmp_path: Path) -> None:
    plan = read_discovery_plan(_plan(tmp_path))

    assert (plan.run_id, plan.corpus_id, plan.window_frames) == ("discovery-1", "pilot-v1", 8)
    assert (plan.approval_owner, plan.approval_reference) == ("project owner", "approval-2026-001")
    assert plan.embedding is not None
    assert [item.extractor_id for item in plan.embedding.extractors] == ["clip-b16", "dino-b14"]
    assert plan.embedding.extractors[1].pretrained is None
    assert plan.hints[0].path == tmp_path / "hints.yaml"


def test_a_plan_may_embed_nothing_and_read_no_hints(tmp_path: Path) -> None:
    def bare(document: dict[str, Any]) -> None:
        del document["embedding"], document["hints"], document["selection"]

    plan = read_discovery_plan(_plan(tmp_path, bare))

    assert plan.embedding is None and plan.hints == () and plan.selection is None


def _drop_approval(document: dict[str, Any]) -> None:
    del document["source_approval"]


def _branch_revision(document: dict[str, Any]) -> None:
    document["embedding"]["extractors"][0]["weights"][0]["revision"] = "main"


def _unordered(document: dict[str, Any]) -> None:
    document["embedding"]["extractors"].reverse()


def _openclip_without_tag(document: dict[str, Any]) -> None:
    del document["embedding"]["extractors"][0]["pretrained"]


def _repeated_hint(document: dict[str, Any]) -> None:
    document["hints"].append(dict(document["hints"][0]))


@pytest.mark.parametrize(
    "change",
    [_drop_approval, _branch_revision, _unordered, _openclip_without_tag, _repeated_hint],
)
def test_a_plan_that_cannot_be_pinned_or_approved_is_refused(tmp_path: Path, change: Any) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_discovery_plan(_plan(tmp_path, change))

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_missing_plan_is_refused(tmp_path: Path) -> None:
    shutil.rmtree(tmp_path)

    with pytest.raises(CorpusRefusal) as caught:
        read_discovery_plan(tmp_path / "plan.yaml")

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_selection_reads_scores_the_run_computes(tmp_path: Path) -> None:
    plan = read_discovery_plan(_plan(tmp_path))

    assert plan.selection is not None
    assert (plan.selection.method, plan.selection.budget, plan.selection.seed) == (
        "ssl-diverse",
        20,
        None,
    )
    assert plan.selection.score_ids == ("clip-b16.deviation", "dino-b14.deviation", "motion")
    dino = plan.extractors()[1]
    assert dino.tiles == (3, 2)
    assert [view for view, _ in dino.views()][:4] == [
        "dino-b14.r0c0",
        "dino-b14.r0c1",
        "dino-b14.r0c2",
        "dino-b14.r1c0",
    ]


def test_a_uniform_selection_needs_no_embedding_and_keeps_its_seed(tmp_path: Path) -> None:
    def uniform(document: dict[str, Any]) -> None:
        del document["embedding"]
        document["selection"] = {"method": "uniform", "budget": 3, "seed": 11}

    plan = read_discovery_plan(_plan(tmp_path, uniform))

    assert plan.selection is not None
    assert (plan.selection.method, plan.selection.seed, plan.selection.score_ids) == (
        "uniform",
        11,
        (),
    )


def _unknown_score(document: dict[str, Any]) -> None:
    document["selection"]["score_ids"] = ["clip-b16.novelty"]


def _unordered_scores(document: dict[str, Any]) -> None:
    document["selection"]["score_ids"].reverse()


def _uniform_without_seed(document: dict[str, Any]) -> None:
    document["selection"] = {"method": "uniform", "budget": 3}


def _taken_tile_id(document: dict[str, Any]) -> None:
    untiled = {key: value for key, value in document["embedding"]["extractors"][1].items()}
    del untiled["tiles"]
    document["embedding"]["extractors"].append(untiled | {"extractor_id": "dino-b14.r0c0"})


def _long_tile_id(document: dict[str, Any]) -> None:
    long_id = "d" * 62
    document["embedding"]["extractors"][1]["extractor_id"] = long_id
    document["selection"]["score_ids"] = ["clip-b16.deviation", "motion"]


def _diverse_without_embedding(document: dict[str, Any]) -> None:
    del document["embedding"]


@pytest.mark.parametrize(
    "change",
    [
        _unknown_score,
        _unordered_scores,
        _uniform_without_seed,
        _taken_tile_id,
        _long_tile_id,
        _diverse_without_embedding,
    ],
)
def test_a_selection_or_tiling_the_run_cannot_name_is_refused(tmp_path: Path, change: Any) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_discovery_plan(_plan(tmp_path, change))

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
