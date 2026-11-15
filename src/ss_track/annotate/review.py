"""Compare two label documents and freeze one hashed revision.

Compare reports every disagreement and exits successfully when the documents can be
compared, including when they differ. Freeze refuses a required disagreement that has
no decision. A disagreement outside the review stays unknown.
"""

from pathlib import Path

from ss_track.annotate.compare import compare_label_sets
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.obligation import apply_decisions, apply_obligation, require_sample
from ss_track.annotate.pack import load_scenario_pack
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.review_model import Disagreement, Reviewer, ReviewPlan
from ss_track.annotate.review_read import read_review, read_settlement
from ss_track.annotate.review_result import ReviewResult
from ss_track.annotate.revision_record import write_revision
from ss_track.annotate.space import FrameSpace, read_frame_space
from ss_track.annotate.validate import read_validated_labels
from ss_track.corpus.declarations.fields import invalid


def compare_labels(left: Path, right: Path, pack: Path, source: Path, review: Path) -> ReviewResult:
    """Report disagreements. An unresolved row is still a successful comparison."""
    _left, _right, plan, rows = _loaded(left, right, pack, source, review)
    return ReviewResult("compare", plan.coverage, _reviewers(_left, _right), rows)


def freeze_labels(
    left: Path,
    right: Path,
    pack: Path,
    source: Path,
    review: Path,
    settlement: Path,
    labels_out: Path,
    revision_out: Path,
) -> ReviewResult:
    """Freeze one label revision. A required disagreement with no decision is refused."""
    if labels_out == revision_out:
        raise invalid("labels and revision must be different files")
    labels_left, labels_right, plan, rows, loaded, space = _context(
        left, right, pack, source, review
    )
    chosen = read_settlement(settlement)
    if chosen.authority != plan.authority:
        raise invalid("settlement authority does not match the review")
    settled = apply_decisions(rows, chosen)
    reviewers = _reviewers(labels_left, labels_right)
    label_sha256, revision_sha256 = write_revision(
        labels_left,
        labels_right,
        settled,
        loaded,
        space,
        plan,
        chosen,
        reviewers,
        labels_out,
        revision_out,
    )
    return ReviewResult(
        "freeze",
        plan.coverage,
        reviewers,
        settled,
        label_sha256,
        revision_sha256,
        labels_out,
        revision_out,
    )


def _loaded(
    left: Path, right: Path, pack: Path, source: Path, review: Path
) -> tuple[LabelSet, LabelSet, ReviewPlan, tuple[Disagreement, ...]]:
    labels_left, labels_right, plan, rows, _pack, _space = _context(
        left, right, pack, source, review
    )
    return labels_left, labels_right, plan, rows


def _context(
    left: Path, right: Path, pack: Path, source: Path, review: Path
) -> tuple[LabelSet, LabelSet, ReviewPlan, tuple[Disagreement, ...], ScenarioPack, FrameSpace]:
    space = read_frame_space(source)
    loaded = load_scenario_pack(pack)
    labels_left = read_validated_labels(left, loaded, space)
    labels_right = read_validated_labels(right, loaded, space)
    plan = read_review(review)
    require_sample(plan, labels_left, labels_right)
    rows = apply_obligation(
        compare_label_sets(labels_left, labels_right), labels_left, labels_right, plan
    )
    return labels_left, labels_right, plan, rows, loaded, space


def _reviewers(left: LabelSet, right: LabelSet) -> tuple[Reviewer, Reviewer]:
    return (
        Reviewer("left", left.document_sha256, _annotators(left)),
        Reviewer("right", right.document_sha256, _annotators(right)),
    )


def _annotators(labels: LabelSet) -> tuple[str, ...]:
    found = {frame.annotator_id for instance in labels.instances for frame in instance.frames}
    return tuple(sorted(found))
