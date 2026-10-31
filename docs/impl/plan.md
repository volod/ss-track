# ss-track Implementation Plan

Forward-only: this file contains software implementation and the human evidence work needed for
correct benchmarks and a reference sensor mesh tracker. Available behavior belongs in
[current-state documentation](current.md); scope and evaluation belong in the
[specification](../design/spec.md).

The Agent lane builds deterministic software and fixtures. The Human-Assisted lane supplies
authorized data, reviewed labels, stand requirements, calibrated measurements and documented hardware
selection. Hardware choices must name the software need, measured alternatives and unresolved limits.
Commercial strategy, staffing, public entry policy, publication operations and launch work are kept
in an owner-managed organizational to-do outside this repository's Git control. They do not gate
software acceptance.

Groups follow the [capability registry](../design/spec.md#capability-registry). Follow explicit
dependencies across both lanes; group priority does not imply a predecessor is complete. Required
work takes priority over optional refinements. `make plan-status` reports counts and the first task
by priority in each lane; dependency readiness must currently be checked from the task fields.

See the [planning workflow](../guide/planning-workflow.md),
[engine milestone map](../design/perception-bench-engine.md#milestone-map),
[test plan](../design/perception-bench-test-plan.md)
and [test-stand requirements](../design/test-stands.md). M1 is the small G0a pipeline, M2 supplies
measurement and host selection, and M3 delivers the reference mesh. M4 and M5 are optional extensions;
neither blocks M3. Fixture implementation proceeds without physical hardware or private data.

## Agent Implementation Tasks

### Corpus provenance -- `corpus-provenance`

#### corpus-manifest-import

Recordings need stable identity before anything can be replayed or compared.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator imports a source and gets a hashed manifest with rights,
  sensitivity and timestamp-quality fields, or a structured refusal.
- Scope boundary: Import, hashing and the canonical decode policy. One pinned decoder is chosen here
  and must have arm64 wheels. Staging and annotation are later tasks.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Add `ss-track import` and `ss-track corpus build` in `src/ss_track/cli.py`, keeping
  logic in `src/ss_track/corpus/`, with small synthetic media fixtures and the smallest justified
  decoder dependency in `uv.lock`.
- Acceptance gates: Truncated, zero-length, wrong-hash, non-increasing PTS and selection-past-end
  fixtures yield a structured failure and never a fabricated value. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), new page `current/corpus.md`.

#### frame-bundle-staging

Every module must see exactly the same decoded frames.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: corpus-manifest-import.
- User-visible outcome: An operator stages one immutable decoded-frame bundle with a frame index and
  per-frame hashes.
- Scope boundary: Staged raw frames, `FrameRef` data and random access by frame index. Network
  delivery and later packet paths are out of scope.
- Data and artifact paths: `src/ss_track/corpus/`, `$DATA_DIR/corpus/<corpus-id>/frames/`.
- Execution path: Add staging that records pixel format, dimensions and bundle hash, with fixtures
  for a clean decode and a corrupted frame.
- Acceptance gates: Two stagings of one source give one bundle hash. A corrupted frame fails
  verification by name.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### corpus-split-grouping

Related frames must stay together, or evaluation leaks across splits.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: corpus-manifest-import.
- User-visible outcome: Corpus versions keep each encounter intact across development, calibration
  and locked splits, including every stream of a multi-stream encounter.
- Scope boundary: Grouping, split membership, stream identity and scenario rights. A locked test and
  near-duplicate detection are out of scope.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add encounter and stream records and split rules with deterministic fixtures.
- Acceptance gates: Fixtures prove no encounter or stream crosses a split. A rights conflict refuses
  the corpus build.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### generated-fixture-cases

Failure mechanisms need cheap, repeatable cases that do not count as field evidence.

- Serves: `corpus-provenance` -- [Deterministic cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: frame-bundle-staging, corpus-split-grouping.
- User-visible outcome: A recipe generates target absence, moving background, shake, blur, dropped
  frames and short occlusion cases from a parent sequence and seed.
- Scope boundary: The spec section 4.3 initial cases. Fusion perturbations are out of scope.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add versioned transforms that store parent, seed and label transform.
- Acceptance gates: A rerun with one seed is byte-identical. A generated case inherits its parent's
  encounter and split and never counts as a new encounter.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Annotation and selection -- `annotation-selection`

#### annotation-contract

Labels need stable identity and a frozen mask before scores can mean anything.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: corpus-manifest-import.
- User-visible outcome: An operator validates visibility status, geometry, instance identity, motion
  events, operator seeds and masks against a versioned schema.
- Scope boundary: Schema, validation and frozen seed replay. Labelling itself is human work.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add `ss-track annotate validate` with positive and malformed fixtures.
- Acceptance gates: Identical seeds replay identically, and invalid labels are rejected with a reason.
  An unverifiable label stays unscorable and is never scored as zero.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### annotation-review-tools

Two reviewers must be able to compare labels and settle disagreement.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: annotation-contract.
- User-visible outcome: Reviewers see disagreements and freeze one hashed label revision, with a
  sensitivity band retained for scoring.
- Scope boundary: Comparison, a recorded rationale, freezing, and a declared review sample for larger
  corpora. A labelling interface is out of scope.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add agreement reports over two label sets with fixtures.
- Acceptance gates: Hand-built disagreements are reported exactly. An unresolved disagreement blocks
  the freeze or stays `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Module contract and runner -- `module-contract-runner`

#### event-schema-contract

Python and later C++ modules need one versioned meaning for every event.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Modules and tools share a validated event schema with golden fixtures.
- Scope boundary: The G0 and G1 record families. G2 fusion records are out of scope.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Define `.proto` files and protobuf-JSON JSON Lines validation. Add a Make target
  that regenerates bindings and a CI drift check, keep generated files out of the size and lint
  gates, and add the smallest justified dependency to `uv.lock`.
- Acceptance gates: Golden fixtures cover absent and unknown fields, malformed payloads, coordinates,
  timestamps and power units. A malformed event is rejected with a reason.
- Documentation target: [Current implementation](current.md#areas), new page `current/runner.md`.

#### scenario-contract

A comparison must pin everything that can change its result.

- Serves: `module-contract-runner` -- [Run artifacts](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: event-schema-contract, corpus-split-grouping, annotation-contract.
- User-visible outcome: A scenario file pins corpus, labels, selection, replay mode, metric suite,
  seed and deadlines, and yields one cohort key.
- Scope boundary: The scenario schema, one cohort-key function, and one type that owns windows and
  runs. G2 boundaries are out of scope.
- Data and artifact paths: `src/ss_track/contract/`, `scenarios/`, `tests/contract/`.
- Execution path: Add the schema and example scenarios, with table-driven cohort-key fixtures.
- Acceptance gates: Changing any key field changes the cohort key. A scenario with a missing hash
  refuses to run.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### run-bundle-store

Every score must be recomputable from immutable evidence.

- Serves: `module-contract-runner` -- [Run artifacts](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: scenario-contract.
- User-visible outcome: A run leaves a complete read-only bundle, or one marked incomplete.
- Scope boundary: The spec section 10 artifact set, write-then-rename finalize, idempotent IDs, and a
  visibility field that defaults to restricted. `loc-lm-bench` is a pattern to check, not an import.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Add bundle reader and writer with crash and retry fixtures.
- Acceptance gates: A crash fixture leaves no complete-looking bundle, a retried ID stays idempotent,
  and each manifest records its re-run command. A bundle with no visibility value reads as restricted.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### lockstep-runner

G0 needs a runner that accounts for every frame.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: run-bundle-store, frame-bundle-staging.
- User-visible outcome: `ss-track run` replays a scenario and reports exact frame accounting.
- Scope boundary: Lockstep execution and fault semantics. Paced timing is a later task.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add the runner with oracle, null, dropper, crash, schema and class-identity
  fixture modules. The null module becomes a reusable module, not only a test double.
- Acceptance gates: The G0a anti-gaming and null rows of the acceptance matrix pass. A crash is
  `MODULE_FAULT` with remaining scorable input missed, and a wrong source hash is `RUNNER_INVALID`.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### paced-frame-release

A module must not see a frame before its time, or paced results are false.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: lockstep-runner.
- User-visible outcome: Paced runs score late and dropped frames as misses, and a read-ahead attempt
  fails conformance.
- Scope boundary: Fixed schedule, per-frame deadline, one-frame release channel, lifecycle messages,
  and a pacing jitter log. Real-time scheduling claims are out of scope.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add runner-controlled release with an injected clock, so tests stay deterministic,
  plus lookahead and slow-module fixtures.
- Acceptance gates: The lookahead fixture cannot read a future frame. The slow fixture records exact
  late and miss counts with no wall-clock dependence.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### container-module-sandbox

Third-party code must not reach labels, the network or restricted data.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: RUN NEEDED
- Milestone: M2
- Dependencies: paced-frame-release.
- User-visible outcome: A reference, null or candidate module runs in a pinned container with
  limits applied.
- Scope boundary: No network, no label path, no mount of future frames, resource limits and a fresh
  container per run. Runtime choice happens here; the selected-host proof is part of
  `calibrate-bench-instruments`.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`, `modules/null/`.
- Execution path: Add the launcher, a hostile fixture module and a separate Make target for the
  container check, so `make ci` stays network-free. Declared run: that target on a host with the
  chosen runtime.
- Acceptance gates: The hostile fixture fails to open a socket, a label path or a future frame. If no
  runtime suits the host, the task records the blocker and does not weaken isolation.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### module-image-recipes

Anyone re-running a row needs the exact module that was measured.

- Serves: `module-contract-runner` -- [Module reproducibility](../design/spec.md#163-module-reproducibility)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: container-module-sandbox, reference-sot-tracker.
- User-visible outcome: Reference and null modules have reproducible recipes, pinned image digests and
  license notices; candidate adapters follow the same contract.
- Scope boundary: Recipes, digests and license notices. Tracker tuning and registry hosting are
  out of scope.
- Data and artifact paths: `modules/<name>/`.
- Execution path: Record recipes and digests in the manifest. Keep third-party dependencies outside the
  core lock; add a recipe when an adapter is introduced.
- Acceptance gates: The declared image digest can be obtained or rebuilt with any difference explained.
  Missing image access is reported as unavailable; no different image silently substitutes for it.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### tracker-compatibility-preflight (optional)

External tracker adapters need conformance evidence on the selected host.

- Serves: `module-contract-runner` -- [Module reproducibility](../design/spec.md#163-module-reproducibility)
- Agent status: RUN NEEDED
- Milestone: M4
- Dependencies: module-image-recipes, select-reference-host.
- User-visible outcome: Declared trackers have pass/fail compatibility records on the reference host.
- Scope boundary: Synthetic-frame schema, isolation and schedule checks with upstream defaults.
  Benchmark scores, entry policy and a mandatory number of projects are out of scope.
- Data and artifact paths: `modules/<tracker>/`, `$DATA_DIR/preflight/<run-id>/`.
- Execution path: Choose adapters needed for the comparison and record their license and configuration.
  Keep recipes under `modules/`. Declared run: each container on the selected reference host.
- Acceptance gates: Each adapter has an explicit supported or unsupported result and timing evidence.
  Zero compatible candidates is valid and does not block the reference implementation.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

### Motion and tracking evaluation -- `motion-sot-evaluation`

#### plugin-evaluator-core

Every suite needs one way to score saved evidence.

- Serves: `motion-sot-evaluation` -- [Metric-suite validity](../design/spec.md#6-metric-suite-validity-and-primary-g0-metrics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: run-bundle-store.
- User-visible outcome: Suites score a saved bundle, and a second process recomputes identical bytes.
- Scope boundary: The TrackEval plugin shape over read-only bundles, with
  `aggregate(level, children)` for episode, encounter, run and block. TrackEval itself is out of
  scope here.
- Data and artifact paths: `src/ss_track/evaluator/`, `tests/evaluator/`.
- Execution path: Add suite and dataset interfaces, the evaluator loop, and one fixture suite that
  exercises the run and block levels.
- Acceptance gates: Recomputing a fixture bundle in a second process is byte-identical. A suite that
  reads outside its bundle fails.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/evaluation.md`.

#### sot-suite

Operators need tracking scores that cannot be gamed by omission.

- Serves: `motion-sot-evaluation` -- [Tracking suite](../design/spec.md#61-operator-selected-tracking-sot-v2-dev)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: plugin-evaluator-core, annotation-contract.
- User-visible outcome: Reports show lock coverage, horizon retention and exposure with denominators.
- Scope boundary: `sot-v2-dev`, and `sot-paced-v1` scoring of late and missing results. Absence and
  re-entry diagnostics are included. Later suites are out of scope.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add hand-computed fixtures for every metric, in table-driven tests.
- Acceptance gates: Hand-computed metrics, denominators and time weights match, and a late result
  counts as a miss in `sot-paced-v1`. An episode with no scorable frame is `NOT_SCOREABLE`.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### motion-suite

Motion proposals need their own event scores.

- Serves: `motion-sot-evaluation` -- [Motion proposals](../design/spec.md#62-motion-proposals-motion-v1-dev)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: plugin-evaluator-core, annotation-contract.
- User-visible outcome: Reports show event recall, detection delay and operator-burden proposals.
- Scope boundary: `motion-v1-dev` only. It is no general detection claim.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add matching-order fixtures and hand-computed recall.
- Acceptance gates: Oracle fixtures reach recall 1 with zero burden proposals. A null module scores a
  `VALID` zero and never `NOT_SCOREABLE`.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### development-decision-status

Maintainers need a rule for saying whether a version improved.

- Serves: `motion-sot-evaluation` -- [Comparisons](../design/spec.md#63-comparisons-and-decision-status)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: sot-suite.
- User-visible outcome: Paired comparisons report improved, regressed, `inconclusive` or
  `insufficient_data` per metric, and a noise floor.
- Scope boundary: Noise floor, seeded encounter-cluster bootstrap and status rules. Public ranks are
  out of scope.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add statistics with deterministic seeded fixtures.
- Acceptance gates: Fixtures reproduce each status. Fewer than 10 encounter groups yields
  `insufficient_data`, and a rerun with one seed is byte-identical.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Reference tracker -- `reference-tracker`

#### reference-sot-tracker

The benchmark needs a simple, inspectable baseline.

- Serves: `reference-tracker` -- [Reference tracker](../design/spec.md#78-tdd-reference-tracker-and-stagewise-development)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: lockstep-runner, sot-suite.
- User-visible outcome: A deterministic seeded tracker and its motion proposal front end run through
  the contract in two declared versions, so G0a has a real comparison.
- Scope boundary: The single-camera path. The staged multi-source tracker belongs to M3.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference/`.
- Execution path: Add a bounded motion proposal, a constant-velocity Kalman model, geometry gates and
  tentative, confirmed, lost and reacquired states.
- Acceptance gates: The G0a reference tracker row of the acceptance matrix passes on rerun with one
  seed. A predicted stale box cannot pass as a measured detection.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/reference-tracker.md`.

#### load-calibrated-baseline (optional)

A light tracker has spare time, so it cannot show whether heat costs quality.

- Serves: `reference-tracker` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: reference-sot-tracker.
- User-visible outcome: The reference tracker gains a declared load setting that places its cool-run
  compute near the frame deadline.
- Scope boundary: One documented load setting recorded in the manifest. It is an unranked mechanism
  baseline and never a tracking result.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`.
- Execution path: Add the setting and a fixture that shows it changes compute time only.
- Acceptance gates: The output with load matches the output without load on a lockstep fixture. A
  setting that leaves no deadline margin in a cool run is refused.
- Documentation target: [Current implementation](current.md#areas), page
  `current/reference-tracker.md`.

### Comparison report -- `comparison-report`

#### local-comparison-report

Maintainers need to inspect two versions and see every exclusion.

- Serves: `comparison-report` -- [Comparison dashboard](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: development-decision-status.
- User-visible outcome: `ss-track compare` writes a local HTML and JSON report, or refuses with a
  reason.
- Scope boundary: Local report with visibility retained. Shareable export uses `visibility-gate`.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Build the report from saved metrics with compatible and incompatible fixtures,
  including frame-linked failure references.
- Acceptance gates: An incompatible cohort is refused with its reason, and the report never edits or
  recomputes source metrics.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### g0a-pipeline-run

The whole offline path must work on real labelled video.

- Serves: `comparison-report` -- [Delivery gates](../design/spec.md#3-scope-and-delivery-gates)
- Agent status: RUN NEEDED
- Milestone: M1
- Dependencies: local-comparison-report, reference-sot-tracker, motion-suite,
  generated-fixture-cases, label-pilot-encounters.
- User-visible outcome: Two reference versions produce an inspectable G0a report on one positive and
  one negative encounter.
- Scope boundary: G0a pipeline validity. No improvement, real-time or energy claim.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Declared run of the G0a scenario through `ss-track run` and `ss-track compare`.
- Acceptance gates: Every G0a row of the acceptance matrix passes. A failed row is reported with its
  cause, and M1 stays open until it is resolved.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### visibility-gate

Restricted data must be unable to reach public output.

- Serves: `comparison-report` -- [Comparison artifacts](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: run-bundle-store.
- User-visible outcome: An explicitly requested shareable export refuses any bundle not marked public.
- Scope boundary: One gate for shareable exports. Local restricted analysis remains available; publishing
  artifacts or operating a public site is outside the repository workflow.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Add the gate as the only public read path, with an import-boundary test.
- Acceptance gates: A restricted or unmarked bundle passed to the builder fails, and no restricted
  value reaches output.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### g0b-decision-run (optional)

Maintainers may want a real development decision before any bench exists.

- Serves: `comparison-report` -- [Comparisons](../design/spec.md#63-comparisons-and-decision-status)
- Agent status: RUN NEEDED
- Milestone: M1
- Dependencies: g0a-pipeline-run, label-development-corpus.
- User-visible outcome: Two versions get a within-corpus decision status on 10 encounter groups.
- Scope boundary: A development-corpus decision. G0a and mesh implementation proceed independently.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Declared run of three same-version repeats plus the paired comparison.
- Acceptance gates: The G0b row of the acceptance matrix passes. An overlapping interval reports
  `inconclusive`.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Hardware probe -- `hardware-probe-adaptive-launch`

#### host-capability-probe

A trial must start from what the host really supports.

- Serves: `hardware-probe-adaptive-launch` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: event-schema-contract.
- User-visible outcome: `ss-track hardware-probe` writes a host profile with explicit support status.
- Scope boundary: CPU, memory, storage, scheduler, governor, frequency and throttle evidence, and
  whether frequency can be capped. Sensors belong to `joint-mode-probe`; accelerators stay in
  spec section 12.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`, `$DATA_DIR/probe/<host-id>/`.
- Execution path: Read system facts behind a replaceable source, with recorded fixture hosts,
  including Raspberry Pi `vcgencmd` evidence.
- Acceptance gates: Recorded hosts produce expected profiles. An unavailable feature yields
  `UNSUPPORTED` or `MEASURE_REQUIRED`.
- Documentation target: [Current implementation](current.md#areas), new page `current/bench.md`.

### Controlled bench, timing and energy -- `controlled-bench-timing-energy`

#### power-trace-ingest

Energy claims need raw traces and honest integration.

- Serves: `controlled-bench-timing-energy` -- [Electrical power](../design/spec.md#794-electrical-power-thermal-state-and-motion)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: run-bundle-store.
- User-visible outcome: A meter trace becomes joules over an exact marked interval, with uncertainty.
- Scope boundary: File-based trace ingest, trapezoid integration, gaps, saturation and marker-based
  clock alignment. Live meter control is out of scope, so any meter can feed it.
- Data and artifact paths: `src/ss_track/energy/`, `tests/energy/`.
- Execution path: Add constant-power, pulsed-power, sample-gap, saturation and clock-drift fixtures.
- Acceptance gates: Hand-calculated joules match. A gap, clipped sample or failed alignment in the
  interval yields `NOT_MEASURABLE` with the raw trace kept.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### energy-metric-suite

The ranked energy number must come from a scored suite, not an ad-hoc calculation.

- Serves: `controlled-bench-timing-energy` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: power-trace-ingest, plugin-evaluator-core.
- User-visible outcome: A run reports joules per scheduled frame, mean and sampled peak watts, and
  scheduled and emitted counts, each with uncertainty.
- Scope boundary: Run-level energy and the energy interval. Idle subtraction stays secondary, and
  ranking is a later task.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite against recorded traces and a declared uncertainty budget.
- Acceptance gates: Hand-calculated values and intervals match. A module that emits few results gains
  no energy advantage from a changed denominator.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### hardware-trial-protocol

Hardware results need a versioned protocol declared before acquisition.

- Serves: `controlled-bench-timing-energy` -- [Hardware metrology](../design/spec.md#79-hardware-metrology-and-measurement-algorithms)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: energy-metric-suite, host-capability-probe.
- User-visible outcome: `ss-track hardware-measure` runs a declared protocol into a `HardwareTrial`
  bundle.
- Scope boundary: Versioned protocol, preflight checks, order, instrument records, timing/resource
  estimates and validity. Camera optics and vibration are in `camera-trial-suite`.
  Optional ranking replacement rules apply only when that protocol is selected.
- Data and artifact paths: `src/ss_track/energy/`, `tests/energy/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Add the protocol schema and fixtures that replay recorded traces.
- Acceptance gates: Fixtures reproduce timing, resource and energy estimates with explicit units and
  uncertainty. Missing instruments invalidate only affected claims. Every invalid attempt remains
  in the bundle; ranking-specific repetition rules never gate a basic bench measurement.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Hardware selection -- `hardware-selection`

#### hardware-selection-report

Hardware choices need a repeatable comparison that keeps its evidence.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: hardware-trial-protocol.
- User-visible outcome: `ss-track hardware-select` compares measured candidates against a stand's
  requirements and budget, and writes a selection record with an energy ledger.
- Scope boundary: Measured configurations only. Datasheet options stay labelled unmeasured, and no
  simulation, prediction or public ranking is included.
- Data and artifact paths: `src/ss_track/selection/`, `tests/selection/`, `scenarios/stands/`,
  `$DATA_DIR/selection/<selection-id>/`.
- Execution path: Add versioned stand requirement files with quality, coverage, timing, interface, storage,
  power and thermal limits and their software consumers. Compare only like-for-like declared trials;
  ledgers keep shared rails shared. Use table-driven fixtures for uncertainty and missing evidence.
- Acceptance gates: A datasheet option is never chosen as measured. Missing required evidence, uncertainty
  across a limit or incompatible workloads cannot produce a qualified choice. No qualifying
  configuration is a valid result; an inaccessible boundary is `NOT_MEASURABLE`.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/hardware-selection.md`.

### Sensor joint-mode probe -- `sensor-joint-mode-probe`

#### joint-mode-probe

A mesh needs sensors that work together, and separate passes do not prove that.

- Serves: `sensor-joint-mode-probe` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: host-capability-probe, hardware-trial-protocol.
- User-visible outcome: `ss-track hardware-probe` tests declared sensors together and reports a
  supported profile or an explicit reason.
- Scope boundary: Installed sensors, simultaneous modes, sustained loss, timestamp quality and bus
  contention. Accelerator graphs stay in spec section 12.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`.
- Execution path: Add a sensor source interface and recorded fixture sets.
- Acceptance gates: A pair that passes alone and fails together reports `UNSUPPORTED` as a pair.
  Discovery alone never yields `SUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), new page `current/sensor-mesh.md`.

### Camera bench characterization -- `camera-bench-characterization`

#### camera-trial-suite

Requested camera settings are not measured performance.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: hardware-trial-protocol, plugin-evaluator-core.
- User-visible outcome: A trial reports measured rate, drops, object extent, sharpness and clock
  alignment, each with uncertainty.
- Scope boundary: Capture, optics and vibration metrics from recorded evidence. Stereo range stays in
  spec section 12.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite against recorded traces with known answers.
- Acceptance gates: Hand-computed values match. Missing source frame IDs report
  `upstream_drop_unknown`, and requested rate never replaces measured rate.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Sensor adapters and front ends -- `sensor-adapter-frontends`

#### sensor-observation-contract

Every sensor needs one way to say what it saw, and what it could not see.

- Serves: `sensor-adapter-frontends` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-schema-contract, scenario-contract.
- User-visible outcome: Typed observations carry modality, evidence role, timing, geometry, coverage
  and provenance.
- Scope boundary: G2 record families for observations and epochs. Sensor drivers are later tasks.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Extend the schema without changing G0 `FrameResult` meaning, with golden fixtures.
- Acceptance gates: `no_detection`, `out_of_view`, `disabled_by_policy`, `missing`, `stale` and
  `invalid` stay distinct. An untyped confidence field is rejected.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### g2-scenario-observation-bundles

The G0 scenario excludes G2 boundaries, so component comparisons need an explicit input contract.

- Serves: `sensor-adapter-frontends` -- [Specification](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: sensor-observation-contract, run-bundle-store, corpus-split-grouping,
  annotation-review-tools.
- User-visible outcome: Four boundary-specific scenarios freeze raw/observation inputs, producers,
  clocks, calibration, opportunity labels and epoch schedules into hashed bundles.
- Scope boundary: Extend the existing scenario and bundle code, including mixed-modality raw attachments.
  No second cohort-key implementation or live capture driver.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/corpus/`, `tests/contract/`, `tests/corpus/`.
- Execution path: Reuse the bundle store and split rules. Extend annotation validation and review for
  modality-specific truth and opportunity masks. Add immutable observation staging and per-boundary
  read permissions with golden mixed-stream fixtures.
- Acceptance gates: Changing calibration, producer, input bytes or schedule changes the cohort. A forbidden
  raw read or cross-split stream fails conformance; unknown clocks never imply synchronization.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### camera-front-end

The mesh needs cameras as typed sources.

- Serves: `sensor-adapter-frontends` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: sensor-observation-contract, reference-sot-tracker.
- User-visible outcome: A recorded camera stream becomes typed observations with coverage and failure
  events.
- Scope boundary: Visible cameras, using the reference proposal. Stereo range is out of scope.
- Data and artifact paths: `src/ss_track/frontends/`, `tests/frontends/`.
- Execution path: Add the adapter with recorded inputs and calibration fixtures.
- Acceptance gates: Conformance fixtures pass, and a stale calibration is reported, never used
  silently.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### non-camera-front-end

The third source must follow the hardware evidence, not a guess.

- Serves: `sensor-adapter-frontends` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: sensor-observation-contract, select-mesh-sensors.
- User-visible outcome: The selected non-camera source emits typed observations with its evidence
  role.
- Scope boundary: The one selected source, which may arrive through an `ss-sens` adapter. Only its
  supported measurement is emitted, with no implied range or class.
- Data and artifact paths: `src/ss_track/frontends/`, `tests/frontends/`.
- Execution path: Add the adapter with raw-format provenance and recorded fixtures.
- Acceptance gates: Conformance fixtures pass, and a single sensor with no justified bearing or range
  emits neither.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### synchronized-sensor-capture

Recorded front ends alone cannot run the installed reference mesh or collect its evidence.

- Serves: `sensor-adapter-frontends` -- [Specification](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: g2-scenario-observation-bundles, camera-front-end, non-camera-front-end, joint-mode-probe.
- User-visible outcome: Sensors capture raw streams and feed typed front ends with clock evidence,
  bounded queues, explicit outages and shutdown handling.
- Scope boundary: Selected hardware drivers and live-to-bundle path. No field deployment, actuation or
  assumption that a receive timestamp is capture time.
- Data and artifact paths: `src/ss_track/capture/`, `tests/capture/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Extend `ss-track run` for live-capture scenarios through replaceable drivers.
  Use fake clocks for start, skew, overflow, disconnect and recovery fixtures. Live acceptance
  belongs to `record-mesh-encounters`.
- Acceptance gates: Every scheduled opportunity is accounted for after loss or recovery. Unsynchronized
  inputs cannot yield a calibrated latency; interruption preserves raw evidence and releases devices.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Fusion analysis -- `fusion-analysis`

#### event-time-replay

Fusion must only see what would have arrived by then.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: g2-scenario-observation-bundles, paced-frame-release, container-module-sandbox.
- User-visible outcome: Replay releases each event at its availability time under a declared clock
  and queue model.
- Scope boundary: Bounded reordering, epochs, availability cutoff and enforcement of each boundary
  through the existing container input channel. Live capture is a separate task.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add the replay path with late, reordered and skewed event fixtures.
- Acceptance gates: A causal test changes future events and holds past decisions unchanged. An event
  past its cutoff never enters a result.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fusion-calibration-suite

The fusion contract requires calibrated evidence, but raw detector scores cannot supply it.

- Serves: `fusion-analysis` -- [Specification](../design/spec.md#65-fusion-probability-and-resource-policy-evaluation)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay, plugin-evaluator-core.
- User-visible outcome: Per-sensor detection/false-alarm and existence/class calibration models are
  fitted on disjoint data and evaluated with proper scores, reliability and coverage.
- Scope boundary: Calibration populations and conservative dependence assumptions. Geometry or
  class quantities without independent labels remain unavailable; no learned fusion architecture.
- Data and artifact paths: `src/ss_track/fusion/`, `src/ss_track/suites/`, `tests/fusion/`, `tests/suites/`.
- Execution path: Implement the calibration contract and a simple deterministic baseline. Add hand-computed
  Brier/reliability fixtures and correlated-source, absent-outcome and split-leakage cases.
- Acceptance gates: Known outcomes reproduce expected scores; leakage is refused. Insufficient calibration
  evidence prevents a calibrated claim and reports coverage instead of fabricating a probability.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### late-fusion-baseline

The reference needs a transparent fusion rule that shows each source's contribution.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay, fusion-calibration-suite.
- User-visible outcome: Observations become fused, ambiguous or empty results with exact source
  lineage.
- Scope boundary: The deterministic late-fusion baseline. Learned and filter-based variants are out of
  scope.
- Data and artifact paths: `src/ss_track/fusion/`, `tests/fusion/`.
- Execution path: Add gated association and deduplication, with hand-audited fixtures.
- Acceptance gates: Correlated evidence is not counted twice, and `missing` or `out_of_view` adds no
  negative evidence. An ambiguous match stays `unassociated`.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fusion-suite

A fusion change must be judged on identical inputs.

- Serves: `fusion-analysis` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: late-fusion-baseline, plugin-evaluator-core.
- User-visible outcome: The `FIXED_OBSERVATION_FUSION` boundary reports association, false merges,
  deduplication and abstention.
- Scope boundary: Fixed hashed bundles, existence/class calibration where independently labelled, and
  stage timing. Unsupported quantities remain explicitly unscorable with coverage shown.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with byte-identical bundle fixtures.
- Acceptance gates: A changed front end forces a new cohort, and raw data access fails conformance.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Fixed-input tracker evaluation -- `fixed-input-tracker-evaluation`

#### tracker-epoch-suite

Tracker changes must be judged apart from what feeds them.

- Serves: `fixed-input-tracker-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay, sot-suite.
- User-visible outcome: The `FIXED_OBSERVATION_TRACKER` boundary reports identity, re-entry,
  prediction and deadline behavior.
- Scope boundary: Fixed observation streams and epoch schedules.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add crossing, miss, occlusion, re-entry and prediction-only fixtures.
- Acceptance gates: Every scheduled epoch is acknowledged, and a tracker that reads raw pixels fails
  this boundary.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Reference sensor mesh tracker -- `multi-source-reference-tracker`

#### mesh-reference-tracker

This is the project's reference implementation.

- Serves: `multi-source-reference-tracker` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: late-fusion-baseline, tracker-epoch-suite, reference-sot-tracker.
- User-visible outcome: Front ends, fusion and track maintenance run as one replaceable mesh tracker
  on frozen observations.
- Scope boundary: Image-plane state until a calibrated common state exists. Filters beyond the
  reference, and learned variants, are out of scope.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference-mesh/`.
- Execution path: Add track maintenance over fused and single-source observations, and work through
  the spec section 7.8 fixture list.
- Acceptance gates: Hand-audited lineage, identity and deadline fixtures pass. A prediction-only
  update is marked as such, and uninstalled sensors supply no evidence.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Sensor-set evaluation -- `g2-sensor-set-evaluation`

#### sensor-set-suite

The mesh should keep only the sensors that earn their place.

- Serves: `g2-sensor-set-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: late-fusion-baseline, camera-front-end, non-camera-front-end.
- User-visible outcome: The `SENSOR_SET_FRONT_END` boundary shows what each sensor adds under one
  frozen fusion rule.
- Scope boundary: Feasible single, paired, all-installed and leave-one-out sets.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with per-sensor and leave-one-out fixtures.
- Acceptance gates: The oracle union is shown only as a ceiling. A sensor that adds nothing is
  reported as such.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Installed-system evaluation -- `installed-system-evaluation`

#### installed-system-suite

The whole mesh must be judged as installed, not only by parts.

- Serves: `installed-system-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: energy-metric-suite, mesh-reference-tracker.
- User-visible outcome: The `FULL_INSTALLED_SYSTEM` boundary reports quality, availability, deadlines
  and full-system energy from one trial.
- Scope boundary: The installed mesh. No component attribution from this score alone.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with recorded traces, including a sensor outage.
- Acceptance gates: Quality and energy come from the same trial, and an outage stays in the
  denominator.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### g2-boundary-report

The local G0 report does not yet expose the four separate mesh evaluation boundaries.

- Serves: `installed-system-evaluation` -- [Specification](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: local-comparison-report, sensor-set-suite, fusion-suite, tracker-epoch-suite, installed-system-suite.
- User-visible outcome: One report shows front-end/sensor-set, fusion, tracking and full-system panels,
  comparable inputs, exposure, uncertainty, timing and energy evidence.
- Scope boundary: Extend the existing HTML/JSON report. No new dashboard service or component attribution
  from whole-system scores.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Render stored metrics from all four suites, with incompatible, missing-calibration,
  sensor-outage and unmeasured-energy fixtures.
- Acceptance gates: Each panel names its boundary and refuses incompatible comparisons. A missing quantity
  is explicit, and no component score is presented as whole-system quality.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### MOT and TrackEval -- `mot-trackeval`

#### trackeval-adapter

Genuine multi-object scenarios need a pinned evaluator on a supported Python.

- Serves: `mot-trackeval` -- [TrackEval adapter](../design/spec.md#8-trackeval-adapter-and-upgrade-policy)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: plugin-evaluator-core.
- User-visible outcome: A pinned TrackEval suite scores hand-audited MOT fixtures on Python 3.12.
- Scope boundary: Choose a patched fork, vendored copy or alternative evaluator, and replace the
  removed NumPy aliases. Energy stays outside it. A real MOT corpus is out of scope.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add byte-exact per-class export fixtures and the spec section 8 audit cases.
- Acceptance gates: Hand-audited perfect, miss, false positive, ID switch and ignore fixtures pass. A
  scenario the adapter cannot represent reports `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Paced thermal trial -- `paced-thermal-trial`

#### thermal-rig-controller (optional)

The rig needs software that holds chip temperature and proves it held.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: host-capability-probe.
- User-visible outcome: An off-host control loop holds a set-point, and a low-rate host log records
  temperature, frequency and throttle flags.
- Scope boundary: Software against a replaceable sensor and actuator interface. The physical rig is a
  human task.
- Data and artifact paths: `src/ss_track/thermal/`, `tests/thermal/`.
- Execution path: Add the loop with a simulated plant and recorded logs.
- Acceptance gates: Simulated runs settle inside the band under a load step. A temperature excursion
  during a scored segment marks the run invalid.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### temperature-run-orchestration (optional)

Heat must be the only difference between cool and hot runs.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: thermal-rig-controller, container-module-sandbox, hardware-trial-protocol.
- User-visible outcome: Blocks run identical frames at two set-points from clean state, plus an
  optional frequency-capped cool run.
- Scope boundary: Fresh container, dropped file cache, runner frame warm-up before timing, randomized
  order within blocks, a frequency cap, and setup energy reported apart.
- Data and artifact paths: `src/ss_track/thermal/`, `tests/thermal/`.
- Execution path: Add the block scheduler with a seeded order fixture and a marker for the timed
  interval.
- Acceptance gates: Fixtures prove module state does not carry between runs and order is balanced.
  Setup energy never enters ranked energy.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### thermal-effect-evaluation (optional)

A causal thermal claim needs a test separating frequency throttling from temperature.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: temperature-run-orchestration, development-decision-status.
- User-visible outcome: A suite reports the cool-to-hot change for any row, and all four bet
  conditions for a baseline.
- Scope boundary: Fixture evaluation. The live result is a human-lane task.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add hand-audited cool, hot and capped fixtures.
- Acceptance gates: An improvement, or a loss the capped arm does not reproduce, does not support the
  bet. A hot run with no throttling evidence reports `not_tested`.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Cohort ranking -- `benchmark-ranking`

#### rank-engine (optional)

Readers need one defensible rule for order.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: sot-suite, energy-metric-suite, hardware-trial-protocol, development-decision-status.
- User-visible outcome: A cohort yields ranks, tiers and unranked groups from saved scores and a
  versioned rules file.
- Scope boundary: Median-run choice, every-run floor, false-continuation cap, exposure minimum,
  anchored tiers, fault penalty, null row, independent-algorithm minimum and diagnostic column.
  Candidate IDs and versions are inputs; public eligibility policy is out of scope.
- Data and artifact paths: `src/ss_track/ranking/`, `tests/ranking/`, `scenarios/`.
- Execution path: Add table-driven fixtures from the
  [test plan](../design/perception-bench-test-plan.md). The rules file carries floors, margin, seed
  and resample count.
- Acceptance gates: Every ranking case in the test plan passes, including a penalty on the last tier,
  A-B-C overlap and an even valid-run count. Under the minimum, every row shows and no rank exists.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### benchmark-report-snapshot (optional)

A benchmark comparison needs an immutable, reproducible local report.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: rank-engine, visibility-gate, thermal-effect-evaluation.
- User-visible outcome: One command builds a local HTML/JSON snapshot from frozen comparison bundles.
- Scope boundary: Reuse the local report renderer for ranked and unranked cohorts, thermal diagnostics
  and limits. Hosting, public branding and submissions are outside the project.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<snapshot-id>/`.
- Execution path: Add the builder with a sample cohort. The snapshot date is an input, so the build
  stays reproducible.
- Acceptance gates: A rebuild is byte-identical and older snapshots stay readable. An empty cohort shows
  the protocol and missing evidence; restricted input is refused for a shareable export.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Device bench evaluation -- `device-bench-evaluation`

#### device-suite-and-adapter (optional)

Finished devices need a suite that works without an operator seed.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: CLEAR
- Milestone: M5
- Dependencies: installed-system-suite, event-schema-contract.
- User-visible outcome: A vendor adapter's events score detection delay, lock coverage and false
  alarms.
- Scope boundary: The suite, adapter contract and same-stimulus cohort key. Bench hardware is a human
  task.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `modules/`.
- Execution path: Add fixture events from two simulated devices.
- Acceptance gates: A device with no output path is `UNSUPPORTED`. Only same-stimulus, same-class,
  same-boundary cases are compared; incompatible or missing references are refused. Results
  are unranked and never pooled into a hardware-agnostic ranking.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/bench.md`.

### Documentation integrity -- `documentation-integrity`

#### plan-dependency-integrity (optional)

Structural checks pass even when a task depends on nothing real, so gating can drift unnoticed.

- Serves: `documentation-integrity` -- [Planning integrity](../design/spec.md#documentation-and-planning-integrity)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `make lint-spec-plan` rejects unknown dependencies and cycles across both lanes,
  including dependencies hidden in wrapped fields; plan status distinguishes priority from readiness.
- Scope boundary: Dependency parsing and graph checks only. Registry order remains capability priority;
  later groups can supply earlier groups through explicit task dependencies. Milestones form
  the DAG in the engine design, not a numeric barrier. Semantic review remains necessary.
- Data and artifact paths: `src/ss_track/quality/plan_model.py`,
  `src/ss_track/quality/plan_integrity.py`, `tests/quality/`.
- Execution path: Parse wrapped fields, then add the checks with failing fixtures.
- Acceptance gates: Fixtures reject unknown IDs, cycles and required tasks that depend on optional work,
  and accept valid cross-lane dependencies. A blocked earlier task is never reported as ready.
- Documentation target: [Governance](current/governance.md).

## Human-Assisted Tasks

Follow the [hardware support flow](../design/test-stands.md#selection-flow).
Acquisition and physical operation require the responsible person; agent tooling
prepares protocols, analyzes evidence and produces reviewable selection records.

### Corpus provenance -- `corpus-provenance`

#### select-development-workload

Software development needs authorized footage with a declared task and useful negative cases.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: none.
- User-visible outcome: One candidate workload has recorded terms, and the owner knows how close it
  is to the small-target stress case.
- Scope boundary: Authorized private or public development sources, benchmarking rights, retention and
  access restrictions. Public redistribution is a separate permission, never a G0a prerequisite.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/`, with source terms and hashes.
- Execution path: The owner checks source terms and selects positive/negative encounters; original
  controlled recordings are an alternative when no existing source fits.
- Acceptance gates: Every source has recorded rights and task suitability. With no authorized source,
  real-data claims remain unavailable while fixture implementation continues.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Annotation and selection -- `annotation-selection`

#### label-pilot-encounters

G0a needs only one positive and one negative encounter, so it should not wait for the whole corpus.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: select-development-workload, annotation-review-tools, frame-bundle-staging.
- User-visible outcome: Two encounters have frozen labels, selections and masks.
- Scope boundary: The pilot encounters, including motion events. The pass also measures labelling
  time per encounter.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Two reviewers label and settle disagreements under a named authority.
- Acceptance gates: Validation passes and the revision is frozen and hashed. Unresolved labels remain
  unknown; time spent labelling is recorded as planning evidence.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### label-development-corpus (optional)

Within-corpus comparisons need reviewed labels across independent encounters.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: label-pilot-encounters, corpus-split-grouping.
- User-visible outcome: At least 10 independent encounter groups have frozen labels.
- Scope boundary: Labelling and review. The sample-size pilot may add groups, and larger corpora may
  use a declared review sample plus all difficult cases.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Two reviewers label and settle disagreements under a named authority.
- Acceptance gates: Validation passes, groups are independent by the spec section 4.1 rule, and the
  revision is frozen. Unlabelable objects stay `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Controlled bench, timing and energy -- `controlled-bench-timing-energy`

#### acquire-bootstrap-bench

The measuring tools need hardware to run on, so the first meter and host are a declared bootstrap.

- Serves: `controlled-bench-timing-energy` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: HUMAN-GATED
- Milestone: M2
- Dependencies: none.
- User-visible outcome: One bootstrap host with fast storage and a logging meter are on the bench,
  with the reason for each choice recorded.
- Scope boundary: Stand A requirements A1 to A7 in the [test stands](../design/test-stands.md). An
  onboard PMIC reading does not qualify as the meter. The bootstrap host can still lose
  `select-reference-host`.
- Data and artifact paths: `scenarios/stands/`, `$DATA_DIR/selection/<selection-id>/`,
  `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: Before acquisition, freeze Stand A requirements and candidate budgets from the declared
  software workload: schedule, latency/loss tolerance, storage, interfaces, average/peak power,
  energy per task and thermal limit. Record measurement precision, meter rate, maximum gap,
  alignment method and acceptance tolerances, then compare available or borrowed instruments.
- Acceptance gates: The meter meets the declared rate, gap and alignment, has a calibration record,
  and passes a known-load check. If none fits, energy stays `NOT_MEASURABLE` and requirements return
  to the spec.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/hardware-selection.md`.

#### calibrate-bench-instruments

Bench evidence needs checked instruments and a measured harness cost.

- Serves: `controlled-bench-timing-energy` -- [Hardware metrology](../design/spec.md#79-hardware-metrology-and-measurement-algorithms)
- Agent status: BLOCKED BY HUMAN
- Milestone: M2
- Dependencies: acquire-bootstrap-bench, hardware-trial-protocol, paced-frame-release,
  module-image-recipes.
- User-visible outcome: A checked bench reports known-load results, pacing jitter, NVMe staging
  throughput and null-module energy.
- Scope boundary: Preflight, marker alignment and harness cost. Module results are out of scope.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person connects the instruments, and an agent runs the protocol with the null
  module in its container at the declared schedule.
- Acceptance gates: Known-load and marker checks pass, raw traces are retained, the selected-host hostile
  container fixture passes, and the harness sustains the declared schedule. A failed check blocks
  only affected claims and states its cause.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Hardware selection -- `hardware-selection`

#### select-reference-host

Benchmark and reference-tracker measurements need a host chosen from evidence.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: BLOCKED BY HUMAN
- Milestone: M2
- Dependencies: hardware-selection-report, calibrate-bench-instruments, reference-sot-tracker.
- User-visible outcome: A selection record names the reference host, with measured evidence for each
  candidate.
- Scope boundary: At least two available candidates against Stand A, including the bootstrap host.
  Optional thermal-rig compatibility is recorded separately from core benchmark suitability.
- Data and artifact paths: `$DATA_DIR/selection/<selection-id>/`, `scenarios/stands/`.
- Execution path: A person obtains approved candidates; an agent runs probe, null-module and
  reference-tracker trials on each under the same declared workload and limits.
- Acceptance gates: Each measured candidate has traceable evidence and rejection reasons. A single available
  candidate is a provisional choice, not a comparative selection. No qualifying host is valid;
  revise the requirement before claiming support.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

#### shortlist-mesh-sensors

A characterization stand needs candidate interfaces before any final sensor choice exists.

- Serves: `hardware-selection` -- [Specification](../design/spec.md#164-hardware-selection)
- Agent status: HUMAN-GATED
- Milestone: M3
- Dependencies: select-reference-host.
- User-visible outcome: A provisional inventory and versioned Stand B/C requirements are ready
  for trials.
- Scope boundary: Candidate availability, evidence roles, task coverage, geometry/clock tolerances, sustained
  modes and resource budgets. No candidate is yet selected as measured.
- Data and artifact paths: `scenarios/stands/`, `$DATA_DIR/selection/<selection-id>/`.
- Execution path: A person obtains approved candidates and documents raw formats, drivers, access conditions,
  independent reference needs and a minimum test for each required quantity.
- Acceptance gates: Every candidate has an executable measurement plan and a supported software need.
  Missing references or unaffordable candidates remain unmeasured with the limitation recorded.
- Documentation target: [Current implementation](current.md#areas), page `current/hardware-selection.md`.

#### select-mesh-sensors

The reference mesh needs a sensor set chosen on evidence.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: HUMAN-GATED
- Milestone: M3
- Dependencies: hardware-selection-report, joint-mode-probe, run-camera-characterization,
  shortlist-mesh-sensors.
- User-visible outcome: A selection record names two visible cameras, one non-camera source and the
  compute host for Stand C.
- Scope boundary: Candidates from the spec section 7.6 registry, each with a declared evidence role.
  Audio and active emitters need their spec section 11 rules first.
- Data and artifact paths: `$DATA_DIR/selection/<selection-id>/`, `scenarios/stands/`.
- Execution path: Measure candidate non-camera task observability and timing against the independent
  reference, then joint-mode and installed-boundary energy trials. Use generic raw logging before
  the production front end exists. Compare all required evidence through `ss-track hardware-select`.
- Acceptance gates: The chosen set satisfies frozen quality, coverage, timing and resource limits with
  uncertainty; each rejected or unmeasured option is recorded. A transport-only pass is insufficient.
  No qualifying set returns to the requirements without inventing a selection.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

### Camera bench characterization -- `camera-bench-characterization`

#### build-sensor-test-stand

Sensors can only be judged against a reference they do not control.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: HUMAN-GATED
- Milestone: M3
- Dependencies: shortlist-mesh-sensors, calibrate-bench-instruments.
- User-visible outcome: Stand B and Stand C exist, with a controlled target, an independent reference
  and a time marker.
- Scope boundary: Stand B and C requirements and the provisional candidate interfaces. Construction
  precedes final sensor selection; field sites are out of scope.
- Data and artifact paths: `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: A person builds the stands, and an agent checks them with marker fixtures.
- Acceptance gates: The reference trace is independent of every tested sensor. Any requirement the
  stand cannot meet is recorded, and its claim stays closed.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

#### run-camera-characterization

Fusion needs calibrated sensors with known limits.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: BLOCKED BY HUMAN
- Milestone: M3
- Dependencies: build-sensor-test-stand, camera-trial-suite.
- User-visible outcome: Each camera has measured capture, optics and timing results.
- Scope boundary: Shortlisted camera candidates on the stand before final selection. No field-range claim.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person operates the stand, and an agent runs the protocol.
- Acceptance gates: Raw evidence reproduces each estimate. A mode that fails stays `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Sensor adapters and front ends -- `sensor-adapter-frontends`

#### record-mesh-encounters

Fusion evaluation needs synchronized recordings with independent truth.

- Serves: `sensor-adapter-frontends` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: BLOCKED BY HUMAN
- Milestone: M3
- Dependencies: synchronized-sensor-capture, run-camera-characterization, annotation-review-tools.
- User-visible outcome: Authorized bench encounters exist with per-sensor opportunity labels and a
  disjoint calibration split.
- Scope boundary: Bench recordings. New public-space capture needs its spec section 11 approvals.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: A person records and reviews, and an agent imports the streams.
- Acceptance gates: Every stream shares its encounter and split; hashes, clock markers, calibration and
  opportunity masks are frozen. Independent reviewers settle cross-sensor identity and negative
  cases. Calibration and evaluation encounters are disjoint; unsupported truth stays unknown.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Installed-system evaluation -- `installed-system-evaluation`

#### run-mesh-trials

The project's second goal needs a measured result.

- Serves: `installed-system-evaluation` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: BLOCKED BY HUMAN
- Milestone: M3
- Dependencies: record-mesh-encounters, g2-boundary-report, build-sensor-test-stand.
- User-visible outcome: The reference mesh has results at all four boundaries, including what each
  sensor adds.
- Scope boundary: The selected sensor set on Stand C. No field-range or safety claim.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person operates the stand, and an agent runs each boundary's scenario.
- Acceptance gates: All four boundaries report through the local report, with faults and exposure shown.
  Recompute matches stored results. A sensor that adds nothing is documented; its selection record
  is revised from evidence and a reduced configuration starts a new cohort.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Paced thermal trial -- `paced-thermal-trial`

#### build-thermal-rig (optional)

The thermal claim needs physical control of chip temperature.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: select-reference-host, thermal-rig-controller.
- User-visible outcome: A rig holds the chip at declared set-points with its power outside the
  boundary, and the host's throttle onset is measured.
- Scope boundary: Stand A requirements A8 to A12 in the [test stands](../design/test-stands.md). The
  board's own fan header stays unused.
- Data and artifact paths: `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: A person builds the rig, and an agent tunes the controller and measures throttle
  onset from frequency evidence.
- Acceptance gates: The chip stays in band through a full segment under load at a hot set-point at or
  above onset. If it cannot, the owner chooses another thermal method and the spec changes first.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### run-thermal-experiment (optional)

The thermal mechanism needs a measured result, including a valid negative outcome.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: BLOCKED BY HUMAN
- Milestone: M4
- Dependencies: build-thermal-rig, calibrate-bench-instruments, thermal-effect-evaluation,
  load-calibrated-baseline, label-development-corpus.
- User-visible outcome: The owner knows whether heat costs tracking quality on the reference host.
- Scope boundary: Reference baselines, including the load-calibrated one. The result tests the
  mechanism and does not establish the behavior of other trackers.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person supervises the bench, and an agent runs cool, hot and capped runs under
  the declared protocol.
- Acceptance gates: All four conditions are evaluated and traces retained. No effect above noise or a
  non-reproducing capped arm is a valid negative result. No throttling reports `not_tested`
  without blocking the core benchmark or mesh.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Cohort ranking -- `benchmark-ranking`

#### run-sample-size-pilot (optional)

The comparison precision and tier margin should come from measurement.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: BLOCKED BY HUMAN
- Milestone: M4
- Dependencies: run-thermal-experiment.
- User-visible outcome: The owner sees floor-interval widths, energy rerun noise, and any extra
  labels needed.
- Scope boundary: Baseline-only interval width and rerun noise. Record a target precision and expansion
  limit before the pilot; baseline precision does not guarantee candidate precision.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Measure interval width and rerun noise on baselines over the labelled corpus. Any
  added groups return to `label-development-corpus`.
- Acceptance gates: Width and noise are recorded per baseline. If the precision target cannot be met,
  report insufficient evidence and revise the protocol before candidate comparisons.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### freeze-benchmark-protocol (optional)

Rules must be fixed before anyone's result is known.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: run-sample-size-pilot, tracker-compatibility-preflight.
- User-visible outcome: A versioned protocol pins workload, floors, margin, set-points, schedule, deadline,
  repetitions, bootstrap seed, resample count and maximum half-width before comparison runs.
- Scope boundary: Measurement parameters and a stated basis for each. Public eligibility, commercial
  terms, disputes and publication decisions are outside this task.
- Data and artifact paths: `scenarios/benchmark/rules-v1.yaml`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A human reviewer accepts the evidence-based protocol; an agent records values and hashes.
- Acceptance gates: Every rule has a value and a basis before comparison runs, and the rules hash
  enters the cohort key. A rule with no defensible value returns to the spec.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### run-benchmark-comparison (optional)

The comparison software needs end-to-end evidence on reference and candidate modules.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: BLOCKED BY HUMAN
- Milestone: M4
- Dependencies: freeze-benchmark-protocol, benchmark-report-snapshot, module-image-recipes.
- User-visible outcome: Candidates, baselines and the null module have full blocks under a
  frozen protocol.
- Scope boundary: Declared module versions only, under the frozen protocol. Public entry operations
  and publication are outside the task.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person supervises the bench; an agent runs each module's blocks with balanced order.
- Acceptance gates: Every run is kept with its status. Below the minimum, every row is shown and no
  rank is published.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### independent-rerun-check (optional)

Reproducibility needs a second person to follow the software instructions.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: run-benchmark-comparison.
- User-visible outcome: A second person recomputes every row and re-runs one available open module
  or reference baseline, even when no row qualifies for ranking.
- Scope boundary: Recompute and Re-run levels. Re-measure is not required.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`.
- Execution path: A second person follows only the documented commands and recorded image references.
- Acceptance gates: Scores match exactly at Recompute and within the declared tolerance at Re-run. A
  failure limits the reproducibility claim and its cause is recorded for repair.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Device bench evaluation -- `device-bench-evaluation`

#### build-device-bench-scene (optional)

Finished devices need one shared physical stimulus, as Stand D requires.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: HUMAN-GATED
- Milestone: M5
- Dependencies: device-suite-and-adapter.
- User-visible outcome: A controlled object and independent reference exercise each device equally.
- Scope boundary: One device class. Field trials and range claims are out of scope.
- Data and artifact paths: `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: A person builds the scene, and an agent validates it with fixtures.
- Acceptance gates: The reference trace is independent of the tested camera. If two devices cannot
  face the same stimulus, the class stays unranked.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### run-device-trials (optional)

The device suite needs measured conformance and validity evidence.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: BLOCKED BY HUMAN
- Milestone: M5
- Dependencies: build-device-bench-scene, device-suite-and-adapter, hardware-trial-protocol.
- User-visible outcome: Available devices have unranked measured cases under a predeclared protocol.
- Scope boundary: One device class with a complete boundary and two units or a single-unit label.
  Vendor enrollment, public naming, release policy and publication are outside the task.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Freeze stimulus, reference, windows and measurement limits before acquisition.
  A person operates the stand; an agent records events and scores the retained bundles.
- Acceptance gates: All attempts and limits remain visible. No available device is a valid negative result,
  and one device can yield an individual case without a comparative claim.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.
