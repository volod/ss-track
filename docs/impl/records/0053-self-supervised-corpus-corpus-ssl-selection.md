# Corpus SSL selection

## Task and scope

- Id / capability: `corpus-ssl-selection` / `self-supervised-corpus`
- State: accepted.
- Source: plan task; starting HEAD `579988c` on branch `st-06-self-supervised-corpus`, clean tree.
- Plan counts at start: 125 tasks, 102 agent and 23 human. Next agent `corpus-ssl-selection`; next
  human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-ssl-selection

Ranking only known objects misses rare, tiny or unfamiliar birds and background negatives.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Research: yes
- Dependencies: none.
- User-visible outcome: Operators get ranked, diverse candidate windows plus reproducible independent
  audit samples from the eligible pool.
- Scope boundary: Frozen pretrained CLIP and DINOv2 backbones pinned by revision, diversity,
  uncertainty, motion and seeded random sampling; an SSL-adapted checkpoint only with a manifest
  naming development-only training sources ([adapted models](current/corpus/sibling-integration.md#adapted-models));
  no claim that a score is a label.
- Data and artifact paths: `contracts/`, `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Implement a model-agnostic selection seam over the feature rows
  [`discover run`](current/corpus/discovery-runs.md) writes, replacing its `unranked` selection,
  and evaluate sibling embeddings against a simple uniform baseline, retaining each sampling
  probability, seed and exclusion reason in the
  [discovery records](current/corpus/discovery-records.md). A stream in the locked split, which
  the adapter reads like any other, is excluded from selection as `operator_excluded` unless the
  locked-test custodian policy allows it. The embedders centre-crop to 224
  pixels, so add tiled or uncropped coverage and measure it on fixtures with small targets near the
  frame edge; a tiled mode adds its crop name and grid to `record/discovery-run` as a minor.
- Acceptance gates: Fixtures reproduce selection and independent audit membership; negatives,
  confusers and unseen candidates can enter the audit sample; edge and small-target coverage is
  reported; unavailable features are explicit. A negative model comparison is valid and `make ci`
  passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

A discovery plan may now name a selection and tiled extractors. A run with a selection scores every
candidate, ranks pool windows within the budget under its method, and states every score, decision,
probability and seed; `discover verify` recomputes them from the feature rows and staged frames.
Current state: [discovery runs](../current/corpus/discovery-runs.md#selection), with the
[discovery records](../current/corpus/discovery-records.md),
[sibling integration](../current/corpus/sibling-integration.md), contracts and corpus pages and
specification section 4.1a updated.

New package `corpus/selection/`: `catalog.py` (score names, methods, revisions), `motion.py`,
`embeddings.py`, `scores.py`, `methods.py` and `apply.py`, the one `score_and_select` that both
`discover run` and `discover verify` call. New `corpus/siblings/tiles.py` (tile geometry, crop,
coverage) and `corpus/siblings/worker_env.py`, which takes the worker's interpreter and environment
out of `embedding.py`; `embedding.py` sends tiles and returns one set of rows per tile position. New
in `corpus/discovery/`: `result.py` (the command result, out of `run.py`) and `selection_check.py`.
`plan.py` reads `tiles` and `selection`; `pool.py` no longer writes a placeholder selection.

Contracts frozen: `declaration/discovery-plan` 1.1.0 (`selection`, an extractor's `tiles`),
`record/discovery-run` 1.2.0 (crop `tiled`, an extractor's `tile`) and `result/command` 1.16.0
(`selection`, `unavailable_scores`, `coverage`). No dependency changed; `pyproject.toml` lists
`ss_track.corpus.selection`.

Decisions:

- Each tile position is its own run extractor (`<id>.r<row>c<column>`), so `record/feature-rows`
  keeps one row per frame and needs no change; its size rule sits in the root `x-rules`, which a
  minor cannot change.
- Tiles are square and evenly spaced from edge to edge, so the embedder's own centre crop removes
  nothing and the union always covers the frame. A grid whose tile exceeds the short side, or a
  non-square model input, is refused rather than silently cropped.
- Scores read frozen backbones only. Deviation compares a window with its own stream's background,
  which suits fixed cameras. Instability, the frame-to-frame change of a window's representation,
  stands in for uncertainty, since a backbone without a classifier has none to report. Motion is the
  most changed 16-pixel block, partial edge blocks included, in integer luma, so it is exact on any
  machine.
- `uniform` reads no score, so its baseline is not narrowed by unavailable features, and its rank
  key names the method, so a selection seed equal to the audit seed still draws independently.
- `ssl-diverse` is deterministic: percentile ranks make scores of different units comparable, and a
  fixed half-weight similarity penalty keeps near-copies of a pick out of the budget. Its
  probabilities are therefore 1 and 0; the independent audit sample measures what it misses.
- Locked-split streams are `operator_excluded` under every ranking method: no custodian policy
  exists to allow them. They stay in the audit pool, since audit eligibility depends only on origin.
- Recomputation lives in `discover verify`, not the record reader, so records written by another
  tool with other methods still read; verifying such a run states that this ss-track cannot
  reproduce it.
- Rejected: a classifier or CLIP text prompts for uncertainty, which would rank known objects and
  is what the task sets out to avoid; letterboxing the whole frame, which shrinks small targets
  further; and score-proportional random selection, which the uniform baseline and audit sample
  make unnecessary for now.

## Acceptance evidence

Run: `$DATA_DIR/self-supervised-corpus/selection-eval-20261107/`. Six synthetic 640 by 360 clips
with known target windows (`media/truth.json`) were staged as one corpus and run with the pinned
CLIP ViT-B/16 and DINOv2 ViT-B/14 extractors, each centre-cropped and in a 4 by 2 grid, on this
host's CPU from a scratch environment holding ss-perception `v0.2.0` (`12cb086`), torch 2.15.0+cpu
and open_clip 4.2.1. `results/scripts/` holds the clip generator and the replay evaluation;
`results/evaluation.json` its output.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Fixtures reproduce selection | `test_selection_run.py` (retry `unchanged`, verify recomputes, a changed decision, score, seed or unknown method refused); `test_methods.py`; real `eval-uniform` retry and `discover verify` of both real runs | pass |
| Fixtures reproduce independent audit membership | `test_selection_leaves_the_audit_sample_where_the_unranked_run_drew_it` | pass: unranked, uniform and diverse runs draw identical audit samples |
| Negatives, confusers and unseen candidates can enter the audit sample | same test (sampled windows include unselected and excluded ones); real run's audit sample | pass: 12 sampled held 3 targets and 2 each of branch, flicker and empty sky |
| Edge and small-target coverage is reported | `coverage` in the command result (`test_a_tiled_extractor_is_one_run_extractor_per_tile`, `test_tiles.py`); `results/evaluation.json` | pass: centre crop shows 56% of a 16:9 frame at scale 0.62, 4 by 2 tiles all of it at 1.24. CLIP deviation AUC for edge targets 0.15 centre-cropped, 0.94 tiled; tiny edge target 0.30 and 0.83 |
| Unavailable features are explicit | `test_a_score_a_window_cannot_support_is_unavailable_with_its_reason`; `unavailable_scores` in the result | pass: `window_too_short` and `extractor_failed`, counted per score |
| Locked-split streams excluded | `test_a_diverse_plan_ranks_pool_windows_outside_the_locked_split`, `test_a_locked_stream_is_excluded_but_counts_against_nothing` | pass: `operator_excluded`, still audit-eligible |
| Model comparison against a uniform baseline (negative valid) | `results/evaluation.json` | measured on fixtures: at budget 12 of 48 windows, tiled CLIP deviation with motion found 11 of 12 targets, uniform 4 (3 expected), centre-crop deviation 4, motion alone 4 with 8 branch picks. Synthetic clips only; no claim for real footage |
| Earlier runs unaffected | `discover verify` of the four `adapter-run-20261107` runs | pass: all verify with the recompute, so the `unranked` path is unchanged |
| Real-release defect probes | `SST_PERCEPTION_PYTHON=... pytest tests/corpus/siblings/test_sibling_defects.py` | pass: 7 of 7 |
| Resources | `results/run-*.time` | measured: 10 min 45 s and 1.56 GB peak for 3,456 embedded images; uniform 1.1 s; verify 1.3 s; run directory 9.6 MB. GPU not measured |
| Contract evolution | `make lint-contracts` | pass: three minors, 0 findings |
| Documentation | `make lint-doc-links`, `make lint-spec-plan`, `make lint-md` | pass, 0 findings each |
| `make ci` passes | `make quality` (CI checks, tests under coverage, Markdown lint, build) | pass: 2158 passed, 7 skipped (the real-release probes without `SST_PERCEPTION_PYTHON`, run separately above); coverage 93.98% |

## Audit handoff

Reviewed scope: the new and changed modules, the three contract minors, tests, documentation and
the real run.

- `AUD-corpus-ssl-selection-1`: the audit sample, which depends only on origin, draws from locked
  groups' strata, so a reviewer could be shown locked footage. Nonblocking: nothing is reviewed
  yet. Owner: `corpus-review-and-freeze`, whose scope now states that review offers no such window
  without the custodian policy.
- `AUD-corpus-ssl-selection-2`: verification compares recomputed scores and the `ssl-diverse`
  similarity exactly, and was checked only on this host. Floating-point differences on another CPU
  could flip a near-tie. Owner: `corpus-scale-pilot`, whose execution path now verifies on a second
  host and quantizes the similarity under a new revision if a tie flips.
- `AUD-corpus-ssl-selection-3`: background deviation compares a window with its own stream, so a
  target present for a whole stream is its background, and motion ranks confusers such as moving
  foliage high. Owner: `corpus-selection-evaluation`, whose execution path now reports misses and
  confusers by kind against the uniform run of the same pool.
- `AUD-corpus-ssl-selection-4`: a 4 by 2 grid costs eight times the embedding compute. Owner:
  `corpus-scale-pilot`, which now chooses the grid from measured cost and scale.
- Dropped: the selection evaluation used synthetic clips. Real-footage evaluation is the stated
  scope of `corpus-selection-evaluation`, which needs no amendment for it.
- Dropped: no change is needed in ss-video or ss-fusion. Tiling happens in ss-track before the
  unchanged embedder, whose centre crop leaves a square tile whole.
- Fixed in this change: `AUD-corpus-video-index-adapter-2` (locked streams) and `-4` (nothing
  ranked) are resolved.

## Close or resume

Every gate passed. The [discovery runs](../current/corpus/discovery-runs.md) page gains tiled
coverage, selection and the measured selection; the discovery records, sibling integration,
contracts and corpus pages and specification section 4.1a are updated. The task is removed from the
plan; `corpus-review-and-freeze` and `corpus-selection-evaluation` drop it from their dependencies.
Plan counts moved from 125 (102 agent, 23 human) to 124 (101 agent, 23 human). The next agent task
is `corpus-group-and-leakage-review`; `self-supervised-corpus` stays planned.
