# Discovery runs

`ss-track discover run` writes one [discovery run](discovery-records.md) over a staged corpus
version from an operator's plan. It embeds staged frames with pinned ss-perception extractors in a
separate process, turns ss-video matches into candidate windows of ss-track frames, tiles every
bundle into pool windows and draws the independent audit sample. A plan with a selection then
scores every candidate and ranks pool windows under its method ([selection](#selection)).
`ss-track discover verify` checks a written run against the corpus version it read and recomputes
its scores and selection. The
[adapter record](../../records/0052-self-supervised-corpus-corpus-video-index-adapter.md) and the
[selection record](../../records/0053-self-supervised-corpus-corpus-ssl-selection.md) hold the
decisions and acceptance evidence.

A candidate is a proposal, a feature row describes pixels and a score ranks windows for review.
None is a label, and a run authorizes no source. A run's feature rows also feed the
[leakage review](leakage-review.md), which compares stream backgrounds across groups.

## Commands

```bash
export SST_PERCEPTION_PYTHON=/path/to/pinned-env/bin/python
ss-track discover run --plan plan.yaml
ss-track discover verify --run-id discovery-1
```

`SST_PERCEPTION_PYTHON` names the interpreter of the pinned ss-perception environment. ss-track
never guesses it, and a plan without extractors does not need it. Each command logs one JSON record:

```json
{"status": "written", "run_id": "discovery-1", "corpus_id": "pilot-v1",
 "manifest_sha256": "...", "manifest_path": ".../self-supervised-corpus/discovery-1/run.json",
 "inventory_count": 2, "candidate_count": 35, "feature_row_count": 240,
 "hint_sources": [{"hint_source_id": "ss-video-1", "read": 20, "mapped": 16,
                   "unmapped": [{"reason": "empty_slot", "count": 4}]}],
 "selection": {"method": "ssl-diverse", "budget": 12, "selected": 12,
               "excluded": [{"reason": "operator_excluded", "count": 8}]},
 "unavailable_scores": [{"score_id": "clip-b16.instability", "reason": "window_too_short",
                         "count": 2}],
 "coverage": [{"extractor_id": "clip-b16", "covered_fraction": 0.5625, "scale": 0.207407}]}
```

`selection` counts what selection decided and why windows were excluded; `unavailable_scores`
counts each score a window could not have, by reason. `coverage` states, for each extractor, the
least share of a frame's area its model input showed over the run's streams, and the least scale
at which it saw a target: `scale` times a target's width in frame pixels is its width in the model
input. The same plan over the same staged frames writes the same bytes, so a retry reports
`unchanged`. Another plan under a used run id is `CORPUS_CONFLICT`. `verify` reports `verified`
with the same fields.

## Plan

`declaration/discovery-plan` 1.1.0 states one run. Extractors, weights and hint files are listed in
ascending id order:

```yaml
schema_version: 1
run_id: discovery-1
corpus_id: pilot-v1
source_approval: {owner: project owner, reference: approval-2026-001}
pool: {window_frames: 8}
audit: {seed: 7, sample_size: 2}        # windows drawn per encounter group
embedding:                              # optional
  package: {name: ss-perception, commit: 12cb0861af8f6ae6562d2cf5211547e284c5b40d}
  frame_stride: 1                       # embed every frame_stride-th frame of each bundle
  extractors:
  - {kind: openclip, extractor_id: clip-b16, model: ViT-B-16, pretrained: openai,
     device: cpu, batch_size: 16, dimensions: 512,
     weights: [{name: timm/vit_base_patch16_clip_224.openai,
                revision: 977e3dd0ec55ab8da155f2fbeb6b5f54948b6e3d,
                sha256: 4b8699299b1e8997753c64b052ba32031449d5d853f55a039148560ee02b820f,
                size_bytes: 598516980}]}
  - {kind: dino, extractor_id: dino-b14, model: dinov3_vitb14,
     device: cpu, batch_size: 16, dimensions: 768,
     weights: [{name: "facebookresearch_dinov2_main:dinov2_vitb14_reg4_pretrain.pth",
                revision: "tree-sha256:71fce3dad7f39787df390e06fdc478bc92895441e7886adefce9f164f3f46315",
                sha256: 73182a088cf94833c94b1666d1c99e02fe87e2007bff57b564fb6206e25dba71,
                size_bytes: 346393545}]}
hints:                                  # optional; paths relative to the plan
- {hint_source_id: ss-video-1, file: hints.yaml}
selection:                              # optional; absent, the run ranks nothing
  {method: ssl-diverse, budget: 12, score_ids: [clip-b16.deviation, motion]}
```

`declaration/discovery-plan` 1.1.0 adds `selection` and an extractor's `tiles`. An extractor with
`tiles: {columns: 4, rows: 2}` embeds square tiles instead of whole frames
([tiled coverage](#tiled-coverage)).

`source_approval` is required on every plan. ss-track cannot tell fixture media from real sources,
so it cannot refuse only real-source runs without it. The run records the approval in
`record/discovery-run` 1.1.0. A plan without it is `MANIFEST_INVALID`.

A weight `revision` is a Hugging Face snapshot commit, or `tree-sha256:` and the digest of the
torch.hub code directory, whose archive records no commit. The contract refuses a branch name. To
pin a new weight, run once with a placeholder: the `EXTRACTOR_UNPINNED` refusal lists the found
name, revision, hash and size, which the owner reviews before copying into the plan.

## Hint files

`declaration/video-hints` 1.0.0 holds what an ss-video index returned, joined to the indexed file's
hash, and the facts that decide the slot rule:

```yaml
schema_version: 1
project: ss-video
commit: 703e3c943dbc960a16cbc859680172c5a7ba5255
ffmpeg_version: 8.0.1-3ubuntu2+esm5
sample_rate: 5/1                        # SAMPLE_FPS_MAX
matches:
- {file_sha256: <processed_files.file_hash>, t_sec: 0.6}
```

ss-video query results carry a random `video_id`, not the hash, so the operator joins each match
to `processed_files.file_hash`. ss-video has no export that does this; see
[sibling integration](sibling-integration.md#interfaces). A match becomes a `sibling_time` window
in each stream whose source has that hash when its slot's frames lie whole inside the stream's
bundle ([frame mapping](sibling-integration.md#frame-mapping)). Repeats name one window. Every
other match is counted under one reason, in the run's hint source and the command result:

| Reason | Meaning |
| --- | --- |
| `no_hash_join` | No stream of the corpus version has a source with that hash |
| `not_on_slot` | `t_sec * sample_rate` is not within 1e-6 of a whole sample index |
| `multi_stream_source` | The source holds more than one video stream, and ffmpeg samples its default one |
| `missing_timestamps` | The pinned source record has no time base or a missing PTS |
| `empty_slot` | No frame falls in the slot; the sample repeats the previous slot's frame |
| `slot_out_of_range` | The slot lies after the source's last frame |
| `outside_bundle` | The slot's frames are not all inside the stream's bundle |

A sibling window is always audit `ineligible`: a kept keyframe has no inclusion probability.

## Embedding worker

ss-track runs `src/ss_track/corpus/siblings/perception_worker.py` as
`$SST_PERCEPTION_PYTHON -I perception_worker.py`, one process per extractor, from an empty
temporary working directory. The script imports nothing from ss-track, and ss-track never imports
the sibling. Its environment is explicit: `PATH`, `HOME`, the Hugging Face and torch cache
variables and `CUDA_VISIBLE_DEVICES` are forwarded; the sibling settings (`DEVICE`, `USE_FP16=false`,
`OPENCLIP_MODEL`, `OPENCLIP_PRETRAINED`, an empty `DINO_CHECKPOINT`, and `DATA_DIR` and
`SUP_CHECKPOINT_DIR` in the empty directory) are set; caches are offline. Nothing else of the
operator's environment reaches it.

The protocol is one JSON line per message followed by the raw bytes it announces. ss-track sends
the plan's package and extractor, and the worker answers with what it loaded. ss-track compares
that with the plan: package name and commit, every weight's name, revision, hash and size,
architecture, device type and row length. It then sends each bundle's frames at the plan's stride
in batches of `batch_size`, never crossing a stream, each frame as packed `rgb24` with its frame
index and hash. The worker checks each frame's hash and returns one float32 row per frame. ss-track
accepts a batch only when the worker echoes the keys it was sent, with finite unit rows of the
stated length. Each answer has a 900 s deadline. A worker that stops, hangs or answers short is
killed and refused with the tail of its standard error.

The guards neutralise the defects the [sibling study](sibling-integration.md#reproducibility)
found in the pinned release. `tests/corpus/siblings/test_sibling_defects.py` probes the real
environment when `SST_PERCEPTION_PYTHON` is set, and fails once a defect is gone. `make test` and
`make coverage` load `.env` and use an executable at
`$DATA_DIR/cache/ss-perception-probes/bin/python` when no interpreter is specified. Those probes are
in the external test group, so `make ci` does not run them. The environment must contain the pinned
sibling and its dependencies; these workflows never install it. Without either interpreter the seven
real-release probes remain skipped under `make test`, while the fake-sibling guard tests still run.
The probes simulate unavailable CUDA and a tiny DINO backbone, so they need neither a GPU nor cached
model weights. The [task record](../../records/0060-adhoc-sibling-defect-test-skips.md) contains the
host verification and regression evidence:

| Defect | Guard | Refusal |
| --- | --- | --- |
| Settings import loads `.env` files and adds variables | Empty working directory; the worker refuses opening `.env` or `.env.local` anywhere, and values ss-track set must come back unchanged | `EXTRACTOR_UNPINNED` |
| torch.hub writes download lines on standard output | Descriptor 1 moves to standard error before any import; the protocol keeps a copy | none needed |
| `DINO_CHECKPOINT` or `active_checkpoint.txt` loads unrecorded; a missing file keeps base weights | A set `DINO_CHECKPOINT` in the operator's environment, or any configured checkpoint in the worker | `EXTRACTOR_UNPINNED` |
| `resolve_device` falls back to the CPU; CUDA out-of-memory moves the model to the CPU | Model device checked after loading and after every batch | `EXTRACTOR_INCOMPATIBLE` |
| Weights resolve from `main` | Network connections refused; every loaded weight file named by snapshot commit or hub tree digest and matched to the plan | `EXTRACTOR_UNPINNED` |

Mixed precision is refused: the adapter records float32 rows only.

## Records written

A run directory holds the [discovery records](discovery-records.md) and, per extractor and stream,
`features/<extractor-id>/<stream-id>.json` (`record/feature-rows` 1.0.0) beside
`<stream-id>.f32`. The record keys row `i` by frame index and frame hash and seals the vector file
by SHA-256 and size; the file holds row `i` as little-endian float32 values. The run's
`feature_rows` lines seal each record. `read_discovery` checks each vector file's hash and that
every value is finite. `verify_discovery` also checks that the rows name exactly the bundle's frames
at the stride, by their sealed hashes, and recomputes every sibling window from the stream's pinned
source record by the slot rule.

A plan without a selection writes the `unranked` method, budget 0 and no scores: every window is
`not_selected` with probability 0. The audit sample is `stratified_fixed_size` with one stratum per
encounter group: each pool window ranks by the SHA-256 of the seed, group, stream and candidate id,
and the lowest `min(sample_size, windows)` are drawn. The rank is the same in any language and
Python version, and selection never moves it: runs with the same pool and audit seed draw the same
audit sample whatever they select.

## Tiled coverage

The embedders scale a frame's short side to 224 pixels and keep the centre, so a 16:9 frame loses
about a fifth of its width on each side and a small bird shrinks with the whole frame. An extractor
with `tiles: {columns: C, rows: R}` cuts each frame into C by R square tiles of side
`S = max(ceil(W / C), ceil(H / R))`, the left edge of column `c` at `floor(c (W - S) / (C - 1))`
and the top edge of row `r` likewise, so the tiles cover the frame. A square tile passes through the
embedder's centre crop whole, and a target in it is `224 / S` times its frame size instead of
`224 / min(W, H)`. A 1920 by 1080 frame in a 4 by 2 grid gives tiles of 540 pixels, twice the scale
of the centre crop, at eight times the compute.

Each tile position is its own extractor of the run, `<extractor_id>.r<row>c<column>`, with crop
`tiled` and its `tile` in `record/discovery-run` 1.2.0, and its own feature records keyed by the
frame each tile was cut from. One worker loads the model once; each batch holds one tile position
of `batch_size` consecutive frames, so rows are reproducible from the plan. A grid whose tile side
exceeds a stream's shorter side, or a model with a non-square input that would crop each tile, is
`EXTRACTOR_INCOMPATIBLE`.

## Selection

A plan's `selection` makes the run compute every score below for every candidate, pool and sibling,
and rank pool windows within `budget`. A score that a window cannot support is `unavailable` with
its reason, never a guessed value.

| Score | Method | Value |
| --- | --- | --- |
| `motion` | `block-difference` | The largest mean absolute BT.601 luma change of any 16 by 16 block, partial edge blocks included, between consecutive frames of the window. A one-frame window has none |
| `<extractor_id>.deviation` | `background-deviation` | `1 - cos` between the unit mean of the window's rows and the unit mean of all the stream's rows, the most over the extractor's tiles. A window with no embedded frame has none |
| `<extractor_id>.instability` | `temporal-instability` | Mean `1 - cos` between consecutive embedded frames of the window, the most over the extractor's tiles. A window needs two embedded frames |

Deviation finds what a fixed camera rarely shows; instability, how much the frozen backbone's account
of a window changes from frame to frame, stands in for uncertainty, which a backbone without a
classifier does not have. Values are rounded to ten decimals. Each score's method has revision 1.

| Method | Seed | Rule |
| --- | --- | --- |
| `uniform` | required | The baseline. A simple random sample of `n = min(budget, N)` of the `N` eligible pool windows, ranked by the SHA-256 of the method, seed, stream and candidate id; every eligible window has probability `n / N`. It reads no score, so `features_unavailable` never applies |
| `ssl-diverse` | none | Deterministic. Each read score becomes a percentile among eligible windows, ties averaged, and priority is their mean. Picks are greedy: the highest priority less half the largest cosine similarity to a window already picked, the similarity being the mean over the extractors the read scores use. Ties go to stream, then candidate order. A window missing a read score is `features_unavailable` |

Only pool windows are ranked: a sibling window keeps its scores for review and is `not_selected`
with probability 0. A pool window of a stream in the `locked` split is `operator_excluded` under
every method that ranks, because no locked-test custodian policy exists to allow it; it still
stays in the audit pool, and [review](review-and-freeze.md#what-review-offers) withholds it.
`discover verify` recomputes every score and decision from the feature rows
and the staged frames and refuses a difference, or a method it does not know, as `RECORD_INVALID`
with a `selection` finding. Scores compare as written, so verification holds on the host that wrote
the run.

## Determinism and concurrency

Nothing is written until every extractor and hint file has answered. A run is built in scratch and
published by one rename under `self-supervised-corpus/.publish.lock`, so a reader meets a whole run
or none, and two writers of one run id leave one run and a `CORPUS_CONFLICT`. A command holds
`.run-<run-id>.lock` while it computes, so a second command for that run id is
`DISCOVERY_IN_PROGRESS` at once.

## Measured run

On 2026-11-07 the four sibling-study clips (`testsrc2` at 30 frames per second, a 1.5 s start
offset, 4 frames per second and a variable rate) were staged as one corpus each, sampled by
ss-perception `extract_frames` with ffmpeg 8.0.1, and run with both pinned extractors on this
host's CPU. Results are under `$DATA_DIR/self-supervised-corpus/adapter-run-20261107/`:

| Clip | Frames | Hint matches mapped | Feature rows | Wall time |
| --- | --- | --- | --- | --- |
| 30 fps | 120 | 20 of 20 | 240 | 51 s |
| offset | 120 | 20 of 20 | 240 | 51 s |
| 4 fps | 16 | 16 of 20, 4 `empty_slot` | 32 | 13 s |
| variable rate | 80 | 20 of 20 | 160 | 36 s |

Every one of the 76 mapped windows ends on the staged frame its ss-video JPEG shows, by least mean
absolute difference; each empty slot showed the previous slot's frame. Peak resident memory was
1.56 GB. A retry of the 30 fps run reported `unchanged`, so CPU rows are reproducible across
processes. A GPU run was not measured.

## Measured selection

On 2026-11-07 six synthetic 640 by 360 clips of 64 frames were staged as one corpus, each stream its
own group: a 12 by 6 pixel gull at the right edge, the same gull at the centre, a 5 by 3 pixel bird
at the top-left edge, empty sky, a swaying branch (a confuser) and a brightness flicker (a
negative). Twelve of the 48 eight-frame pool windows hold a target. One run embedded every second
frame with CLIP ViT-B/16 and DINOv2 ViT-B/14, each centre-cropped and in a 4 by 2 grid, and selected
12 windows by `ssl-diverse` over `clip-b16-tiles.deviation` and `motion`; a second ran `uniform`
with the same audit seed. Other score sets were replayed through the same `score_and_select` over
the first run's rows. Results, scripts and records are under
`$DATA_DIR/self-supervised-corpus/selection-eval-20261107/`.

| Scores read | Targets of 12 selected | Edge, centre, tiny edge | Confusers selected |
| --- | --- | --- | --- |
| `uniform`, seed 3 (expected 3) | 4 | 2, 0, 2 | branch 2, flicker 2, empty 1 |
| `motion` | 4 | 3, 1, 0 | branch 8 |
| CLIP centre deviation | 4 | 0, 4, 0 | flicker 4 |
| CLIP tiled deviation | 8 | 4, 4, 0 | none |
| CLIP centre deviation and motion | 5 | 0, 4, 1 | branch 5, flicker 1 |
| CLIP tiled deviation and motion (the run) | 11 | 4, 4, 3 | branch 1 |
| DINOv2 tiled deviation and motion | 10 | 4, 4, 2 | branch 1 |

The centre crop cannot see an edge target: CLIP deviation separates edge-gull windows from
target-free ones with an area under the curve of 0.15 centre-cropped and 0.94 tiled, and the tiny
bird with 0.30 and 0.83. Motion alone ranks the branch first. The 12-window audit sample held 3
target windows and 2 each of branch, flicker and empty sky, so negatives and confusers stay
measurable whatever selection picks. The run took 10 min 45 s on this host's CPU with 1.56 GB peak
resident memory for 3,456 embedded images; the uniform run, which embeds nothing, took 1.1 s and a
retry reported `unchanged`. `discover verify` recomputed every score and decision in 1.3 s. These
clips are fixtures: the result shows the mechanism works and that tiles matter for edge and small
targets, not how selection performs on real footage.

## Limits

- Deviation compares a window with its own stream, so an object present for a whole stream is its
  background; motion and the audit sample are the cover for it. Scores rank review; they do not
  detect, and a high score is not a bird.
- Selection evidence on real footage needs the reviewed protocol of the
  [selection evaluation](../../plan.md#corpus-selection-evaluation).
- ss-video has no export of matches joined to file hashes, so an operator builds the hint file.
- Rows are float32 only; a GPU mixed-precision mode is a contract minor that the
  [scale pilot](../../plan.md#corpus-scale-pilot) owns if it needs one.
- A tiled grid multiplies embedding compute by its tile count.
- Running over real sources waits for the
  [source authorization](../../plan.md#authorize-video-corpus-sources) grant for the sibling code
  and weights.

## Interfaces

| Module | Does |
| --- | --- |
| `commands/discover.py` | `discover run` and `discover verify` |
| `corpus/discovery/run.py` | `run_discovery`, `build_discovery`, `verify_discovery_run` |
| `corpus/discovery/result.py` | `DiscoveryResult`: counts, selection summary, unavailable scores, coverage |
| `corpus/discovery/plan.py` | `read_discovery_plan`, tile views and the selection's score rule |
| `corpus/discovery/pool.py` | Pool tiling and the audit draw |
| `corpus/discovery/selection_check.py` | `require_reproduced`: recompute scores and selection on verify |
| `corpus/selection/catalog.py` | Score names, methods and revisions |
| `corpus/selection/motion.py` | The `block-difference` motion score |
| `corpus/selection/embeddings.py` | Feature rows by extractor and stream, window rows, stream background |
| `corpus/selection/scores.py` | Every candidate's scores, or why each is unavailable |
| `corpus/selection/methods.py` | `unranked`, `uniform` and `ssl-diverse` |
| `corpus/selection/apply.py` | `score_and_select` from a plan or from a written run |
| `corpus/siblings/tiles.py` | Tile geometry, crops and coverage |
| `corpus/siblings/worker_env.py` | The worker's interpreter and process environment |
| `corpus/discovery/features.py` | Feature-rows records: seal, rules, vector reads, frame binding |
| `corpus/discovery/sibling_check.py` | Recomputes each sibling window from pinned PTS |
| `corpus/siblings/slots.py` | The slot rule, in exact rationals |
| `corpus/siblings/video_hints.py` | `read_hint_source`, `map_hints` |
| `corpus/siblings/embedding.py` | `embed_streams`: worker environment, pins, batches and row checks |
| `corpus/siblings/worker_process.py` | Worker process, protocol framing and deadlines |
| `corpus/siblings/perception_worker.py` | The standalone worker and its guards |

## Verification

```bash
.venv/bin/pytest tests/corpus/siblings tests/corpus/discovery tests/corpus/selection
SST_PERCEPTION_PYTHON=/path/to/pinned-env/bin/python \
  .venv/bin/pytest tests/corpus/siblings/test_sibling_defects.py
make ci
```

`tests/corpus/siblings/` runs the real worker script in a throwaway environment holding a fake
ss-perception (`fake_site/`), which reproduces each defect on request, over really staged bundles.
`test_slots.py` covers a start offset, a slower source and a variable rate.
`tests/corpus/discovery/test_discovery_run.py` writes, retries, conflicts, locks, races two
writers, and refuses a moved sibling window, altered vectors and rows naming other frames.
`test_selection_run.py` runs tiled extractors and both methods over a corpus with a locked stream,
holds the audit sample fixed across methods, and refuses a changed decision, a changed score and an
unknown method on verify. `tests/corpus/selection/` checks tile geometry, coverage, the motion
block rule, each score and both methods against hand-calculated values.

## Evaluating selection

`discover evaluate` compares verified `ssl-diverse` and `uniform` runs of the same pool, frame set,
audit design and selection budget. Give each run either its review declaration or the identifier of
a frozen corpus made from that review:

```bash
ss-track discover evaluate --diverse-run diverse-1 --uniform-run uniform-1 \
  --diverse-review diverse-review.yaml --uniform-review uniform-review.yaml
```

`--diverse-freeze` and `--uniform-freeze` replace the respective review argument. The command
verifies both runs and recomputes selection, checks each review against its queue, and refuses
conflicting observations. It reports selected and offered counts, overlap with the audit draw,
withheld windows, selection exclusions, distinct selected streams and groups, and individual
observations with selection decisions and motion rank. A whole-stream target is reported only when
all its pool windows have a target-present observation. Motion rank is descending among the distinct
available motion scores, with ties sharing a rank. When a review or freeze states independence,
blinding and reviewer minutes, the comparison reports those declarations. A review that omits them
stays unrecorded. A stated value is not a verification that the procedure was followed, and pictures
may still show the source. Compute cost stays unrecorded because discovery does not capture it.

The log line is a `result/command` 1.22.0 record. `status` is `estimated` when the comparison has
recall and an interval, and `inconclusive` when evidence is missing, variance is unavailable, or the
runs selected different counts. `review_blinding`, `review_independence` and
`review_effort_minutes` belong to this comparison. They are not the `blind` counts from
`discover blind` or `discover unblind`. `compute_cost` on each run is null.

For each group, an audit observation receives weight `population / sample_size`. Weighted target
counts yield recall for each selection and the paired difference. The approximate 95% intervals use
stratified finite-population variance and a delta-method ratio; they are not guarantees, especially
for small samples. No sample, an unknown or unreviewed audit window, no observed target, unavailable
variance, or unequal actual selection counts makes the comparison inconclusive. Unknown observations
are never treated as target absence. Weighted observation counts are explicitly marked incomplete
when audit observations are missing. Observations are reviewer statements, not verified labels,
species, or field accuracy. The [evaluation task](../../plan.md#corpus-selection-evaluation) remains
open for a reviewed evaluation run.

The reader and comparison are in `corpus/evaluation/inputs.py` and `report.py`; stratified estimates
are in `statistics.py`. Verify with `tests/corpus/evaluation/`, the discovery selection and review
freeze tests, and `make ci`. The evaluation command test logs an estimated comparison, an
inconclusive one, and one whose blinding declarations differ. The suite checks each log against the
newest `result/command`.

The [task record](../../records/0064-self-supervised-corpus-corpus-evaluation-result-contract.md)
holds the decisions and acceptance evidence.
