"""Compare two label documents and freeze one hashed revision.

Compare reports every disagreement and exits successfully when the documents can be
compared, including when they differ. Freeze refuses a required disagreement that has
no decision. A disagreement outside the review stays unknown. A frozen revision is
written once: the same freeze again changes nothing, and another revision at those
paths is refused, as is an output path that is one of the inputs.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.annotate.labels.document import read_label_file
from ss_track.annotate.labels.model import LabelSet
from ss_track.annotate.packs.load import load_scenario_pack
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.review.compare import compare_label_sets
from ss_track.annotate.review.model import Disagreement, Reviewer, ReviewPlan
from ss_track.annotate.review.obligation import apply_decisions, apply_obligation, require_sample
from ss_track.annotate.review.read import read_review, read_settlement
from ss_track.annotate.review.result import ReviewResult
from ss_track.annotate.review.revision import write_revision
from ss_track.annotate.sources.declared_space import require_stream
from ss_track.annotate.sources.frame_space import FrameSpace, read_frame_space
from ss_track.corpus.declarations.fields import invalid


@dataclass(frozen=True, slots=True)
class ReviewInputs:
    """Two label documents of one source and one pack, and the review plan that covers them."""

    left: Path
    right: Path
    pack: Path
    source: Path
    review: Path
    video_stream_index: int | None = None


@dataclass(frozen=True, slots=True)
class _Loaded:
    """Both label sets after their checks, and the disagreements the plan marks."""

    left: LabelSet
    right: LabelSet
    pack: ScenarioPack
    space: FrameSpace
    plan: ReviewPlan
    rows: tuple[Disagreement, ...]

    @property
    def reviewers(self) -> tuple[Reviewer, Reviewer]:
        """Return both sides with the annotator ids each document carries."""
        return (
            Reviewer("left", self.left.document_sha256, _annotators(self.left)),
            Reviewer("right", self.right.document_sha256, _annotators(self.right)),
        )


def compare_labels(inputs: ReviewInputs) -> ReviewResult:
    """Report disagreements. An unresolved row is still a successful comparison."""
    loaded = _load(inputs)
    return ReviewResult("compare", loaded.plan.coverage, loaded.reviewers, loaded.rows)


def freeze_labels(
    inputs: ReviewInputs,
    settlement: Path,
    labels_out: Path,
    revision_out: Path,
    *,
    stream: Mapping[str, object] | None = None,
) -> ReviewResult:
    """Freeze one label revision. A required disagreement with no decision is refused.

    `stream` is the corpus stream the revision is filed under, when the freeze names one. The
    source is then checked against the frame shape that stream's pinned decode gave.
    """
    _require_outputs(inputs, settlement, labels_out, revision_out)
    loaded = _load(inputs)
    if stream is not None:
        require_stream(loaded.left.space, stream, f"labels {loaded.left.label_id}")
    chosen = read_settlement(settlement)
    if chosen.authority != loaded.plan.authority:
        raise invalid("settlement authority does not match the review")
    settled = apply_decisions(loaded.rows, chosen)
    label_sha256, revision_sha256 = write_revision(
        loaded.left,
        loaded.right,
        settled,
        loaded.pack,
        loaded.space,
        loaded.plan,
        chosen,
        loaded.reviewers,
        labels_out,
        revision_out,
    )
    return ReviewResult(
        "freeze",
        loaded.plan.coverage,
        loaded.reviewers,
        settled,
        label_sha256,
        revision_sha256,
        labels_out,
        revision_out,
    )


def _require_outputs(
    inputs: ReviewInputs, settlement: Path, labels_out: Path, revision_out: Path
) -> None:
    """Refuse outputs that are one file, or a file the freeze reads."""
    if labels_out.resolve() == revision_out.resolve():
        raise invalid("labels and revision must be different files")
    read = {
        "left": inputs.left,
        "right": inputs.right,
        "pack": inputs.pack,
        "source": inputs.source,
        "review": inputs.review,
        "settlement": settlement,
    }
    for output in (labels_out, revision_out):
        for name, path in read.items():
            if output.resolve() == path.resolve():
                raise invalid(f"output {output.name} is the {name} input; choose another path")


def _load(inputs: ReviewInputs) -> _Loaded:
    space = read_frame_space(inputs.source, inputs.video_stream_index)
    pack = load_scenario_pack(inputs.pack)
    left = read_label_file(inputs.left, pack, space)
    right = read_label_file(inputs.right, pack, space)
    plan = read_review(inputs.review)
    require_sample(plan, left, right)
    rows = apply_obligation(compare_label_sets(left, right), left, right, plan)
    return _Loaded(left, right, pack, space, plan, rows)


def _annotators(labels: LabelSet) -> tuple[str, ...]:
    found = {frame.annotator_id for instance in labels.instances for frame in instance.frames}
    return tuple(sorted(found))
