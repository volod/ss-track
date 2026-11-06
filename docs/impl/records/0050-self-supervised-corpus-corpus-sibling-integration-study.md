# Sibling integration study for video corpus formation

## Task and scope

- Id / capability: `corpus-sibling-integration-study` / `self-supervised-corpus`
- State: accepted.
- Source: plan task; starting HEAD `a7773f2` on branch `st-06-self-supervised-corpus`, clean tree.
- Plan counts at start: 128 tasks, 105 agent and 23 human. Next agent
  `corpus-sibling-integration-study`; next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-sibling-integration-study

The sibling projects expose video indexing and SSL research, but their exact export and version
compatibility for frozen corpus formation need evidence.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Research: yes
- Dependencies: none.
- User-visible outcome: A reviewable adapter plan identifies usable ss-video and ss-fusion interfaces.
- Scope boundary: Inspect pinned revisions, package and model licenses, sampling and export paths;
  training, privileged service deployment, and broad source acquisition are excluded.
- Data and artifact paths: `docs/impl/current/corpus.md`, `docs/impl/records/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Inspect ss-video ingest/search and ss-fusion perception/SSL paths; test a small
  local example or fixtures and record exact revisions, versions, resource requirements and gaps.
- Acceptance gates: Document the source/frame-to-embedding and export mapping, model and data rights,
  version compatibility and reproducibility; a reasoned incompatibility or unavailable interface is
  a valid negative with an alternative or explicit block. `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

Research only: no production code, contract or dependency changed, and ss-track still neither
depends on nor imports a sibling. The result is the
[sibling integration page](../current/corpus/sibling-integration.md), linked from the corpus page and
the current-state index.

Inspected: ss-video `v0.2.0` (`703e3c9`), ss-fusion `v0.2.0` (`12cb086`) and ss-common `v0.2.1`
(`2558373`), cloned into a scratch directory. Both `v0.2.0` tags are the branch heads that record
0038 inspected, so the 0.2.0 and 0.2.1 question it raised is a label mismatch inside one tree, not
a code mismatch. Paths read: the ss-video indexer, index and query routers, schemas, the processed
file registry and compose stack; ss-perception embedders, frame extraction, settings and env
loading, manifests; ss-fusion SSL training, the `ssv` embed step and local env.

Run: `$DATA_DIR/self-supervised-corpus/sibling-study-20261106/`. Four ffmpeg `testsrc2` clips
(constant 30 frames per second, a 1.5 s start offset, 4 frames per second, variable rate) were
imported, built and staged by ss-track, one corpus each, because ss-track refused one shared-content
corpus with its shared-run check, as designed. ss-perception from the `v0.2.0` git tag, CPU torch
and open_clip were installed into an isolated Python 3.12 environment outside the project lock.
`extract_frames` ran on each clip, and each JPEG was matched to the nearest staged frame by mean
absolute difference. The two embedders ran over staged frames twice in one process, with batch 16
and batch 1, and once more in a second process. Scripts are not kept; the JSON results are.

Decisions:

- The integration runs ss-perception out of process over ss-track-staged frames. In-process import
  was rejected: it mutates the process environment, reads `.env` files from the working directory's
  project and writes to standard output. Depending on a running ss-video was rejected: it has no
  bulk export, and reading its stores is privileged service access.
- A sibling timestamp names a window, never a frame. The `fps` slot rule reproduced all 80 JPEGs,
  while nearest-time matching names the wrong frame.
- Frozen pretrained backbones only; SSL-adapted checkpoints carry no training-source manifest.
- ss-fusion has no licence, so a real run waits for the owner's grant under
  `authorize-video-corpus-sources`.

