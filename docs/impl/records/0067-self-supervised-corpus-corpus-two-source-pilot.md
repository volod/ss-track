# corpus-two-source-pilot

## Task and scope

- Id / capability: `corpus-two-source-pilot` / `self-supervised-corpus`
- State: active
- Source: plan task; start commit `21dae935e84a00431257617804114e65a4cb546d`;
  preexisting change: `docs/impl/records/0056-self-supervised-corpus-corpus-selection-evaluation.md`.
- Plan counts at start: 101 agent, 23 human; next agent `corpus-two-source-pilot`,
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-two-source-pilot

The chosen sources need an approved, measured pool and paired runs before people can review them.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: authorize-video-corpus-sources.
- User-visible outcome: An approved bounded subset of both collections is staged and offers a
  reproducible independent audit sample and matched selection runs, or an evidence-backed negative.
- Scope boundary: Approved sources, rights, models, storage, compute and reviewer budget only; no
  unattended spend, public upload, held-out access or field-prevalence claim.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`,
  `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Resolve pins and terms per source, acquire only approved inputs, verify hashes,
  group cross-source related recordings, build and stage the pool, and run `ssl-diverse` and
  `uniform` at one pool, audit seed and budget. Freeze the review protocol before `discover blind`;
  record source coverage, exclusions, resources, approvals and stopped runs.
- Acceptance gates: Inputs, staged frames, grouping, selection and sampling verify; the review queue
  includes eligible unselected windows, reports withheld exposure and retains reproducible evidence.
  Insufficient rights, targets or resources is an explicit valid negative; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: the owner requested host-appropriate settings; freeze sampling and audit settings
  across comparisons. Revised task:

```markdown
#### corpus-two-source-pilot

The chosen sources need an approved, measured pool and paired runs before people can review them.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: authorize-video-corpus-sources.
- User-visible outcome: An approved bounded subset of both collections is staged and offers a
  reproducible independent audit sample and matched selection runs, or an evidence-backed negative.
- Scope boundary: Approved sources, rights, models, storage, compute and reviewer budget only; no
  unattended spend, public upload, held-out access or field-prevalence claim.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`,
  `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Resolve pins and terms per source, acquire only approved inputs, verify hashes,
  group cross-source related recordings, build and stage the pool, and run `ssl-diverse` and
  `uniform` at one pool, audit seed and budget. Freeze the review protocol before `discover blind`;
  record source coverage, exclusions, resources, approvals and stopped runs. Select device, batch
  size and resource limits for the host and record them; hold the sampling, tile grid and audit
  settings fixed when comparing hosts, since those settings change the experiment.
- Acceptance gates: Inputs, staged frames, grouping, selection and sampling verify; the review queue
  includes eligible unselected windows, reports withheld exposure and retains reproducible evidence.
  Insufficient rights, targets or resources is an explicit valid negative; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: real-source acquisition and the embedding-based relationship check exposed missing
  per-recording associations and unresolved cross-group links. Revised task:

```markdown
#### corpus-two-source-pilot

The chosen sources need an approved, measured pool and paired runs before people can review them.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: authorize-video-corpus-sources.
- User-visible outcome: An approved bounded subset of both collections is staged and offers a
  reproducible independent audit sample and matched selection runs, or an evidence-backed negative.
- Scope boundary: Approved sources, rights, models, storage, compute and reviewer budget only; no
  unattended spend, public upload, held-out access or field-prevalence claim.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`,
  `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Resolve pins and terms per source, acquire only approved inputs, verify hashes,
  group cross-source related recordings, build and stage the pool, and run `ssl-diverse` and
  `uniform` at one pool, audit seed and budget. Freeze the review protocol before `discover blind`;
  record source coverage, exclusions, resources, approvals and stopped runs. Select device, batch
  size and resource limits for the host and record them; hold the sampling, tile grid and audit
  settings fixed when comparing hosts, since those settings change the experiment. Resolve or
  explicitly withhold uncertain per-recording provenance and flagged cross-group links before
  relying on groups as independent; report an evidence-backed negative when they cannot be resolved.
- Acceptance gates: Inputs, staged frames, grouping, selection and sampling verify; the review queue
  includes eligible unselected windows, reports withheld exposure and retains reproducible evidence.
  Insufficient rights, targets or resources is an explicit valid negative; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: staged real footage exposed missing color-matrix metadata. Revised task:

