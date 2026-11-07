# Discovery runs

`ss-track discover run` writes one [discovery run](discovery-records.md) over a staged corpus
version from an operator's plan. It embeds staged frames with pinned ss-perception extractors in a
separate process, turns ss-video matches into candidate windows of ss-track frames, tiles every
bundle into pool windows and draws the independent audit sample. `ss-track discover verify` checks
a written run against the corpus version it read. The adapter ranks nothing: SSL selection, which
the [plan](../../plan.md#corpus-ssl-selection) schedules, adds scores and a selection method. The
[task record](../../records/0052-self-supervised-corpus-corpus-video-index-adapter.md) holds the
decisions and acceptance evidence.

A candidate is a proposal and a feature row describes pixels. Neither is a label, and a run
authorizes no source.

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
                   "unmapped": [{"reason": "empty_slot", "count": 4}]}]}
```

The same plan over the same staged frames writes the same bytes, so a retry reports `unchanged`.
Another plan under a used run id is `CORPUS_CONFLICT`. `verify` reports `verified` with the same
fields.

## Plan

`declaration/discovery-plan` 1.0.0 states one run. Extractors, weights and hint files are listed in
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
```

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
environment when `SST_PERCEPTION_PYTHON` is set, and fails once a defect is gone:

| Defect | Guard | Refusal |
| --- | --- | --- |
| Settings import loads `.env` files and adds variables | Empty working directory; values ss-track set must come back unchanged | `EXTRACTOR_UNPINNED` |
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

Every pool window is `not_selected` with probability 0 under the `unranked` method, budget 0 and
no scores. The audit sample is `stratified_fixed_size` with one stratum per encounter group: each
pool window ranks by the SHA-256 of the seed, group, stream and candidate id, and the lowest
`min(sample_size, windows)` are drawn. The rank is the same in any language and Python version.

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

## Limits

- The adapter ranks nothing and draws only the audit sample;
  [SSL selection](../../plan.md#corpus-ssl-selection) adds scores and selection.
- ss-video has no export of matches joined to file hashes, so an operator builds the hint file.
- Rows are float32 only; a GPU mixed-precision mode is a contract minor that the
  [scale pilot](../../plan.md#corpus-scale-pilot) owns if it needs one.
- Embedders centre-crop to 224 pixels; tiled coverage belongs to
  [SSL selection](../../plan.md#corpus-ssl-selection).
- Running over real sources waits for the
  [source authorization](../../plan.md#authorize-video-corpus-sources) grant for the sibling code
  and weights.

## Interfaces

| Module | Does |
| --- | --- |
| `commands/discover.py` | `discover run` and `discover verify` |
| `corpus/discovery/run.py` | `run_discovery`, `build_discovery`, `verify_discovery_run` |
| `corpus/discovery/plan.py` | `read_discovery_plan` |
| `corpus/discovery/pool.py` | Pool tiling, the `unranked` selection and the audit draw |
| `corpus/discovery/features.py` | Feature-rows records: seal, rules, vector reads, frame binding |
| `corpus/discovery/sibling_check.py` | Recomputes each sibling window from pinned PTS |
| `corpus/siblings/slots.py` | The slot rule, in exact rationals |
| `corpus/siblings/video_hints.py` | `read_hint_source`, `map_hints` |
| `corpus/siblings/embedding.py` | `embed_streams`: worker environment, pins, batches and row checks |
| `corpus/siblings/worker_process.py` | Worker process, protocol framing and deadlines |
| `corpus/siblings/perception_worker.py` | The standalone worker and its guards |

## Verification

```bash
.venv/bin/pytest tests/corpus/siblings tests/corpus/discovery
SST_PERCEPTION_PYTHON=/path/to/pinned-env/bin/python \
  .venv/bin/pytest tests/corpus/siblings/test_sibling_defects.py
make ci
```

`tests/corpus/siblings/` runs the real worker script in a throwaway environment holding a fake
ss-perception (`fake_site/`), which reproduces each defect on request, over really staged bundles.
`test_slots.py` covers a start offset, a slower source and a variable rate.
`tests/corpus/discovery/test_discovery_run.py` writes, retries, conflicts, locks, races two
writers, and refuses a moved sibling window, altered vectors and rows naming other frames.
