# Annotation review tools

## Task and scope

- Id / capability: `annotation-review-tools` / `annotation-selection`
- State: accepted
- Source: plan task at `c24d4fd`; no unrelated dirty files.
- Plan counts at start: 159 open tasks (130 agent, 29 human); next agent
  `annotation-review-tools`, next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### annotation-review-tools

Two reviewers must be able to compare labels and settle disagreement.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Reviewers see disagreements and freeze one hashed label revision, with a
  sensitivity band retained for scoring.
- Scope boundary: Comparison, a recorded rationale, freezing, and a declared review sample for larger
  corpora. A labelling interface is out of scope.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add agreement reports over two label sets with fixtures.
- Acceptance gates: Hand-built disagreements are reported exactly. An unresolved disagreement blocks
  the freeze or stays `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`declaration/annotation-review` and `declaration/annotation-settlement` are 1.0.0.
`record/annotation-revision` is 1.0.0, kind `ss-track.annotation-revision`. `result/command`
1.31.0 adds optional `label_review`. The object has no `score` field.

`ss-track annotate compare` reports each differing field as canonical JSON and exits 0 when the
documents can be compared, including when they differ. The annotator id and the label id are not
disagreements. Equal numbers, including `1` and `1.0`, are not a disagreement. Presence means one
document lacks the subject.

`ss-track annotate freeze` writes the frozen label document and the sealed revision. A required
disagreement with no decision is `MANIFEST_INVALID` and writes nothing. A disagreement outside
the review stays `unknown` and does not block. The frozen annotator id is the review authority.
The sensitivity band is the two annotator document hashes. The label hash is the declaration
hash. The revision hash is the record seal.

An unknown frame is visibility `unknown` and geometry `unlocalizable`. Camera motion stays
independent. An unknown class keeps the left class and becomes `identity_ambiguous`. A class and
a mark the pack cannot combine are refused. An unknown motion-event field other than selection
quality drops the event.

`--source` is one video file. A directory is refused. `annotation-sequence-source` owns sequence
labels for validate, compare and freeze.

Current page: [Corpus](../current/corpus.md#annotation-review).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Hand-built disagreements | `test_a_visibility_disagreement_is_reported_exactly`, `test_a_one_pixel_box_move_is_only_that_field`, `test_an_added_instance_is_one_presence_row`, `test_an_integer_and_the_same_float_are_not_a_disagreement`, `test_the_annotator_id_is_not_a_disagreement` | pass: the absent frame lists the box, kind, uncertainty `1.0`, visibility and the event visibility; a one-pixel move is only `geometry.box`; an added instance is one presence row |
| Unresolved blocks or stays unknown | `test_an_unresolved_disagreement_blocks_the_freeze`, `test_a_box_outside_the_sample_stays_unknown_without_a_decision`, `test_a_difficult_disagreement_outside_the_sample_still_blocks`, `test_an_unknown_decision_stays_unknown_and_is_not_a_score`, `test_an_unknown_camera_keeps_the_box` | pass: a required row blocks and names the field; an outside box stays unknown without a decision; a difficult row outside the sample still blocks; an explicit unknown drops the disagreed event and keeps no score |
| CI | `make ci` | pass: 2572 passed, 115 deselected |

No runtime artifact was written under `$DATA_DIR`. The frozen label and revision in the tests
stay in the test temporary directory.

## Audit handoff

- AUD-annotation-review-tools-1, nonblocking: `ss-track annotate compare` and `annotate freeze`
  refuse a directory with `SOURCE_NOT_FOUND`. An ordered image sequence is a source, and its
  identity is `sequence_identity`. Labels on a sequence cannot be compared or frozen. Owner:
  `annotation-sequence-source`, amended in this change so its outcome and acceptance gates name
  compare and freeze as well as validate.
- Dropped, fixed here: an unknown camera-only settlement kept the left camera. The freeze now
  stores `unknown` and leaves the agreed box in place. `test_an_unknown_camera_keeps_the_box`
  covers it.
- Dropped, no work needed: a labelling interface is outside this task.
- Dropped, no work needed: the revision stores both annotator hashes and computes no score.
  [Section 6.1](../../design/spec.md#61-operator-selected-tracking-sot-v2-dev) keeps the score,
  and `sot-suite` and `motion-suite` remain open.
- Dropped, no work needed: `generated-case-labels` now says derive reads the sealed annotation
  revision and the label document whose hash it pins. That task remains open.

## Close or resume

Every gate passed. Current page
[Corpus](../current/corpus.md#annotation-review), records index and plan updated. After the plan
edit, 158 open tasks remain (129 agent, 29 human). The next agent task is
`generated-case-labels`. The next human task is `define-locked-test-policy (optional)`.
`annotation-selection` stays `planned`.
