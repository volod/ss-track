# Track-following generated cases

## Task and scope

- Id / capability: `label-driven-cases` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `f01e8d0`; clean worktree.
- Plan counts at start: 132 open (109 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=103, HUMAN-GATED=13, RUN NEEDED=6. Next agent `label-driven-cases (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### label-driven-cases (optional)

One static rectangle cannot follow a moving target, and an occluder that appears in one frame is
unlike a real crossing.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: generated-case-labels.
- User-visible outcome: Recipes take a target's frozen track to generate a crossing occluder, a
  moving removal, a similar distractor and out-of-view and re-entry intervals.
- Scope boundary: Per-frame boxes from one frozen label revision, in a new transform revision. No
  realism claim.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add a track input to the region transforms and derive labels through
  `generated-case-labels`.
- Acceptance gates: A rerun with one seed is byte-identical, and the case's bundle hash covers the
  label revision. A hand-audited occluder covers the target exactly in its declared frames, and a
  frame with no scorable box stays `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: `generated-case-labels` now names `track_status`. The open task's scope, execution
  path and acceptance gates state the roles `unknown`, `region`, `shift`, `reentry` and
  `unchanged`, that `unknown` stays `unknown`, that a shift is `out_of_view`, that re-entry is
  recorded, that a distractor entry names the copy, that the plate check covers each removed box,
  and that boxes or `label_revision` which do not match the parent's frozen instance are refused.
  The rest of that task is unchanged. Amended in this change because the stored transform is not
  applied until that task, and the user asked to update the plan.

## Implementation

`src/ss_track/corpus/cases/track_transforms.py` adds revision 1 of `crossing_occluder`,
`moving_removal`, `similar_distractor` and `out_of_view`. `track_labels.py` builds the
`track_status` record. The boxes are recipe parameters: `label_revision`, `instance_id` and
`track`. Annotation is not built, so this task does not read a label file and does not implement
`annotate derive`. The bundle hash covers the revision because both `recipe.parameters` and
`label_transform` are inside the case identity.

`crossing_occluder` draws one of four axis directions and one full-frame texture. On `cover` the
painted rectangle is the box. Other window frames stand one pixel farther from the nearest covered
frame. A rectangle fully outside the frame leaves that frame unchanged. `moving_removal` copies
each box from `plate_frame` and adds seeded noise. `similar_distractor` copies the box to the
first seed-ranked side that shares an edge and fits. `out_of_view` draws one edge and shifts by
the smallest amount that puts the box outside it. A later frame that still has a box is `reentry`
and keeps its pixels. A window frame with no box is `unknown` and keeps its pixels. `cover` and
`outside` must sit strictly inside the case window.

`camera_shake` and `out_of_view` share `shift_frame`. The `camera_shake` golden hash is unchanged.
`Region.fits` refuses a rectangle with a negative origin, which the declaration schema already
refused. Current page: [Generated cases](../current/corpus.md#generated-cases). Specification
sections 4.2 and 4.3 state the rules.

`declaration/corpus` 3.2.0, `record/corpus-manifest` 3.4.0 and `record/frame-bundle` 3.4.0 add the
recipes. The record contracts also add `track_status`. Writers still stamp the major. A declaration
stamped schema 3 validates under `declaration/corpus` 3.2.0, and a dataset descriptor copies that
newest minor, so the copied corpus-manifest and frame-bundle contracts are 3.4.0. Recipe
`label_revision` is `restricted` on records. `instance_id` is `public`. Box geometry and the
label-transform fields are unmarked, as the sibling region and label kinds are. No new dependency,
environment variable or command flag.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A rerun with one seed is byte-identical | `tests/corpus/cases/test_generated_cases.py` cases `crossing`, `removal`, `distractor` and `exited` in `every_case`, including `test_a_second_process_stages_identical_case_bytes` | pass; all four names are in the second-process comparison |
| The bundle hash covers the label revision | `tests/corpus/cases/test_track_cases.py::test_the_bundle_hash_covers_the_label_revision` | pass; two `crossing_occluder` cases, seed 5, same pixels, different `label_revision`, and each `bundle_sha256` equals `bundle_hash(identity)` |
| A hand-audited occluder covers the target | `test_the_occluder_covers_the_target_exactly_on_declared_frames` | pass; cover frames paint the box, and pixels outside the box stay |
| A frame with no scorable box stays `unknown` | `test_a_frame_with_no_scorable_box_stays_unknown` | pass; role `unknown` and pixels unchanged, for the crossing and the other three transforms |
| Golden hashes pin each revision | `tests/corpus/cases/test_transform_golden.py`, seed `20261101` | pass; revision 1 digests `fb80a80f74dcf71ce098af044acca8dfa5b28023bddc0c8873b91349a8f67796`, `b57680ac3f1b04216d355ab90309c49c7b198ffd0aeb156f35fe295d7b3b75fe`, `ddcfc4ecdd1dd963645b1271b88ff7c284c541f4f4b7b121f0a0dcd069cfcd3c` and `1d145c3bb40d095479c18a135baba9543d5ab345904e3166ee805ab8e284039b` |
| `make ci` | `make ci` | pass; 1864 tests |

## Audit handoff

`AUD-label-driven-cases-1`, nonblocking. `track_status` is stored and hashed, and nothing applies
it to frozen parent labels. Evidence: the kind is in the frame-bundle and corpus-manifest
contracts, and `annotate derive` does not exist. Impact: a scored track case would have no derived
labels until that task runs. Owner: `generated-case-labels`, amended in this change. Its text now
names the five roles, the plate check on each removed box, the distractor copy, and the refusal
when the boxes or `label_revision` do not match the parent's frozen instance.

Dropped, each because it needs no work:

- An `out_of_view` shift that changes no pixel, such as a uniform frame, is the existing
  `CASE_INVALID` rule that a case must change pixels or presentation time.
- Preview does not outline a `track_status` case. The case carries no operator rectangle, which
  specification section 4.3 states, so there is no rectangle for the sheet to draw.
- The published host table still reports 78 bundles and 879 frames. That measurement counted seven
  transforms. The fixture now includes every transform. The new ones are integer and pinned by the
  golden hashes, so this change claims no new cross-architecture result.

## Close or resume

Gates passed. Current page, specification sections 4.2 and 4.3, contracts page, test plan,
records index and the plan are updated.
Plan counts after: 131 open (108 agent, 23 human). Statuses: BLOCKED BY HUMAN=10, CLEAR=102,
HUMAN-GATED=13, RUN NEEDED=6. Next agent `near-duplicate-detection (optional)`; next human
`define-locked-test-policy (optional)`. `corpus-provenance` stays `planned`.
