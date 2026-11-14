"""The scores a discovery run can compute, named from its plan, and the selection methods it knows.

A score is named by what it measures and, for one that reads embeddings, by the plan extractor whose
rows it reads: `motion`, `<extractor_id>.deviation` and `<extractor_id>.instability`. A tiled plan
extractor is many run extractors, one per tile, and its scores read all of them. Each score and
method has a revision; a changed algorithm takes a new one, so a run names exactly what computed it.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ss_track.core.refusal import JsonValue

MOTION = "motion"
DEVIATION = "deviation"
INSTABILITY = "instability"
HIGHER = "higher"
UNRANKED = "unranked"
UNIFORM = "uniform"
SSL_DIVERSE = "ssl-diverse"
SEEDED_METHODS = frozenset({UNIFORM})
METHOD_REVISIONS = {UNRANKED: 1, UNIFORM: 1, SSL_DIVERSE: 1}
# The method of each score, by what it measures, and the method's revision.
SCORE_METHODS = {
    MOTION: ("block-difference", 1),
    DEVIATION: ("background-deviation", 1),
    INSTABILITY: ("temporal-instability", 1),
}


@dataclass(frozen=True, slots=True)
class ScoreSpec:
    """One score of a run: what computes it and which run extractors it reads."""

    score_id: str
    method: str
    revision: int
    extractor_ids: tuple[str, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the score as a run states it."""
        return {
            "score_id": self.score_id,
            "method": self.method,
            "revision": self.revision,
            "extractor_ids": list(self.extractor_ids),
            "preferred": HIGHER,
        }


def _spec(score_id: str, measure: str, extractor_ids: Sequence[str]) -> ScoreSpec:
    method, revision = SCORE_METHODS[measure]
    return ScoreSpec(score_id, method, revision, tuple(sorted(extractor_ids)))


def score_specs(extractors: Sequence[tuple[str, Sequence[str]]]) -> list[ScoreSpec]:
    """Return every score a run computes, in ascending score_id order.

    `extractors` names each plan extractor and the run extractors it became.
    """
    specs = [_spec(MOTION, MOTION, ())]
    for plan_id, run_ids in extractors:
        specs += [
            _spec(f"{plan_id}.{measure}", measure, run_ids) for measure in (DEVIATION, INSTABILITY)
        ]
    return sorted(specs, key=lambda spec: spec.score_id)
