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

## Acceptance evidence

The source-acquisition regression tests pass, including a mocked native record with matching and
mismatched versions, invalid indexes and media type. `make ci` passed: 2278 tests passed, 112
deselected. The real pilot remains in progress and is not established by these fixture tests.

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
- Further audit is pending.

## Close or resume

The owner suspended the run for a network change and then requested downloads resume. The
WetlandBirds transfer initially stopped and a later retry reached 2885681152 confirmed bytes
before Zenodo returned HTTP 500. A bounded resumable retry reused the confirmed prefix and
transferred 6546933699 further bytes. The complete archive passed its published MD5, and the
standard acquisition verified and extracted it. Both corrected acquisitions are complete. The
first partial archive remains unverified and is not used. Account for all transfers within the
50 GB cap. The grouped corpus and both runs are verified; finish provenance and relationship
checks, resolve the unmatched review-workload protocol, and complete the review handoff.
