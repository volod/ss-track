# Generated fixture cases

## Task and scope

- Id / capability: `generated-fixture-cases` / `corpus-provenance`
- State: accepted
- Source: plan task at `78db68c` on branch `st-corpus-provenance`. The working tree was clean.
- Plan counts at start: 70 open (50 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=46`,
  `HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `generated-fixture-cases` and
  `select-development-workload`.
- Accepted task:

```markdown
#### generated-fixture-cases

Failure mechanisms need cheap, repeatable cases that do not count as field evidence.

- Serves: `corpus-provenance` -- [Deterministic cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A recipe generates target absence, moving background, shake, blur, dropped
  frames and short occlusion cases from a parent sequence and seed.
- Scope boundary: The spec section 4.3 initial cases. Fusion perturbations are out of scope.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add versioned transforms that store parent, seed and label transform.
- Acceptance gates: A rerun with one seed is byte-identical. A generated case inherits its parent's
  encounter and split and never counts as a new encounter.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none to the task text. The corpus declaration moved to schema 3, spec section 4.3 gained
  the case structure and labelling rules, and the test plan lists this case as existing behavior.

## Implementation

`ss-track corpus build` now reads generated-case recipes and `corpus stage` and `corpus verify` cover
their bundles. There are no new commands, and `src/ss_track/cli.py` is unchanged. Behavior is in
`src/ss_track/corpus/`:

- `seeded.py` (new): every random value, derived by SHAKE-256.
- `case_model.py` (new): what a transform receives and returns, and two pixel helpers.
- `transforms.py` (new): frame-wide and temporal transforms, the revision table and `prepare_case`.
- `region_transforms.py` (new): absence, moving background and occlusion.
- `recipes.py` (new): strict recipe reading and the record a corpus stores.
- `generated.py` (new): writes one case bundle.
- `staging.py`, `frames.py`, `grouping.py`, `builder.py`: cases in stage and verify, gaps in a frame
  index, case names in the uniqueness rule, and a case count beside the split counts.

Reused rather than repeated: `publish_bundle`, `store_frame` and `require_space` came out of
`bundle_writer.py`, so a case bundle gets the same scratch, publish and space rules as a stream.
`open_frame_bundle`, `read_frame`, `damage` and `_open_for_corpus` serve cases unchanged in meaning.
`Fields.identifier` and `Fields.selection` moved in from `declaration.py` for recipes to share.

Decisions and rejected alternatives:

- **A recipe sits under its parent stream (`AUD-corpus-split-grouping-1`):** membership is then
  structural. A top-level list naming a parent was rejected: it adds a bad-reference failure, and
  nesting means no key exists that could state another split. The audit item ends here.
- **Cases are a separate manifest list:** split, rights and count rules read `streams`, so a case
  cannot be counted by accident. Adding a flag to stream records was rejected, because every reader
  would then have to remember to filter. A case adds its own `generated_case_count`.
- **A case is an ordinary bundle under `frames/`:** modules read one path and `corpus verify` needs
  no second implementation. Recomputing frames on read was rejected: it would make input depend on
  the installed transform at run time rather than on a sealed hash.
- **Recipes live in the corpus version:** spec section 4.1 says so, and a separate command would leave
  evidence the corpus does not name.
- **Transforms run at build too:** a build validates a recipe by running the real transform without
  pixels, so build and stage cannot disagree, and the manifest holds the label transform.
- **SHAKE-256, not `random` or NumPy generators:** Python guarantees only `random()` itself, and
  NumPy's stream policy allows changes. A published hash function has neither problem.
- **NumPy is a new dependency:** a box blur touches every component of every frame, which pure Python
  was estimated, not measured, to do at about one second per 1080p frame. `numpy>=2.1,<3` is justified,
  and only integer arithmetic is used, so its version does not move bytes.
  An FFmpeg filter was rejected, because staging already showed FFmpeg pixels vary by SIMD path.
- **A declared rectangle, not a target:** no labels exist, and the task has no dependency on them.
  One static rectangle covers a moving target if it covers its path. Per-frame boxes were rejected as
  more than these cases need.
- **Overlapping labels lose geometry:** a visible extent is a rectangle minus a rectangle, which is
  not a box. Keeping the stale box would be a confident wrong label.
- **`moving_background` adds `distractor`, not `ignore_region`:** ignoring the region would hide the
  false alarms this case exists to provoke.
- **Labels follow pixels:** a label describes what is shown, so a repeated frame takes the labels of
  the frame it repeats.
- **A repeat is a replaced slot, not an inserted frame:** indices and PTS stay valid and unchanged.
- **Repeats give up `measured`:** that PTS is no longer when those pixels were captured.
- **Each blur frame draws its radius:** a fixed radius would leave the seed unused.
- **Occlusion needs frames on both sides:** without them it is not a short occlusion and tests no
  re-acquisition.

Findings from design review and from undoing safeguards, each with a regression test:

| Finding | Regression test |
| --- | --- |
| A recipe could change nothing and still pass as a perturbation, such as a blur of a uniform clip | `test_a_case_that_changes_no_frame_is_refused_and_leaves_nothing` |
| A repeated frame kept `measured` and its clock evidence, a false claim about those pixels | `test_a_repeated_frame_gives_up_a_measured_capture_time` |
| Halving the noise range survived the behavior tests | `test_noise_reaches_every_value_on_both_sides_of_the_plate` |
| Motionless, one-directional and time-independent sprites survived the behavior tests | `test_a_sprite_moves_one_step_per_frame_in_a_seeded_direction_and_wraps` |
| Blur rounding down survived the behavior tests | `test_blur_rounds_each_average_to_the_nearest_value` |

The blur cumulative sum first used 64-bit values at 122 ms per 1080p frame. 32-bit values cannot
overflow at any supported frame size and took 65 ms, with the golden hash unchanged.

Compatibility: `corpus.yaml` is schema 3, so a schema 2 declaration is `MANIFEST_INVALID`. Corpus
manifests and frame bundles are schema 3, and a schema 2 record is `RECORD_SCHEMA_UNSUPPORTED`; such
a corpus must be rebuilt under a new `corpus_id`. A stream's `bundle_sha256` is unchanged by this task
because its identity block is, and sources need no re-import. Stream records add `width` and `height`,
a `FrameRef` adds `content_frame_index`, a build result adds `generated_case_count`, a split summary
adds the same field, and a stage or verify result adds `transform`. `FRAME_NOT_IN_BUNDLE` now also
covers a gap. `CASE_INVALID` and `TRANSFORM_REVISION_MISMATCH` are new. `pyproject.toml` and `uv.lock`
add NumPy, which resolved to 2.5.4.

Limitations:

- A region and a plate frame are operator claims that nothing checks. A plate showing the target gives
  a false negative interval.
- Label transforms are stored records. No code applies them, because no labels exist.
- One static rectangle per case, and an occluder appears and vanishes in one frame.
- A case perturbs one stream, so the other streams of its encounter stay clean.
- No realism is claimed: sprites are solid squares, and shake is independent per frame.
- A case holds a full copy of its raw frames.
- Nothing checks that a source's terms permit derived frames.
- A case that changes no frame is found at staging, not at build, because that takes pixels.

Current-state page: [Corpus](../current/corpus.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A rerun with one seed is byte-identical | `test_a_rerun_with_one_seed_is_byte_identical`, `test_a_second_process_stages_identical_case_bytes`, `test_a_transform_revision_always_produces_the_same_bytes` | pass, for all seven transforms, across data roots and processes, comparing every file |
| A case inherits its parent's encounter and split | `test_a_case_inherits_its_parents_encounter_group_and_split`, `test_a_malformed_recipe_is_refused[own-split]` | pass, in the corpus manifest and bundle record, and a recipe cannot state otherwise |
| A case never counts as a new encounter | `test_a_case_adds_no_group_encounter_or_stream_to_any_count`, `test_a_case_does_not_change_a_stream_record` | pass, with cases counted on a separate line |
| The six named cases, with duplicated frames from spec section 4.3 | `tests/corpus/test_transforms.py`, `test_transform_recipes.py` | pass, seven transforms on hand-checkable frames |
| Stores parent, seed and label transform | `test_a_case_is_stored_with_parent_transform_seed_and_label_transform` | pass. Limit: label transforms are records until labels exist |
| Versioned transforms | `test_a_stored_case_this_code_cannot_reproduce_refuses_before_any_write`, `test_every_declared_transform_is_pinned` | pass |
| `make ci` | `make ci` | pass on Python 3.12, 446 tests |
| Fuller local gate | `make quality` | pass, coverage 99% |
| Second CI version | `pytest` in a locked Python 3.13 environment | pass, 446 tests. Limit: tests only, not the lint gates |

The rest was a one-off investigation on the final code. Its scripts lived in session scratch space
and were not kept; the regression tests above are the lasting form.

| Investigation | Method | Result and limit |
| --- | --- | --- |
| Visual check | One frame of each pixel transform from `ffmpeg` H.264 at 640x360, viewed as a contact sheet | Each looked as intended, with no wrap, tear or color fault. Limit: one reviewer, one clip |
| Real encoders through the CLI | Six sources in Matroska, MP4 and AVI: H.264, HEVC 10-bit, MJPEG and FFV1 in RGB, gray and 4:4:4, with seven cases each across three splits | 42 cases built, staged and verified. AVI stayed `missing`, and only repeats left `measured` |
| Reproducibility | One corpus of 638 files staged under two hash seeds, NumPy SIMD off, Python 3.13 and NumPy 2.1.3 | One tree hash in all five runs. Limit: SIMD off is a proxy; never run on arm64 hardware |
| Refusals through the CLI | 10 malformed or impossible recipes | Each exited 1 with a structured refusal, no traceback and no corpus written |
| Operational failures | `kill -9` during case staging, a concurrent run, sibling cases swapped, a case swapped with its parent | No partial bundle; the rerun cleared scratch and kept the parent; `STAGING_IN_PROGRESS`; `BUNDLE_CONFLICT` both ways; `verified` once restored |
| Throughput | Four cases of 300 1080p frames over one parent, with and without the cases, on tmpfs on one host | 36.8 s for the cases, about 33 frames per second, 227 MB peak. Verify 4.2 s |
| Test strength | 66 safeguards undone one at a time in a scratch copy, from a passing baseline, naming the test that failed | 65 failed a test. The survivor is equivalent: the mutated path leaves its key unread, so the strict reader still refuses. Rerun with the golden and pinned-stream tests excluded, because those values come from this code: 60 failed, and the five real survivors became the tests above; now 65 again |

## Audit handoff

Every entry is nonblocking and has one owner. `AUD-corpus-split-grouping-1` is resolved above.

- `AUD-generated-fixture-cases-1`: label transforms are stored but never applied. Evidence:
  `label_transform` in each case record. Impact: a case has no scorable labels until they are derived
  from its parent's frozen labels, including box clipping and `out_of_view` after a shift. Owner:
  `generated-case-labels`.
- `AUD-generated-fixture-cases-2`: nothing checks a region or plate frame against labels. Evidence:
  `region_transforms.py` knows no target. Impact: a wrong claim makes a false negative interval, so
  frozen labels should refuse a plate that overlaps the target. Owner: `generated-case-labels`.
- `AUD-generated-fixture-cases-3`: `FrameRef` gained `content_frame_index`. Evidence: `frames.py`.
  Impact: the field must reach the `.proto` definition with this meaning. Owner:
  `event-schema-contract`.
- `AUD-generated-fixture-cases-4`: a corpus manifest does not name a case's bundle hash. Evidence:
  staging is a separate step, as for streams. Impact: a scenario must pin it to fix a case's input.
  Owner: `staged-frame-set`.
- `AUD-generated-fixture-cases-5`: a removed frame has no defined scoring. Evidence: `FrameBundle`
  simply lacks it. Impact: the runner must decide whether it is a scheduled miss or was never
  scheduled, and its exact frame accounting must say so. Owner: `lockstep-runner`.
- `AUD-generated-fixture-cases-6`: nothing yet keeps cases out of field aggregates. Evidence: spec
  section 4.3 requires separate report slices, and the data needed is `generated` on each record.
  Impact: a report must never merge them. Owner: `local-comparison-report`.
- `AUD-generated-fixture-cases-7`: rights never ask whether derived frames are permitted. Evidence:
  `holder`, `basis` and `retention` are not compared. Impact: a license forbidding derivatives would
  pass. Owner: `source-terms-enforcement`.

## Close or resume

Every declared gate passed; the commit is left to the project owner. The task left the plan, and
`g0a-pipeline-run` dropped it as a dependency. No agent task remains in `corpus-provenance`, so that
group left the Agent lane; its human task remains. [Corpus](../current/corpus.md) is updated and its
index entry extended, and this record is indexed in the [records README](README.md). The spec gained
the case structure and labelling rules, and the test plan lists this case as existing behavior.

Plan counts after: 69 open (49 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=45`,
`HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `annotation-contract` and
`select-development-workload`. Capability `corpus-provenance` stays `planned`.