```markdown
#### corpus-two-source-pilot

The chosen sources need an approved, measured pool and paired runs before people can review them.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: authorize-video-corpus-sources.
- User-visible outcome: An approved bounded subset of both collections is staged and offers a
  reproducible independent audit sample and matched selection runs, or an evidence-backed negative.
- Scope boundary: Approved sources, rights, models, storage, compute and reviewer budget only; no
  unattended spend, public upload, held-out access or field-prevalence claim.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`,
  `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Resolve pins and terms per source, acquire only approved inputs, verify hashes,
  group cross-source related recordings, build and stage the pool, and run `ssl-diverse` and
  `uniform` at one pool, audit seed and budget. Freeze the review protocol before `discover blind`;
  record source coverage, exclusions, resources, approvals and stopped runs. Select device, batch
  size and resource limits for the host and record them; hold the sampling, tile grid and audit
  settings fixed when comparing hosts, since those settings change the experiment. Resolve or
  explicitly withhold uncertain per-recording provenance and flagged cross-group links before
  relying on groups as independent; check untagged source color matrices and report the effect of
  any required fallback. Report an evidence-backed negative when evidence cannot be resolved.
- Acceptance gates: Inputs, staged frames, grouping, selection and sampling verify; the review queue
  includes eligible unselected windows, reports withheld exposure and retains reproducible evidence.
  Insufficient rights, targets or resources is an explicit valid negative; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: the selection-pass protocol (record 0070), the human link-review dependency (record
  0072) and the media-free recipe requirement (record 0073) revised the open task. Revised task:

```markdown
#### corpus-two-source-pilot

The chosen sources need an approved, measured pool and paired runs before people can review them.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: authorize-video-corpus-sources, review-pilot-recording-links.
- User-visible outcome: An approved bounded subset of both collections is staged and offers a
  reproducible independent audit sample and matched selection runs, or an evidence-backed negative.
- Scope boundary: Approved sources, rights, models, storage, compute and reviewer budget only; no
  unattended spend, public upload, held-out access or field-prevalence claim.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`,
  `$DATA_DIR/corpus/<corpus-id>/`, `docs/impl/workloads/two-source-pilot/`.
- Execution path: Resolve pins and terms per source, acquire only approved inputs, verify hashes,
  group cross-source related recordings, build and stage the pool, and run `ssl-diverse` and
  `uniform` at one pool, audit seed and budget. Freeze the review protocol, including a selection
  pass of each run over the one shared audit, before `discover blind`;
  record source coverage, exclusions, resources, approvals and stopped runs. Select device, batch
  size and resource limits for the host and record them; hold the sampling, tile grid and audit
  settings fixed when comparing hosts, since those settings change the experiment. Resolve or
  explicitly withhold uncertain per-recording provenance and flagged cross-group links before
  relying on groups as independent; check untagged source color matrices and report the effect of
  any required fallback. Publish a media-free creation recipe with the pinned inventory, exact
  selections, acquisition commands and byte limits, and pool declaration so every authorized host
  can independently acquire and stage the same corpus. Report an evidence-backed negative when
  evidence cannot be resolved.
- Acceptance gates: Inputs, staged frames, grouping, selection and sampling verify; the review queue
  includes eligible unselected windows, reports withheld exposure and retains reproducible evidence.
  A fresh authorized data root recreates the same source, corpus and frame-set identities from the
  media-free recipe, or records an explicit valid negative. Insufficient rights, targets or resources
  is an explicit valid negative; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: the former host's data root was unavailable here, and the owner chose a fresh
  selection recreated from the sources on this host. The recipe, pool, runs and link record now
  exist, so the task states only the remaining link application, regrouping, cross-host comparison,
  blinded presentation and color-score work. Revised task:

```markdown
#### corpus-two-source-pilot

The chosen sources need an approved, measured pool and paired runs before people can review them.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: authorize-video-corpus-sources, review-pilot-recording-links.
- User-visible outcome: An approved bounded subset of both collections is staged and offers a
  reproducible independent audit sample and matched selection runs, or an evidence-backed negative.
