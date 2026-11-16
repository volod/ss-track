# Generated case labels

## Task and scope

- Id / capability: `generated-case-labels` / `annotation-selection`
- State: accepted
- Source: plan task at `871f6915ac954323fa591b8fc08769b2bb7e534d`; the tree was clean.
- Plan counts at start: 157 open tasks (128 agent, 29 human). Next agent
  `generated-case-labels`. Next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### generated-case-labels

A generated case cannot be scored until its labels follow its pixels, and a wrong region must not
create a false negative.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track annotate derive` gives each generated case a hashed label revision
  from its parent's frozen labels and stored label transform, including a `track_status` case.
- Scope boundary: Every stored label transform: region status, translation with clipping and
  `out_of_view`, frame maps, `scale`, `compression`, `timing` and `track_status`. `scale` divides
  geometry, uncertainty and plausible extent by its integer factor and clips to the output frame.
  It turns a box under the pinned pack's minimum box extent into `point_only`, and a target under
  its minimum point extent into
  `unlocalizable`. `compression` and `timing` do not move geometry. `timing` records that
  presentation time is `derived`. `track_status` lists one role per case-window frame: `unknown`
  when that frame has no box, `region` for a painted rectangle, `shift` when the frame leaves the
  view, `reentry` when the box is back, and `unchanged` when the box stays. `unknown` stays
  `unknown` and is never `absent`. A `shift` frame is `out_of_view`. A `reentry` frame records
  re-entry. A `region` role names the painted rectangle: the occluder, the removed box, or the
  distractor copy. The target box on a distractor frame is not that rectangle and stays as the
  parent labeled it. The plate check applies to each box `moving_removal` replaces. A track case
  whose boxes or `label_revision` do not match that instance in the parent's frozen revision is
  refused. Derived labels are never edited by hand.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`,
  `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Read the parent's sealed annotation revision and the label document whose hash
  it pins. Apply each label-transform kind to those labels, then check plates and regions against
  those labels. Apply each `track_status` role to the frame it names.
- Acceptance gates: Hand-computed labels match for every transform, including `scale`,
  `compression`, `timing` and `track_status`. A scaled box under the pack's minimum extent is
  `point_only`, never a box. A plate showing a target inside its region is refused, and a target
  the region does not fully cover stays `unknown`. A frame with no scorable box stays `unknown`.
  The same plate check applies to each box `moving_removal` replaces. A track case whose boxes or
  `label_revision` do not match that instance in the parent's frozen revision is refused. A parent
  with no frozen labels leaves its cases unscorable, never scored as zero.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`ss-track annotate derive --corpus <id> --pack <path>` reads each parent's frozen revision from
`$DATA_DIR/corpus/<corpus-id>/labels/<stream-id>/` and writes the case under `labels/<case-id>/`.
A missing parent revision leaves the case `unscorable` with reason `no_frozen_labels`. The command
status stays `derived`. That row has no hashes and no score.

The new record is `record/derived-label` 1.0.0, kind `ss-track.derived-label`. It pins the parent
revision seal, the parent label hash and the canonical hash of the stored label transform.
`label_revision` on a track case is that parent seal, `manifest_sha256` of
`record/annotation-revision`. `result/command` 1.32.0 adds status `derived` and optional
`label_derivation`. Neither object has a score.

Checks finish before any case is written. A plate whose painted region fully contains a scoring
target on `plate_frame` is `MANIFEST_INVALID`, including each box `moving_removal` replaces. A
target the region only overlaps stays `unknown`. A track whose boxes or revision do not match the
frozen instance is refused the same way.

Current page: [Corpus](../current/corpus.md#derived-case-labels).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Hand-computed labels for every transform, including scale, compression, timing and track roles | `pytest tests/annotate/test_derive_labels.py tests/annotate/test_derive_track.py` | pass |
| A box under the pack minimum is `point_only`; under the point minimum it is `unlocalizable` | `test_a_box_below_the_minimum_becomes_a_point_then_unlocalizable` | pass |
| A covered plate is refused; a partial cover stays `unknown`; a frame with no box stays `unknown` | `test_overlap_stays_unknown_and_a_covered_plate_is_refused`, `test_unchanged_reentry_shift_and_unknown` | pass |
| A track revision or box that is not the frozen instance is refused | `test_a_track_that_is_not_the_frozen_instance_is_refused` | pass |
| No frozen parent is unscorable and not zero; a later refusal keeps written files | `pytest tests/annotate/test_derive_command.py` | pass |
| Full gate | `make ci` | pass: 2640 passed, 120 deselected |

## Audit handoff

- Dropped, no work needed: a moving-background case does not gain sprite instances. The stored
  `region_status` record has no sprite box. Inventing those boxes would be a new transform revision.
- Dropped, no work needed: derive does not decode the case. The task checks the stored transform
  against the frozen labels. The label header supplies the frame space.

## Close or resume

Every gate passed. Current page [Corpus](../current/corpus.md#derived-case-labels), records index
and plan updated. After the plan edit, 156 open tasks remain (127 agent, 29 human). The next
agent task is `annotation-sequence-source`. The next human task is
`define-locked-test-policy (optional)`. `annotation-selection` stays `planned`.