Plan and specification: this task is removed. `corpus-discovery-contract` loses its dependency on it
and gains feature-provenance fields and a sibling-time refusal. `corpus-video-index-adapter` is
rewritten around the worker, the hint reader and the defect wrappers. `corpus-ssl-selection` now
depends on the adapter and gains frozen-backbone and edge-coverage scope.
`authorize-video-corpus-sources` gains the code and weight grants, and `corpus-scale-pilot` gains
CPU or GPU compute. Specification section 4.1a states the boundary.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Source/frame-to-embedding and export mapping | `slot_rule.json`, `sibling_study-a.json` in the run directory | pass: the slot rule matched 80 of 80 JPEGs; source join through `file_hash` read from code, not run against a live ss-video |
| Model and data rights | GitHub and Hugging Face licence metadata, CLIP model card, ss-fusion tree | pass: ss-fusion unlicensed, an explicit block owned by `authorize-video-corpus-sources` |
| Version compatibility | `uv pip install` of ss-perception at `v0.2.0` with ss-common `v0.2.1`; `direct_url.json` commits | pass: one tree; package versions 0.2.1 under tag `v0.2.0` |
| Reproducibility | `sibling_study-a.json`, `sibling_study-b.json` | pass on CPU: bitwise equal across runs and processes; CLIP batch-size dependence 2.4e-7; GPU not measured |
| Resources | same files | measured: 1.2 GB environment, 0.94 GB weights, 151 and 205 ms per frame, 1.6 GB peak memory |
| Document links and lint | `make lint-doc-links`, `make lint-md` | pass |
| Plan integrity | `make lint-spec-plan` | pass, 0 findings |
| Final gate | `make ci` | pass: 1930 tests, four third-party deprecation warnings |

## Audit handoff

- `AUD-corpus-sibling-integration-study-1`: sibling settings import adds 21 variables, including
  `DATA_DIR=./.data`, reads `.env` files under the working directory's project and prints download
  progress on standard output. Nonblocking for fixtures. Owner: `corpus-video-index-adapter`
  (explicit environment, neutral working directory, own process, wrapper tests).
- `AUD-corpus-sibling-integration-study-2`: `DINOEmbedder` loads `DINO_CHECKPOINT` or
  `active_checkpoint.txt` unrecorded and keeps base weights when the file is missing; both
  embedders move to the CPU on CUDA out-of-memory. Owner: `corpus-video-index-adapter`.
- `AUD-corpus-sibling-integration-study-3`: CLIP and DINOv2 weights resolve from `main`, and CLIP
  rows depend on batch size. Owners: `corpus-video-index-adapter` (pinned revisions, refusal) and
  `corpus-discovery-contract` (weight revision, SHA-256 and batch size in provenance).
- `AUD-corpus-sibling-integration-study-4`: ss-video `t_sec` counts from the first frame, leads the
  content by up to half a slot and repeats frames of slow sources; Qdrant points carry a random
  `video_id`, no source hash and no model name, and kept keyframes have no inclusion probability.
  Owners: `corpus-video-index-adapter` (slot rule, hash join, no audit-sample entry) and
  `corpus-discovery-contract` (sibling-time refusal).
- `AUD-corpus-sibling-integration-study-5`: ss-fusion carries no licence, and the CLIP model card
  puts deployed use out of scope. Blocking for real runs only. Owner:
  `authorize-video-corpus-sources`.
- `AUD-corpus-sibling-integration-study-6`: both embedders centre-crop to 224 pixels, dropping
  about 22% of a 16:9 frame's width on each side and shrinking small targets; SSL checkpoints have
  no training-source manifest. Owner: `corpus-ssl-selection`.
- `AUD-corpus-sibling-integration-study-7`: compute was measured on CPU only. Owner:
  `corpus-scale-pilot`.
- Dropped: the ss-fusion `ssv` pipeline records its `--fps` argument in `frames_metadata.json`
  while extraction reads `SAMPLE_FPS_MAX`, which a loaded `.env` may already have set. The
  integration plan excludes that pipeline, so no ss-track path reaches it.
- Dropped: a suspected washed-out colour range from `-color_range 2` in `extract_frames`. Measured
  luma standard deviation stayed within 0.2% of the staged frames, so there is no defect.

## Close or resume

Every gate passed. The current corpus page and the current-state index link the new
[sibling integration page](../current/corpus/sibling-integration.md), which links this record. Plan
counts moved from 128 (105 agent, 23 human) to 127 (104 agent, 23 human). The next agent task is
`corpus-discovery-contract`; `self-supervised-corpus` stays planned.