- Scope boundary: Approved sources, rights, models, storage, compute and reviewer budget only; no
  unattended spend, public upload, held-out access or field-prevalence claim.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`,
  `$DATA_DIR/corpus/<corpus-id>/`, `docs/impl/workloads/two-source-pilot/`.
- Execution path: The [pilot recipe](workloads/two-source-pilot/README.md) pins the sources,
  pool, paired plans and frozen review protocol, including a selection pass of each run over the
  one shared audit. Apply the reviewer's returned link decisions with `discover links`. When a
  related pair crosses groups, group it in a new corpus version and rerun both plans and
  `discover verify`, because the audit is stratified by group; withhold undecided pairs from any
  independence claim and report their effect, or report an evidence-backed negative. Compare the
  reviewer host's independently created staged identities with the origin's, then present the
  shared blinded audit with `discover blind` over both runs before human review. Measure the effect
  of the BT.601 fallback on the untagged sources' scores, or report it unmeasured beside the pixel
  difference. Record source coverage, exclusions, resources, approvals and stopped runs. Select
  device, batch size and resource limits for the host and record them; hold the sampling, tile
  grid and audit settings fixed when comparing hosts, since those settings change the experiment.
- Acceptance gates: Inputs, staged frames, grouping, selection and sampling verify; the review queue
  includes eligible unselected windows, reports withheld exposure and retains reproducible evidence.
  A fresh authorized data root recreates the same source, corpus and frame-set identities from the
  media-free recipe, or records an explicit valid negative. Insufficient rights, targets or resources
  is an explicit valid negative; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

## Implementation

The active protocol draft and source metadata are under
`$DATA_DIR/self-supervised-corpus/two-source-pilot-20261109/`. The owner authorized a bounded
local pilot and selected the licensed ss-fusion `v0.2.1`; the authorization record holds the
limits. The public tag resolves to `75debcfed31a3c148d2f194a8ae2345e4b7508f1`; the files shared
with the previously studied `v0.2.0` tree are byte-identical. A separate GPU environment and
both source acquisitions are complete. The existing CPU worker environment is preserved.
The CUDA environment has PyTorch 2.7.1+cu128 and ss-perception pinned to the licensed commit.
CUDA arithmetic passed on the RTX 5050; a synthetic tiled CLIP run wrote and verified 192 feature
rows in `selection-eval-20261107/ss-track-data/self-supervised-corpus/pilot-gpu-smoke-20261109/`.
A second synthetic tiled DINO run wrote and verified 384 rows in
`selection-eval-20261107/ss-track-data/self-supervised-corpus/pilot-gpu-dino-smoke-20261109/`
and had no selection exclusions. The CLIP smoke run's deliberately sparse stride of 16 left half
its eight-frame windows without embeddings; the
real pilot plan must use a stride no larger than its window to avoid that missing coverage.
The owner identified the current machine as the lower-resource host and the standard station as
128 GB RAM with a 16 GB GPU. Select device and batch size for each host, preserve them in each
run, and verify resource use there. Keep scientifically consequential sampling and audit settings
fixed across comparisons. The standard station has not been measured here.
The drone acquisition completed and verified 15 candidates, approximately 12.84 minutes and
63.92 GB of decoded RGB frames by ffprobe estimates. Its sealed acquisition and inventory are
under `$DATA_DIR/self-supervised-corpus/pilot-drone-acquisition-20261109/`; the inventory retains
123 other discovered videos as unknown. Individual source associations remain under review.
The initial inventories used a collection URL
as each recording source, which would falsely group all videos of a collection. Corrected
inventories leave the individual source unknown, and new acquisition runs reuse and verify the
original cached inputs without changing the sealed first records.

The real WetlandBirds v4 acquisition initially refused `SOURCE_DAMAGED`: the legacy Zenodo API
omits `metadata.version`. The native API gives the same record id and version index 4. Acquisition
now requests the native representation only when the legacy version is absent, checks the id and
positive version index, then retains the existing archive size and checksum checks. Regression
tests cover the missing version, mismatch and malformed indexes. The preliminary source selection
is not reviewed ground truth and does not establish independent groups. Both corrected
acquisitions are sealed; 31 selected videos total approximately 18.36 minutes and 128.95 GB of
decoded RGB by ffprobe estimates. All 31 per-recording associations remain missing. A provisional
build found three consecutive gull videos with similarities 0.9525-0.959; they are conservatively
grouped in the v2 pool before the audit draw. The grouped build has 29 provisional groups; visual
relationship review has not yet established their independence. The grouped corpus staged all
31 streams with frame-set SHA-256
`a75f5b3014dfaaf03d7fbef1ec7ea6ce5a7f2a9a3dfedab96ac4e28d9172ea88`; 13 streams lacked color
matrix, primaries and transfer tags and use the documented BT.601 fallback. `ffprobe` showed
untagged color metadata on six drone and seven WetlandBirds videos; the other 18 state BT.709.
The untagged videos do not prove their intended matrix, so no replacement was invented. This may
affect pixel values and downstream scores. `corpus verify` verified all 31 bundles
and that frame-set hash. On this host staging took 7m 20s and verification 1m 48s;
resource details are in `two-source-pilot-20261109/stage-v2.time` and `verify-v2.time`.
The luma-only links run returned clear, without comparing embedding backgrounds. A frozen protocol
and paired plans are under `two-source-pilot-20261109/`; the GPU model-assisted run completed
in 1h 07m 45s, with 139776 feature rows, 2193 candidate windows, 100 selected and two excluded
for unavailable features. Sampling every two seconds reported a peak 847 MiB GPU memory; CPU
peak RSS was 1628320 KiB. The smallest tile scale across the pool was 0.207407 model pixels per
source-frame pixel, so a 19-121 pixel full-resolution target would span about 4-25 model-input
pixels at that scale before blur or foreshortening. The camera estimate is not a measured target
in these videos. The uniform run selected 100 of the same 2193 windows in 11m 11s and used
431164 KiB peak RSS. Selection is not a reviewed label. Both discovery runs verified against their
sealed frame set; the embedding-background relationship review found 136 unresolved links among
the 29 provisional groups, forming connected components of 15 and 14 groups. Grouping every flag
would collapse the pool to two groups; similar backgrounds alone do not prove shared provenance.
Independent grouping requires review of those links and the missing source associations before the
audit sample is used.
The `two-source-pilot-20261109/link-review/` packet indexes all 136 pairs and contains blank
decisions; its converter was checked against the existing link-decisions declaration using a
separate fixture. No recording relationship has been inferred from the similarity score alone.

### Second host, fresh selection (2026-11-12 and 2026-11-13)

The former host's data root, with its exact 31-video selection, was not available on this host
(RTX PRO 3000 Blackwell laptop GPU with 12 GiB, 62 GiB RAM, 20 logical CPUs). The owner chose a
fresh selection recreated from the pinned sources. The earlier identities, the 136-pair link
packet and the 317 versus 319 queues describe the former selection and are not reused.

The media-free recipe is `docs/impl/workloads/two-source-pilot/`: `inventory.yaml`, `pool.yaml`,
`plan-diverse.yaml`, `plan-uniform.yaml`, the frozen `protocol.md` and a README with the commands,
byte budgets, environment pins and expected identities. WetlandBirds contributes 16 train and
validation videos, one of each of the 13 species plus three from distant clip numbers. The drone
dataset contributes 15 RGB videos at commit `509cdb0f45c77f61fe5f62e5a303411045148c8d`: birds at
long and mid range, insect, airplane and helicopter confusers, empty sky, drones with birds and a
night drone. The selection holds about 11.6 minutes of video.

Two code changes came out of the run:

- Provenance. The drone CSV names omit the video directory, so no per-video license joined.
  `declaration/corpus-pool` 1.1.0 adds an optional per-collection `metadata_names` rule that
  replaces a stated name prefix with a stated path prefix for one acquired CSV file. A name without
  the prefix keeps the exact rule, blank CSV rows are skipped, and a rule that names an unacquired
  or non-CSV file, repeats a file, or has a `..` segment is `MANIFEST_INVALID`. With the two rules
  in `pool.yaml`, all 15 drone videos record their upstream license (`cc-1.0`, `mit` or
  `personal`) with the CSV as its reference. WetlandBirds has no per-video metadata: each video is
  the collection's own footage, so its association stays `missing` and its independence rests on
  the link review. `pool_load.py` reads the rule; `metadata_join.py` and `metadata_text.py` apply it.
- Fail fast on pins. The first model-assisted run was refused `EXTRACTOR_UNPINNED` after 14 min:
  CLIP had embedded the corpus before the DINO worker reported a torch.hub tree that differs from
  the pin. `require_extractors` in `corpus/siblings/embedding.py` now loads every extractor and
  checks its pin before any frame is sent when a plan has more than one. The shared
  `~/.cache/torch/hub` held an April 2026 dinov2 tree; GitHub commit
  `7764ea0f912e53c92e82eb78a2a1631e92725fc8` reproduces the pinned
  `tree-sha256:71fce3da...` exactly, and the run used it from `$DATA_DIR/cache/torch-pilot`
  without changing the shared cache.

The GPU worker environment is `$DATA_DIR/cache/ss-perception-gpu`: Python 3.12, torch 2.7.1+cu128,
torchvision 0.22.1, open-clip-torch 4.2.2, timm 1.0.31, ss-common 0.2.1 and ss-perception at
`75debcfed31a3c148d2f194a8ae2345e4b7508f1`. Both runs use 16-frame windows, audit seed 7 with 8
windows per group and a budget of 100. The model-assisted run embeds every fourth frame with
CLIP ViT-B/16 and DINOv2 ViT-B/14 in a 4 by 2 tile grid on `cuda` with batch 64, and selects
by `ssl-diverse` over `clip-b16-tiles.deviation` and `motion`; the uniform run uses seed 3.

| Step | Result | Resources |
| --- | --- | --- |
| Drone acquisition | 15 videos and 4 metadata files, sealed | 1m19s, 202 MB peak RSS |
| WetlandBirds acquisition | full 9,432,614,851-byte archive verified by MD5, 16 videos extracted | 27m47s, 81 MB peak RSS |
| Pool `pilot-pool-20261112` | 31 included, 31 provisional groups; 15 drone licenses matched, 16 WetlandBirds missing | under 1 s |
| Import, build | 31 sources; luma-grid near duplicates 141-mallard and 157-black_winged_stilt (0.913), 141-mallard and 114-eurasian_moorhen (0.9649) | |
| Stage, verify | frame set `27833c7d...`, 59 GB | 2m11s and 48s |
| `pilot-diverse-20261112` | 80,816 rows, 1,273 candidates, 100 selected, 4 `features_unavailable` | 30m48s, 1.64 GB peak RSS, 1,570 MiB GPU |
| `pilot-uniform-20261112` | 100 selected of the same 1,273 | 1m22s, 190 MB peak RSS |
| `discover verify` | both verified | 89.5 s and 83.9 s |
| `pilot-links-20261112` | 85 unresolved cross-group links: 85 CLIP and 5 DINO background, 2 luma | |
| Queues | 330 and 318 windows offered; the 248-window audit holds 18 and 30 of the selections | 3.6 s and 0.6 s |
| Review pack | `two-source-pilot-20261112/pilot-link-review.tar`, 2,785,280 bytes, 6 recipes, no media | |

The smallest tile scale was 0.414815 model pixels per frame pixel, so a 10-pixel bird spans about
4 model-input pixels. During the DINO pass the GPU sat near 6% utilization while the worker used
about seven CPU cores; preprocessing, not the GPU, bounded the run on this host.

All 85 links join videos of one collection: 28 among WetlandBirds and 57 among drone videos.
Grouping every flag would collapse the pool to three components: 14 WetlandBirds videos, 13 drone
sky videos, and the two 1920 by 1080 drone clips. As on the former host, similar backgrounds do not
prove a shared session, so the groups are provisional until the human review returns.

Colour: 24 of 31 sources carry no colour-matrix tag and use the documented BT.601 fallback; 7
state BT.709. Converting five sampled frames of each untagged video with BT.709 instead changes RGB
by a mean of 0.09 to 2.74 levels, with the 99th percentile at most 5 and a maximum of 27
(`two-source-pilot-20261112/color-effect.jsonl`). No matrix was invented. The effect on scores
and selection is not measured.

This host transferred about 9.6 GB against the 50 GB cap, in addition to the former host's
transfers above. Additional storage is 59 GB of frames and about 0.5 GB of sources and features.
Evidence and timings are under `$DATA_DIR/self-supervised-corpus/two-source-pilot-20261112/`;
the refused first run's output is in its `stopped/` directory.

## Acceptance evidence

The source-acquisition regression tests pass, including a mocked native record with matching and
mismatched versions, invalid indexes and media type. `make ci` passed: 2278 tests passed, 112
deselected. The real pilot remains in progress and is not established by these fixture tests.

Second host:

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Inputs verify | `discover acquire` for both runs; published MD5 and Hugging Face LFS hashes | pass |
| Staged frames verify | `corpus verify --corpus pilot-two-source-20261112` | pass: 31 bundles, frame set `27833c7d...` |
| Selection and sampling verify | `discover verify` for both runs | pass |
| Queue includes unselected windows | `discover queue` for both runs | pass: 248 audit windows, 230 and 218 of them unselected; nothing withheld |
| Grouping verifies | `discover links` | not met: 85 links unresolved; owner `review-pilot-recording-links` |
| Fresh data root recreates identities | recipe in `docs/impl/workloads/two-source-pilot/` | not yet run on a fresh root; the reviewer host's independent creation does it |
| Name rule | `tests/corpus/sources/test_pool_metadata_names.py`, `test_metadata_join.py` | pass: license recorded only with the rule; bad, repeated and parent-directory rules refused |
| Pin preflight | `tests/corpus/siblings/test_worker.py::test_a_later_unpinned_extractor_is_refused_before_any_frame_is_embedded` | pass; fails without the preflight |
| Contract | `contracts freeze declaration/corpus-pool` 1.1.0; example updated | pass |
| Required gate | `make ci` | see close |

## Audit handoff

- `AUD-corpus-two-source-pilot-1`: The real GPU discovery run emits no phase or completed-work
  progress while processing the staged corpus, making it difficult to tell how far a multi-hour
  job has advanced. Evidence: `pilot-diverse-v2-20261109`; only external GPU sampling showed
  activity. Owner: `corpus-discovery-progress`.
- `AUD-corpus-two-source-pilot-2`: The verified paired queues offer 317 and 319 windows: each
  selects 100, but the shared audit overlaps 15 and 13 of those respectively. The current
  evaluator correctly calls the resulting review budgets unmatched, and the queues cannot pad
  the smaller workload. Owner: `corpus-balanced-review-budget`.
- `AUD-corpus-two-source-pilot-3`: Exact recording-source associations are missing for all 31
  selected videos, and background comparison found 136 undecided cross-group links. The pilot cannot
  assert group independence from these records. Owner: `corpus-two-source-pilot`, which requires
  provenance and link review or an explicit negative.
- `AUD-corpus-two-source-pilot-4`: Thirteen sources lack color-matrix metadata; the BT.601 fallback
  may differ from their intended colors and affect scores. Owner: `corpus-two-source-pilot`, which
  requires checking available color evidence and reporting the fallback's effect.
- `AUD-corpus-two-source-pilot-3` on the second host: the fresh selection has 85 unresolved
  cross-group links and no per-video association for the 16 WetlandBirds videos; the drone videos
  now join their upstream license. Owner: `review-pilot-recording-links`, then
  `corpus-two-source-pilot`, whose task states the application and regrouping.
- `AUD-corpus-two-source-pilot-4` on the second host: the pixel effect of the fallback is measured
  for 24 sources; the score effect is not. Owner: `corpus-two-source-pilot`, whose task now states
  it.
- `AUD-corpus-two-source-pilot-5`: a later extractor's pin mismatch was found only after the first
  extractor had embedded the corpus (14 min lost). Fixed in this change by the preflight; dropped.
- `AUD-corpus-two-source-pilot-6`: the GPU worker was CPU-bound at about 6% GPU utilization.
  Owner: `corpus-scale-pilot`, whose execution path now states the measurement and the
  improvement.
- `AUD-corpus-two-source-pilot-7`: the second run again gave no progress for 30 minutes. Owner:
  `corpus-discovery-progress`, which states it.
- `AUD-corpus-two-source-pilot-8`: the fresh-data-root recreation gate is not run. Owner:
  `corpus-two-source-pilot`, which retains the gate; the reviewer host's independent creation
  under `review-pilot-recording-links` provides it.
- Dropped: `corpus/siblings/embedding.py` is 264 lines after the preflight; it stays one cohesive
  worker-protocol module.
- Dropped: the review pack names no reviewer because no checkpoint exists yet.

## Close or resume

The owner suspended the run for a network change and then requested downloads resume. The
WetlandBirds transfer initially stopped and a later retry reached 2885681152 confirmed bytes
before Zenodo returned HTTP 500. A bounded resumable retry reused the confirmed prefix and
transferred 6546933699 further bytes. The complete archive passed its published MD5, and the
standard acquisition verified and extracted it. Both corrected acquisitions are complete. The
first partial archive remains unverified and is not used. Account for all transfers within the
50 GB cap. The grouped corpus and both runs are verified; finish provenance and relationship
checks, resolve the unmatched review-workload protocol, and complete the review handoff.

Second host: the recipe, corpus, both runs, the link record and the portable review archive are
complete and verified. The task stays open and RUN NEEDED. It waits on the human link review
(`review-pilot-recording-links`), which uses the archive above and independently creates the
dataset on its host. Then apply the decisions, regroup and rerun when needed, compare the
identities, measure or report the colour-score effect, and present `discover blind`. The
capability remains planned.
