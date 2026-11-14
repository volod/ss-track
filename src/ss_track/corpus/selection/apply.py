"""Score and select a run's candidates, from a plan when a run is built or from the run itself.

The same function serves both, so `discover verify` recomputes from the feature rows and staged
frames exactly what `discover run` wrote. A run states every score and its selection fully: the
score methods, revisions and extractors, and the selection method, budget, seed and scores read.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.descriptors.descriptor_public import LOCKED
from ss_track.corpus.discovery.features import FeatureFile
from ss_track.corpus.discovery.inventory_rules import COMPUTED
from ss_track.corpus.discovery.run_rules import POOL
from ss_track.corpus.selection.catalog import (
    METHOD_REVISIONS,
    MOTION,
    SCORE_METHODS,
    SEEDED_METHODS,
    UNRANKED,
    ScoreSpec,
)
from ss_track.corpus.selection.embeddings import stream_embeddings, unit
from ss_track.corpus.selection.methods import SelectionSpec, Window, known_selection, select
from ss_track.corpus.selection.motion import stream_changes
from ss_track.corpus.selection.scores import WindowFacts, candidate_scores, known_method


@dataclass(frozen=True, slots=True)
class Selection:
    """The scores a run computes and how it selects."""

    scores: tuple[ScoreSpec, ...]
    spec: SelectionSpec

    def run_scores(self) -> list[JsonValue]:
        """Return the run's scores section."""
        return [score.to_record() for score in self.scores]

    def run_selection(self) -> dict[str, JsonValue]:
        """Return the run's selection section."""
        return {
            "method": self.spec.method,
            "revision": METHOD_REVISIONS[self.spec.method],
            "seed": self.spec.seed,
            "budget": self.spec.budget,
            "score_ids": list(self.spec.score_ids),
        }


def unranked() -> Selection:
    """Return the selection of a run that ranks nothing and computes no score."""
    return Selection((), SelectionSpec(UNRANKED, 0, None, (), ()))


def planned(
    method: str,
    budget: int,
    seed: int | None,
    score_ids: Sequence[str],
    scores: Sequence[ScoreSpec],
) -> Selection:
    """Return a plan's selection over the scores the run computes."""
    read = {score.score_id: score for score in scores}
    extractors = sorted({e for score_id in score_ids for e in read[score_id].extractor_ids})
    spec = SelectionSpec(method, budget, seed, tuple(score_ids), tuple(extractors))
    return Selection(tuple(scores), spec)


def _cannot_reproduce(what: str, details: dict[str, JsonValue]) -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.RECORD_INVALID,
        f"this ss-track cannot reproduce the run's {what}",
        details,
    )


def from_run(run: Mapping[str, Any]) -> Selection:
    """Return the selection a run states, refusing a method this ss-track does not know."""
    scores = []
    for score in run["scores"]:
        if not known_method(score["method"], score["revision"]):
            details = {"score_id": score["score_id"], "method": score["method"]}
            raise _cannot_reproduce("score", details | {"revision": score["revision"]})
        spec = (score["score_id"], score["method"], score["revision"], score["extractor_ids"])
        scores.append(ScoreSpec(spec[0], spec[1], spec[2], tuple(spec[3])))
    selection = run["selection"]
    if not known_selection(selection["method"], selection["revision"]):
        details = {"method": selection["method"], "revision": selection["revision"]}
        raise _cannot_reproduce("selection", details)
    seed = selection["seed"] if selection["method"] in SEEDED_METHODS else None
    return planned(selection["method"], selection["budget"], seed, selection["score_ids"], scores)


def locked_streams(corpus: Mapping[str, Any]) -> frozenset[str]:
    """Return the streams a corpus version places in the locked split."""
    return frozenset(
        str(stream["stream_id"]) for stream in corpus["streams"] if stream["split"] == LOCKED
    )


def _facts(
    selection: Selection, features: Mapping[str, FeatureFile], bundles: Iterable[FrameBundle]
) -> WindowFacts:
    motion_method = SCORE_METHODS[MOTION]
    needs_frames = any((s.method, s.revision) == motion_method for s in selection.scores)
    changes = stream_changes(bundles) if needs_frames else {}
    return WindowFacts(changes, stream_embeddings(features))


def score_and_select(
    selection: Selection,
    inventories: Sequence[Mapping[str, Any]],
    features: Mapping[str, FeatureFile],
    bundles: Iterable[FrameBundle],
    locked: frozenset[str],
) -> list[dict[str, Any]]:
    """Return the inventories with every candidate's scores and selection filled in."""
    if not selection.scores and selection.spec.method == UNRANKED:
        facts = WindowFacts({}, {})
    else:
        facts = _facts(selection, features, bundles)
    scored: list[dict[str, Any]] = []
    windows: list[Window] = []
    for inventory in inventories:
        stream_id = str(inventory["stream_id"])
        candidates = []
        for candidate in inventory["candidates"]:
            scores = candidate_scores(selection.scores, facts, stream_id, candidate["window"])
            candidates.append({**candidate, "scores": scores})
            windows.append(_window(selection, facts, stream_id, candidates[-1], locked))
        scored.append({**inventory, "candidates": candidates})
    decided = select(selection.spec, windows)
    return [
        {
            **inventory,
            "candidates": [
                {**item, "selection": decided[(inventory["stream_id"], item["candidate_id"])]}
                for item in inventory["candidates"]
            ],
        }
        for inventory in scored
    ]


def _window(
    selection: Selection,
    facts: WindowFacts,
    stream_id: str,
    candidate: Mapping[str, Any],
    locked: frozenset[str],
) -> Window:
    values = {
        score["score_id"]: float(score["value"])
        for score in candidate["scores"]
        if score["status"] == COMPUTED
    }
    window = candidate["window"]
    descriptors = {}
    for extractor_id in selection.spec.extractor_ids:
        embedding = facts.embeddings.get((extractor_id, stream_id))
        rows = (
            None
            if embedding is None
            else embedding.window(window["start_frame"], window["end_frame"])
        )
        if rows is not None and len(rows):
            descriptors[extractor_id] = unit(rows.mean(axis=0))
    return Window(
        stream_id,
        str(candidate["candidate_id"]),
        candidate["origin"]["source"] == POOL,
        stream_id in locked,
        values,
        descriptors,
    )
