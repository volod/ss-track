# Perception Bench test plan

Requirements for the [engine design](perception-bench-engine.md) and
[spec section 16](spec.md#16-benchmark-extensions-hardware-selection-and-reference-sensor-mesh).
Each case
names the [plan](../impl/plan.md) task that owns it. Value lines state what the test protects, what
makes it fail, and what it does not prove. A case with no task left is listed as existing behavior.

## Existing behavior to protect

- `ss-track info` stays unchanged as subcommands are added. `tests/test_cli.py` already covers it.
- Truncated, zero-length, wrong-hash, non-increasing PTS and selection-past-end inputs stay
  structured refusals. `tests/corpus/` covers them.
  Value: protects=structured refusal; fails_when=a bad source yields a score; no_claim=real decoder
  coverage.
- One source staged twice gives one bundle hash, and a corrupted frame fails verification by name.
  `tests/corpus/` covers them.
  Value: protects=identical input for every module; fails_when=the hash drifts or corruption passes;
  no_claim=cross-platform decoders.
- An encounter with two streams, an encounter, stream, group or source that crosses a split, a bundle
  moved to another stream, and a rights conflict all stay structured refusals. `tests/corpus/` covers
  them.
  Value: protects=no leakage across splits; fails_when=a stream crosses a split; no_claim=grouping
  judgment on real footage, or a remuxed copy of one recording.
- A generated case rerun with one seed stays byte-identical, stays in its parent's encounter and split
  and adds nothing to any evidence count. `tests/corpus/` covers them.
  Value: protects=reproducible cases that are not encounters; fails_when=a case counts as new
  evidence; no_claim=realism.

## Fixture-level cases

### Input and evidence

- `annotation-contract`: malformed labels, an unverifiable label, and seed replay.
  Value: protects=frozen truth; fails_when=an unverifiable label scores zero; no_claim=label quality.
- `annotation-review-tools`: hand-built disagreements between two label sets.
  Value: protects=review before freezing; fails_when=an unresolved case freezes; no_claim=reviewer
  skill.
- `source-terms-enforcement`: a source one day either side of its retention date, and a generated case
  of a source that forbids derived frames.
  Value: protects=recorded terms; fails_when=a source outside its terms is staged; no_claim=legal
  sufficiency of the declared terms.
- `corpus-verify-rights`: a source re-imported under narrower rights after staging.
  Value: protects=a verified corpus means valid rights; fails_when=verify passes on withdrawn rights;
  no_claim=the truth of a declaration.
- `source-terms-amendment`: a source amended to `restricted` after staging, and a changed file
  declared as an amendment.
  Value: protects=a withdrawal that can be recorded; fails_when=stored bytes change or an amendment
  carries more than terms; no_claim=removal of frames already staged.
- `corpus-version-lineage`: a source moved between splits, and a source added, across linked versions.
  Value: protects=split isolation over time; fails_when=a moved source builds; no_claim=versions that
  declare no predecessor.
- `staged-frame-set`: two stagings of one corpus, a replaced bundle and an interrupted stage.
  Value: protects=one pin for all staged input; fails_when=a changed bundle keeps its frame set;
  no_claim=undeclared files outside the corpus.
- `duplicate-frame-detection`: a remux across two splits, and two clips sharing a black frame.
  Value: protects=split isolation for remuxed copies; fails_when=identical frames cross a split or a
  shared black frame is refused; no_claim=re-encoded copies.
- `arm64-reproducibility`: golden transforms and tree hashes of one corpus on x86-64 and arm64.
  Value: protects=a stated cross-architecture boundary; fails_when=a difference goes unrecorded;
  no_claim=macOS, or timing.
- `generated-case-labels`: hand-built labels through each transform, and a plate showing a target.
  Value: protects=labels that follow pixels; fails_when=a covered target stays visible or a wrong
  region yields `absent`; no_claim=parent label quality.
- `event-schema-contract`: golden fixtures, unknown fields, malformed payloads and regenerated
  bindings.
  Value: protects=one meaning for every event; fails_when=generated code drifts from `.proto`;
  no_claim=C++ round trips.
- `scenario-contract`: each cohort-key field changed in turn, and a scenario with a missing hash.
  Value: protects=comparison identity; fails_when=a changed input keeps its key; no_claim=none
  beyond protects.
- `run-bundle-store`: a crash during write, a retried ID, and a bundle with no visibility value.
  Value: protects=complete immutable evidence and restricted by default; fails_when=a partial bundle
  reads as complete; no_claim=disk failure modes.

### Execution

- `lockstep-runner`: oracle, null, dropper, crash, schema and class-identity modules.
  Value: protects=exact frame accounting; fails_when=a dropped frame leaves the denominator;
  no_claim=paced behavior.
- `locked-split-guard`: a development scenario naming a locked stream, and an approved re-score.
  Value: protects=held-out material and its audit trail; fails_when=the run starts or a read goes
  unrecorded; no_claim=access control against someone with disk access.
- `paced-frame-release`: a fixture module attempts to read a future frame.
  Value: protects=causal input; fails_when=the read succeeds; no_claim=defense beyond the channel.
- `paced-frame-release`: a slow module against an injected clock.
  Value: protects=late and dropped frames count as misses; fails_when=a late answer scores;
  no_claim=host jitter.
- `reference-sot-tracker`: perfect observation, a miss, a distractor, occlusion and re-entry, rerun
  with one seed.
  Value: protects=a deterministic baseline; fails_when=a stale box passes as a detection;
  no_claim=tracking quality.
- `host-capability-probe`: recorded hosts, including one with no frequency cap.
  Value: protects=explicit support status; fails_when=a missing feature reports `SUPPORTED`;
  no_claim=sustained behavior.
- `container-module-sandbox`: a hostile module tries a socket, a label path and a future frame.
  Value: protects=isolation; fails_when=any attempt succeeds; no_claim=a deliberate container escape.
- `temperature-run-orchestration`: module state between runs, and block order over seeds.
  Value: protects=heat as the only difference; fails_when=state carries or order is unbalanced;
  no_claim=rig quality.

### Scoring

- `plugin-evaluator-core`: a saved bundle recomputed in a second process.
  Value: protects=the Recompute level; fails_when=scoring reads outside the bundle; no_claim=hardware
  re-measurement.
- `sot-suite`: hand-computed coverage, retention and time weights, and a late result in
  `sot-paced-v1`.
  Value: protects=metric formulas; fails_when=a denominator changes; no_claim=task adequacy.
- `motion-suite`: oracle and null modules.
  Value: protects=event scoring; fails_when=a null module is `NOT_SCOREABLE`; no_claim=general
  detection.
- `development-decision-status`: each status, and fewer than 10 groups.
  Value: protects=honest decisions; fails_when=overlap reports a gain; no_claim=public sample size.
- `local-comparison-report`: compatible and incompatible cohorts.
  Value: protects=refused comparisons; fails_when=an incompatible pair is compared; no_claim=public
  output.
- `trackeval-adapter`: perfect, miss, false positive, ID switch and ignore fixtures.
  Value: protects=a pinned evaluator on Python 3.12; fails_when=an export shifts by one;
  no_claim=a real MOT corpus.
- `power-trace-ingest`: constant, pulsed, gap, clipped and drifting traces.
  Value: protects=joules over an exact interval; fails_when=joules integrate across a gap;
  no_claim=instrument accuracy.
- `energy-metric-suite`: a module that emits few results.
  Value: protects=scheduled-frame denominator; fails_when=fewer outputs lower energy per frame;
  no_claim=real power.
- `hardware-trial-protocol`: invalid, misaligned and partially instrumented trials.
  Value: protects=per-quantity validity and retained attempts; fails_when=missing energy erases valid
  quality evidence; no_claim=real supply behavior.
- `thermal-rig-controller`: a load step, and a temperature excursion during a segment.
  Value: protects=thermal validity; fails_when=an out-of-band run counts; no_claim=the physical rig.
- `thermal-effect-evaluation`: an improvement, a loss the capped arm does not reproduce, and a hot run
  with no throttling.
  Value: protects=direction and cause; fails_when=an improvement supports the thermal hypothesis;
  no_claim=that throttling hurts real trackers.
- `load-calibrated-baseline`: lockstep output with and without load.
  Value: protects=a mechanism baseline that changes time only; fails_when=the load changes results;
  no_claim=any tracker's behavior.

### Optional ranking and shareable exports

- `rank-engine`: floor cleared in two runs and missed in one.
  Value: protects=every-run floor; fails_when=only the ranked run is checked; no_claim=real interval
  widths.
- `rank-engine`: an even valid-run count, and a median tie.
  Value: protects=one deterministic row; fails_when=values mix across runs; no_claim=none beyond
  protects.
- `rank-engine`: A overlaps B and B overlaps C, but A does not overlap C.
  Value: protects=anchored tiers; fails_when=ties chain; no_claim=real meter uncertainty.
- `rank-engine`: a `MODULE_FAULT` row, including on the last tier.
  Value: protects=one-tier penalty; fails_when=the row keeps its tier or vanishes; no_claim=crash
  causes.
- `rank-engine`: a null row, a baseline, unmeasured energy, and two qualifying projects.
  Value: protects=unranked groups and the minimum; fails_when=a null row is subtracted or two rows
  rank; no_claim=none beyond protects.
- `rank-engine`: insufficient valid runs and an invalid attempt with its replacement retained.
  Value: protects=declared repetition rules; fails_when=invalid attempts disappear; no_claim=hardware
  fault cause.
- `rank-engine`: a false-continuation cap breach, and low scorable exposure.
  Value: protects=floor companions; fails_when=a confident stale track ranks; no_claim=task adequacy.
- `visibility-gate`: a restricted bundle and an unmarked bundle passed to the builder.
  Value: protects=restricted data; fails_when=any restricted value reaches output; no_claim=none
  beyond protects.
- `benchmark-report-snapshot`: a rebuild, and an empty cohort.
  Value: protects=citable snapshots; fails_when=a rebuild differs; no_claim=hosting.

### Hardware selection

- `hardware-selection-report`: a datasheet-only option, a shared rail, incompatible trials, missing task
  quality, uncertainty crossing a requirement, and no qualifying configuration.
  Value: protects=measured choices and honest ledgers; fails_when=an unmeasured option is chosen;
  no_claim=that the choice is best outside the stand.

### Reference sensor mesh

- `g2-scenario-observation-bundles`: mixed-modality streams, changed producers/calibration/schedule,
  cross-split streams and an attempted raw-input read by a fixed-input module.
  Value: protects=immutable comparable boundary inputs; fails_when=forbidden input is accepted;
  no_claim=physical synchronization.
- `synchronized-sensor-capture`: fake drivers with skew, queue overflow, disconnect, recovery and
  interrupted shutdown.
  Value: protects=explicit capture accounting and released devices; fails_when=loss vanishes or
  receive time becomes capture time; no_claim=live driver performance.
- `fusion-calibration-suite`: known probability outcomes, correlated sources, absent independent
  labels and calibration/evaluation leakage.
  Value: protects=proper scores and honest probability claims; fails_when=uncalibrated scores become
  posteriors; no_claim=generalization outside the calibration population.
- `g2-boundary-report`: four suites, missing quantities and incompatible input bundles.
  Value: protects=separate attribution and visible limits; fails_when=a component score appears as
  whole-system quality; no_claim=live performance.

- `joint-mode-probe`: recorded sensor sets, including a pair that passes alone and fails together.
  Value: protects=joint-mode truth; fails_when=single-sensor passes imply a joint mode; no_claim=real
  bus behavior.
- `camera-trial-suite`: recorded traces with known drops, extent and timing.
  Value: protects=measured capture quality; fails_when=requested fps replaces measured fps;
  no_claim=field optics.
- `sensor-observation-contract`: golden records for each observation state.
  Value: protects=typed evidence; fails_when=`missing` reads as `no_detection`; no_claim=sensor
  quality.
- `camera-front-end` and `non-camera-front-end`: recorded inputs, coverage and failure states.
  Value: protects=explicit negative and failure events; fails_when=an out-of-view source counts as a
  negative; no_claim=detection range.
- `event-time-replay`: late, reordered and skewed events, plus a changed future with a fixed past.
  Value: protects=causal input; fails_when=a future event enters a decision; no_claim=real clocks.
- `late-fusion-baseline`: correlated duplicates, contradictions and ambiguous matches.
  Value: protects=lineage and no false merge; fails_when=correlated evidence counts twice;
  no_claim=fusion gain.
- `fusion-suite`: byte-identical observation bundles with fixed epochs.
  Value: protects=fusion-only attribution; fails_when=a changed front end keeps its cohort;
  no_claim=whole-system quality.
- `tracker-epoch-suite`: crossing, misses, occlusion, re-entry and prediction-only epochs.
  Value: protects=tracker-only attribution; fails_when=a tracker reads raw pixels; no_claim=front-end
  quality.
- `mesh-reference-tracker`: the section 7.8 fixture list for sources, deadlines and lineage.
  Value: protects=one acknowledgment per epoch and exact lineage; fails_when=prediction passes as
  measurement; no_claim=an accuracy ceiling.
- `sensor-set-suite`: single, paired, all-installed and leave-one-out sets.
  Value: protects=what each sensor adds; fails_when=the oracle ceiling reads as achieved quality;
  no_claim=uninstalled sensors.
- `installed-system-suite`: quality and energy from the same trial.
  Value: protects=whole-system pairing; fails_when=values mix across trials; no_claim=component
  causes.

### Optional device bench evaluation

- `device-suite-and-adapter`: a device with no output path and mismatched stimulus/reference/boundary.
  Value: protects=unranked comparable cases; fails_when=an unmatched pair is compared;
  no_claim=real devices or device ranking.

### Plan tooling

- `plan-dependency-integrity`: an unknown dependency, a cycle, a required task depending on optional
  work, a valid cross-lane dependency and a wrapped field.
  Value: protects=gating that stays real; fails_when=a broken dependency passes; no_claim=semantic
  review.

## End-to-end paths

- `g0a-pipeline-run`: corpus and labels through scenario, run, bundle, suites and report.
  Value: protects=the offline chain; fails_when=any stage changes frame accounting; no_claim=hardware
  energy.
- `run-thermal-experiment`: identical frames cool, hot and capped on the reference host.
  Value: protects=the thermal hypothesis; fails_when=a condition is skipped; no_claim=other tracker behavior.
- `independent-rerun-check`: a second person recomputes every row and re-runs one open module or
  reference baseline, including a cohort with no ranked rows.
  Value: protects=the reproducibility promise; fails_when=a value differs beyond tolerance;
  no_claim=Re-measure.
- `select-reference-host`: two or more measured candidates, a provisional single-candidate
  choice and no qualifying host.
  Value: protects=a data-driven host; fails_when=a candidate has no evidence; no_claim=other hosts.
- `run-mesh-trials`: the installed mesh across all four G2 boundaries.
  Value: protects=the reference mesh goal; fails_when=a boundary is skipped; no_claim=field behavior.

## Bench checks

- `calibrate-bench-instruments`: known load, marker alignment, pacing jitter, staging throughput and
  null-module energy.
- `build-thermal-rig`: chip held in band under load at a set-point at or above measured onset.
- `tracker-compatibility-preflight`: adapters pass or explicitly fail schema, isolation and schedule
  checks on the selected host; no external-project count gates the mesh.
- `run-camera-characterization`: shortlisted cameras have delivered rate, drops, extent and
  clock alignment on Stand B before final selection.
- `select-mesh-sensors`: non-camera positive/negative observability, joint modes and energy meet
  frozen requirements before the choice is recorded; absent evidence cannot pass.
- `record-mesh-encounters`: selected live capture retains clock markers, raw hashes, reviewed
  opportunity/identity labels and disjoint calibration/evaluation encounters.

## Tests to Retire

- none

## Pending engineering choices

Runtime, decoder, evaluator and hardware-specific fixtures follow the owning plan tasks.
Their live acceptance requires recorded hardware evidence; fixture passes alone are insufficient.
