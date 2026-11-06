# Compression and variable timing cases

## Task and scope

- Id / capability: `compression-and-timing-cases` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `af65ef9`; clean worktree.
- Plan counts at start: 133 open (110 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=104, HUMAN-GATED=13, RUN NEEDED=6. Next agent `compression-and-timing-cases (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### compression-and-timing-cases (optional)

Field video also fails through heavy compression and uneven frame timing, which no generated case
covers.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Recipes generate compression artifacts and variable frame timing from a
  parent and seed.
- Scope boundary: The spec section 4.3 further cases that need no labels. Sensor loss belongs to
  `fusion-generated-fixtures`.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add versioned transforms, pinning the encoder in the compression revision, and
  declare what a timing change does to `timestamp_quality`.
- Acceptance gates: A rerun with one seed is byte-identical, golden hashes pin each revision, and a
  changed PTS never stays `measured`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`src/ss_track/corpus/cases/field_transforms.py` adds revision 1 of `compression` and
`variable_timing`. Both are integer functions of the parent frames, the parameters and a SHAKE-256
seed. An FFmpeg or PyAV encoder was rejected.
[Arm64 reproducibility](0011-corpus-provenance-arm64-reproducibility.md) showed decoded pixels move
with the CPU unless the IDCT is pinned, so a codec would not be a stable case.
`compression` revision 1 is the encoder `block-quant-rgb24-v1`. Each 8x8 block, and any
leftover edge rectangle, becomes its average, rounded half-up to a multiple of that frame's step
and clamped to 0..255. The seed draws the step from 1 to `max_step`. The encoder name and the block
size are constants of the revision. Pixels outside the window stay the parent's, and so does every
presentation time, so a measured parent stays measured.

`variable_timing` keeps every pixel and multiplies the presentation gap that ends inside the window
by an integer from 2 to `max_scale`. The first frame keeps its presentation time. A later frame
that the case does not scale keeps its parent interval and starts from the new time, so the
sequence stays strictly increasing, including frames outside the window. Returning those frames to
the parent's presentation time made the sequence decrease; that is fixed here. The case is
`derived` and stores no capture-clock evidence. A parent whose timestamp quality is `missing`, or a
frame whose presentation time is absent while a gap is scaled, is `CASE_INVALID`. A window that
scales no gap is refused at build. A change of presentation time counts as a change, so variable
timing of a uniform clip is a real case. Compression of a uniform clip that lands on the
quantization grid is still `CASE_INVALID`.

`declaration/corpus` 3.1.0, `record/corpus-manifest` 3.3.0 and `record/frame-bundle` 3.3.0 add the
recipes and the label kinds `compression` and `timing`. Writers still stamp the major. A
declaration stamped schema 3 validates under `declaration/corpus` 3.1.0, and a dataset descriptor
copies that newest minor, so the copied corpus-manifest and frame-bundle contracts are 3.3.0.
The existing `x-rules.time` sentence was left unchanged, because editing it is a major. It remains
true, and the timing label states that a changed presentation time is derived. Current page:
[Generated cases](../current/corpus.md#generated-cases). Specification section 4.3 names both cases.
No new dependency, environment variable or command flag.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Golden hashes pin each revision | `tests/corpus/cases/test_transform_golden.py`, seed `20261101`, `compression` `max_step` 8, `variable_timing` `max_scale` 4 | pass; revision 1 digests `db6fd2df8e6e0048e965590d64edd2e5c78f9699b059cdb95351c2f78fdc4ae3` and `d9d05fdf5e674456796799265f90a55c5d6baabeae8e3ef5b9094f68ec52f3c5` |
| The encoder is part of the revision | `tests/corpus/cases/test_field_cases.py::test_compression_revision_pins_the_block_encoder` | pass; label kind `compression`, encoder `block-quant-rgb24-v1`, block 8 |
| A changed PTS never stays `measured` | `test_a_changed_presentation_time_never_stays_measured` | pass; quality `derived`, no capture-clock evidence, PTS strictly increasing, frames before the window unchanged, later frames shifted, pixels hard-linked |
| A measured clock survives compression | `test_compression_changes_only_the_window_and_keeps_a_measured_clock` | pass; window bytes change, outside frames keep their inodes and PTS |
| A missing presentation time is refused | `test_variable_timing_refuses_a_parent_with_no_presentation_time`, `test_variable_timing_refuses_a_source_with_no_presentation_time` | pass; `CASE_INVALID` at build, and no manifest is written |
| A rerun with one seed is byte-identical | `tests/corpus/cases/test_generated_cases.py` cases `compressed` and `timed` in `every_case`, including `test_a_second_process_stages_identical_case_bytes` | pass; both names are in the second-process comparison |
| `make ci` | `make ci` | pass; 1830 tests |

## Audit handoff

`AUD-compression-and-timing-cases-1`, nonblocking. Label kinds `compression` and `timing` are stored
but not yet applied to frozen parent labels. Evidence: the kinds are in the frame-bundle and
corpus-manifest contracts, and `generated-case-labels` previously said "all seven transforms".
Impact: a scored case of either kind would have no derived labels until that task runs. Owner:
`generated-case-labels`, amended in this change. Its text now names both kinds, states that neither
moves geometry, and states that `timing` records a derived presentation time.

Dropped, each because it needs no work:

- Compression of a uniform color that is already a multiple of the step changes no frame. That is
  the existing `CASE_INVALID` rule, and `test_compression_of_a_uniform_clip_changes_no_frame` covers
  step 1.
- The published host table still reports 78 bundles and 879 frames. That measurement counted seven
  transforms. The fixture now includes every transform. The new ones are integer and pinned by the
  golden hashes, so this change claims no new cross-architecture result.
- The frozen `x-rules.time` sentence was not edited. Changing existing `x-rules` text is a major.
  The sentence stays true, and the timing label plus specification section 4.3 state the new rule.

## Close or resume

Gates passed. Current page, specification section 4.3, contracts page, records index and the plan
are updated.
Plan counts after: 132 open (109 agent, 23 human). Statuses: BLOCKED BY HUMAN=10, CLEAR=103,
HUMAN-GATED=13, RUN NEEDED=6. Next agent `label-driven-cases (optional)`; next human
`define-locked-test-policy (optional)`. `corpus-provenance` stays `planned`.
