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
by priority in each lane; dependency readiness must currently be checked from the task fields. Every
Agent group ends with its [group audit](../guide/planning-workflow.md#group-audits), whose
`(optional)` marker sets its order and does not make it skippable.

See the [planning workflow](../guide/planning-workflow.md), [engine milestone
map](../design/perception-bench-engine.md#milestone-map), [test
plan](../design/perception-bench-test-plan.md) and [test-stand
requirements](../design/test-stands.md). M1 is the small G0a pipeline, M2 supplies measurement and
host selection, and M3 delivers the reference mesh. Together they are [Phase
1](../design/spec.md#mission-and-phases): long-range detection, tracking and work with a human
operator. M7, autonomous recognition inside an energy budget, and M8, stand-off following in
simulation, and M9, the autonomous mission evaluation, are Phase 2 under [spec section
19](../design/spec.md#19-phase-2-autonomous-operation) and start from M3 evidence. M4, M5 and M6 are
optional extensions; none blocks M3, M7, M8 or M9. Fixture implementation proceeds without physical
hardware or private data.

## Agent Implementation Tasks

### Corpus provenance -- `corpus-provenance`

#### capture-encounter-counts

A build reports split counts but cannot expose how much of its evidence uses each camera-control
mode or observer platform, leaving ground footage indistinguishable from airborne evidence.

- Serves: `corpus-provenance` -- [Capture compatibility](../design/spec.md#capture-vocabulary-and-historical-source-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Build results report distinct encounter counts for every control-mode and
  observer-platform bin, including unknown and zero bins.
- Scope boundary: Count each encounter once in each applicable bin; mixed-stream encounters can
  enter several bins. Generated cases do not contribute. No score, joint histogram, inferred
  classification or claim that bin totals are additive.
- Data and artifact paths: `src/ss_track/corpus/versions/`, `tests/corpus/`, command-result contracts.
- Execution path: Reuse the verified source records used to build streams, retain capture data
  only as needed for the result, and avoid changing sealed corpus bytes for reporting alone.
  Document result field names and the multi-stream counting rule.
- Acceptance gates: Hand-counted fixtures cover every value, omission, repeated streams, mixed
  values in one encounter, multiple encounters and generated cases. A rerun has the same counts
  and manifest seal. Historical sources refuse with the migration remedy and count correctly
  after explicit amendment and successor build. Frozen contracts and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).

#### scale-reduction-case

No generated case makes a target smaller, so the benchmark cannot show where a module stops seeing
a target as it covers fewer pixels, which is the offline form of long-range detection.

- Serves: `corpus-provenance` -- [Deterministic cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A recipe declares a scale-reduction case, and staging writes frames
  resampled by its factor with a stored `scale` label transform.
- Scope boundary: Whole-frame reduction by a declared factor, with an area-average filter that is
  part of the transform revision, and a label transform that states the factor. No blur, noise,
  atmosphere or optics model, no enlargement and no range claim. A graded list of factors belongs
  to `robustness-severity-sweep`, and deriving the labels belongs to `generated-case-labels`.
- Data and artifact paths: `src/ss_track/corpus/cases/`, `tests/corpus/cases/`, `contracts/`,
  `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Add the transform in integer arithmetic, so one recipe gives identical bytes on
  x86-64 and arm64, record the output dimensions in the bundle, and extend `corpus preview` to
  show the reduced frame beside its parent.
- Acceptance gates: Hand-computed frames match for even and odd dimensions and for a factor that
  does not divide them. A rerun is byte-identical, a factor that changes no pixel is refused, and
  a stored case of another revision is refused. The case inherits its parent's split, encounter
  and group and adds to no count. `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).

#### frame-sequence-source-import (optional)

Public airborne-observer collections often ship as numbered images, and import accepts one video
stream of one file, so such a source cannot enter a corpus.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A recording declares an ordered image sequence as its source, and import,
  build, stage and verify treat it as they treat a video stream.
- Scope boundary: Lossless image files in a declared order, with one source identity over the
  ordered file hashes. A sequence stores no presentation time, so its timestamp quality is
  `missing` unless the declaration states a frame rate, which makes it `derived`. No lossy image
  format, no resampling and no reordering by guesswork.
- Data and artifact paths: `contracts/declaration/recording/`, `contracts/record/source-manifest/`,
  `src/ss_track/corpus/sources/`, `src/ss_track/corpus/decoding/`, `tests/corpus/`.
- Execution path: Evolve both contracts under the spec section 17.3 rules, read each image through
  the pinned decoder into the canonical pixel format, and add fixtures with a missing index, a
  changed image and mixed dimensions.
- Acceptance gates: One sequence imported twice gives one source identity and one bundle hash. A
  missing index, a changed image and mixed dimensions are each refused by name. Time-based scores
  of a sequence with no declared rate are unavailable with their cause, and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).

#### corpus-provenance-audit (optional)

Shared primitives, closed capture vocabularies and a geometry-changing case each touch records
that earlier work sealed, and a difference between them would move a hash.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: The corpus area keeps one account of sealing, capture facts and generated
  cases after its primitives moved.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/core/`, `src/ss_track/corpus/`, `tests/core/`,
  `tests/corpus/`, `contracts/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every caller of the shared primitives, how an older recording reads under the closed
  vocabularies, and what the scale-reduction case shares with the other frame-map cases.
- Acceptance gates: Historic records read to the same bytes and hashes, the import boundary holds,
  and generated cases stay byte-identical on rerun. Every finding is fixed, routed to a task or
  dropped with its reason, and `make quality` passes. Finding nothing is a valid result when the
  record states what was reviewed.
- Documentation target: [Corpus](current/corpus.md).

### Annotation and selection -- `annotation-selection`

#### scenario-pack-contract

Labels, scenarios and reports all name a scenario pack, but no format defines one. A class ID has
no pinned meaning, and the mission's targets exist only in prose.

- Serves: `annotation-selection` -- [Evidence lanes](../design/spec.md#2-evidence-lanes-and-claims)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts validate` accepts a scenario pack that states its
  classes, annotation vocabulary and limits, and a draft `aerial-small-objects` pack is the first.
- Scope boundary: A `declaration` contract for a pack: stable class IDs with scoring, distractor
  and ignore roles, a class hierarchy, minimum box, point and identifiable extents, extent bins,
  observer-platform strata, and named slots for the access policy, the non-disturbance envelope
  and the Phase 2 declarations of spec sections 19.3 and 19.7: target set, known non-targets,
  unknown set, declaration deadline and burden, declared target size and stand-off levels. The
  draft mission pack holds bird, bird of prey, drone, aircraft, insect and clutter classes. Its
  values are the owner's, through `approve-mission-scenario-pack`. No species list and no
  envelope value is invented here, and a Phase 2 slot stays empty until its human task fills it.
- Data and artifact paths: `contracts/declaration/scenario-pack/`, `scenarios/packs/`,
  `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add the contract and its registry entry, a loader that returns one pack hash,
  and positive and malformed fixtures.
- Acceptance gates: A duplicate class ID, a class with no role, an extent bin that overlaps
  another, and an envelope slot filled with no approval record are each refused with a reason.
  Changing any class, role, extent or bin changes the pack hash. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### annotation-contract

Labels need stable identity and a frozen mask before scores can mean anything.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: scenario-pack-contract.
- User-visible outcome: An operator validates visibility status, geometry, instance identity, motion
  events, operator seeds and masks against a versioned contract.
- Scope boundary: Label, seed and mask contracts, validation and frozen seed replay, in the stored
  orientation modules receive. Class names stay data in a scenario pack, so a label contract states
  the shape of a class ID and the pinned pack states its values. Labelling itself is human work.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add `ss-track annotate validate` with positive and malformed fixtures, including a
  source with display rotation.
- Acceptance gates: Identical seeds replay identically, and invalid labels are rejected with a reason.
  An unverifiable label stays unscorable and is never scored as zero. A label in any orientation other
  than the stored one is refused.
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

#### generated-case-labels

A generated case cannot be scored until its labels follow its pixels, and a wrong region must not
create a false negative.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: annotation-review-tools, scale-reduction-case.
- User-visible outcome: `ss-track annotate derive` gives each generated case a hashed label revision
  from its parent's frozen labels and stored label transform, including a `track_status` case.
- Scope boundary: Every stored label transform: region status, translation with clipping and
  `out_of_view`, frame maps, `scale`, `compression`, `timing` and `track_status`. `scale` multiplies
  geometry, uncertainty and plausible extent by its factor, turns a box under the pinned pack's
  minimum box extent into `point_only`, and a target under its minimum point extent into
  `unlocalizable`. `compression` and `timing` do not move geometry. `timing` records that
  presentation time is `derived`. `track_status` lists one role per case-window frame: `unknown`
  when that frame has no box, `region` for a painted rectangle, `shift` when the frame leaves the
  view, `reentry` when the box is back, and `unchanged` when the box stays. `unknown` stays
  `unknown` and is never `absent`. A `shift` frame is `out_of_view`. A `reentry` frame records
  re-entry. A `region` role names the painted rectangle: the occluder, the removed box, or the
  distractor copy. The target box on a distractor frame is not that rectangle and stays as the
  parent labeled it. The plate check applies to each box `moving_removal` replaces. A track case
  whose boxes or `label_revision` do not match that instance in the parent's frozen revision is
  refused. Derived labels are never edited by hand.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`,
  `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Apply each label-transform kind to hand-built parent labels, then check plates and
  regions against those labels. Apply each `track_status` role to the frame it names.
- Acceptance gates: Hand-computed labels match for every transform, including `scale`,
  `compression`, `timing` and `track_status`. A scaled box under the pack's minimum extent is
  `point_only`, never a box. A plate showing a target inside its region is refused, and a target
  the region does not fully cover stays `unknown`. A frame with no scorable box stays `unknown`.
  The same plate check applies to each box `moving_removal` replaces. A track case whose boxes or
  `label_revision` do not match that instance in the parent's frozen revision is refused. A parent
  with no frozen labels leaves its cases unscorable, never scored as zero.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### annotation-selection-audit (optional)

Label validation, review and generated labels each touch identity and the frozen mask, and a
difference between them would change what a score means.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: One set of rules decides what a label is, what can freeze and what stays
  unverifiable.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`,
  `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from the
  rules that validation, review tools and generated labels each apply, and from how a label joins a
  staged frame and a generated case.
- Acceptance gates: Seed replay stays identical, an unresolved case never freezes, and an
  unverifiable label never scores as zero. Every finding is fixed, routed to a task or dropped with
  its reason, and `make quality` passes. Finding nothing is a valid result when the record states
  what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Module contract and runner -- `module-contract-runner`

#### event-schema-contract

Python and later C++ modules need one versioned meaning for every event.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Modules and tools share a validated event schema with golden fixtures, and a
  breaking change fails CI.
- Scope boundary: The G0 and G1 record families. G2 fusion records are out of scope.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Define `.proto` files and protobuf-JSON JSON Lines validation. Add a Make target
  that regenerates bindings and a CI drift check, keep generated files out of the size and lint
  gates, and add the smallest justified dependency to `uv.lock`. Register each package under
  `contracts/event/`, pin `buf-bin` in the dev extra, and gate on `buf breaking` with the `WIRE_JSON`
  category against the frozen descriptor set, because G0 events travel as JSON. The registry,
  `make lint-contracts` and the contract `$id` pattern hold JSON Schema files only, so this task
  teaches them the `event` family.
- Acceptance gates: Golden fixtures cover absent and unknown fields, malformed payloads, coordinates,
  timestamps and power units. A malformed event is rejected with a reason. A renamed field, a reused
  field number and a changed `json_name` each fail the gate. `FrameRef` round-trips every
  field the staged bundle reports, including `transform` and `content_frame_index`, with those meanings.
- Documentation target: [Current implementation](current.md#areas), new page `current/runner.md`.

#### scenario-contract

A comparison must pin everything that can change its result.

- Serves: `module-contract-runner` -- [Run artifacts](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: event-schema-contract, annotation-contract.
- User-visible outcome: A scenario file pins scenario pack, corpus, frame set, labels, selection,
  replay mode, metric suite, seed and deadlines, and yields one cohort key.
- Scope boundary: The scenario schema, one cohort-key function, and one type that owns windows and
  runs. G2 boundaries are out of scope.
- Data and artifact paths: `src/ss_track/contract/`, `scenarios/`, `tests/contract/`.
- Execution path: Add the scenario as a `declaration` contract with example scenarios, and
  table-driven cohort-key fixtures.
- Acceptance gates: Changing any key field changes the cohort key. A scenario with a missing hash
  refuses to run, as does one whose corpus fails `corpus verify` or whose pinned frame-set hash differs
  from the `frame_set_sha256` that command reports. The pin is the only check that sees a frame set
  rewritten on disk. A source with empty `completeness_checks` is reported, never assumed complete.
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
- Execution path: Add bundle reader and writer with crash and retry fixtures. The run manifest and
  bundle are `record` contracts, and the manifest lists the contract set in force.
- Acceptance gates: A crash fixture leaves no complete-looking bundle, a retried ID stays
  idempotent, and each manifest records its re-run command. A bundle with no visibility value reads
  as restricted. Run scratch and any reproducible cache are registered
  [data clean](current/corpus.md#cleaning-the-data-root) kinds with restore paths and tests; sealed
  bundles never are.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### lockstep-runner

G0 needs a runner that accounts for every frame.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: run-bundle-store.
- User-visible outcome: `ss-track run` replays a scenario and reports exact frame accounting.
- Scope boundary: Lockstep execution and fault semantics. Paced timing is a later task.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add the runner with oracle, null, dropper, crash, schema and class-identity
  fixture modules. The null module becomes a reusable module, not only a test double.
- Acceptance gates: The G0a anti-gaming and null rows of the acceptance matrix pass. A crash is
  `MODULE_FAULT` with remaining scorable input missed, and a wrong source hash is `RUNNER_INVALID`, as
  are `FRAME_CORRUPTED`, `RECORD_TAMPERED`, `BUNDLE_NOT_STAGED`, `BUNDLE_CONFLICT`,
  `FRAME_SET_NOT_STAGED` and `FRAME_SET_MISMATCH`. `open_frame_bundle` reads any bundle directory, so
  the runner opens only bundles its pinned frame set names, and a module given another is
  `RUNNER_INVALID`. A frame a generated case removed is unscheduled and reported as undelivered, while
  a module drop stays a miss.
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
  a pacing jitter log, and frame hashing before release or reported as runner time. Real-time
  scheduling claims are out of scope.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add runner-controlled release with an injected clock, so tests stay deterministic,
  plus lookahead and slow-module fixtures.
- Acceptance gates: The lookahead fixture cannot read a future frame. The slow fixture records exact
  late and miss counts with no wall-clock dependence. Frame hashing never counts as module latency.
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
- Acceptance gates: The hostile fixture fails to open a socket, a label path or a future frame. If
  no runtime suits the host, the task records the blocker and does not weaken isolation. Sandbox
  scratch and runtime state are a registered [data clean](current/corpus.md#cleaning-the-data-root)
  kind with a test.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### module-image-recipes

Anyone re-running a row needs the exact module that was measured.

- Serves: `module-contract-runner` -- [Module reproducibility](../design/spec.md#163-module-reproducibility)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: container-module-sandbox, reference-sot-tracker.
- User-visible outcome: Reference and null modules have reproducible recipes, pinned image digests and
  license notices; candidate adapters follow the same contract.
- Scope boundary: Recipes, digests and license notices, including the FFmpeg, libx264 and libx265
  notices of any image that carries PyAV wheels. Tracker tuning and registry hosting are out of scope.
- Data and artifact paths: `modules/<name>/`.
- Execution path: Record recipes and digests in the manifest. Keep third-party dependencies outside the
  core lock; add a recipe when an adapter is introduced.
- Acceptance gates: The declared image digest can be obtained or rebuilt with any difference
  explained. Missing image access is reported as unavailable; no different image silently
  substitutes for it. Built images and build caches are a registered
  [data clean](current/corpus.md#cleaning-the-data-root) kind whose restore path rebuilds or fetches
  the declared digest.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### locked-split-guard (optional)

`locked` records membership only, so a development run can read held-out material with nothing
noticing.

- Serves: `module-contract-runner` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: lockstep-runner.
- User-visible outcome: A development scenario that names a locked stream is refused, and an
  approved locked evaluation leaves an append-only access record.
- Scope boundary: Runner enforcement and audit records. This is no access control against a person
  with disk access, and it creates no locked test.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Check split membership when a run starts, and add refused, approved and re-scored
  fixtures. Review now withholds every locked window as `locked_without_policy`
  ([review and freeze](current/corpus/review-and-freeze.md#what-review-offers)); once a custodian
  policy exists, let a review that names the policy's hash decide locked windows, and leave the same
  access record.
- Acceptance gates: A locked stream in a development scenario is `RUNNER_INVALID`. Each approved
  read and re-score leaves one record, and output never calls a stream held-out without a declared
  custodian policy. A corpus version with no declared predecessor is reported as having no lineage,
  and one whose `corpus verify` names a predecessor under `shared_frames.not_compared` is reported
  with each one named, so nothing calls its locked material unseen.
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

#### module-contract-runner-audit (optional)

Contracts, the store, the runner and the sandbox were written against each other in stages, so a
frame or a boundary can be accounted for in one place and assumed in another.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every frame has one account from release to stored result, and no path leads
  from a module to labels, the network or restricted data.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`, `scenarios/`,
  `$DATA_DIR/run/<run-id>/`, `src/ss_track/runner/`, `tests/runner/`, `modules/null/`,
  `modules/<name>/`, `modules/<tracker>/`, `$DATA_DIR/preflight/<run-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  frame accounting across the lockstep and paced paths, how the run store and `corpus` share
  sealed-record code, and every route out of the sandbox.
- Acceptance gates: Oracle, null, dropper, crash, schema and class-identity fixtures keep their
  exact accounting, a partial bundle never reads as complete, and a test covers each sandbox
  boundary. Every finding is fixed, routed to a task or dropped with its reason, and `make quality`
  passes. Finding nothing is a valid result when the record states what was reviewed.
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
  counts as a miss in `sot-paced-v1`. An episode with no scorable frame is `NOT_SCOREABLE`. A stream
  with `missing` timestamp quality reports time-based scores as unavailable, with its cause, on a real
  AVI fixture.
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

#### extent-envelope-view

Long-range detection is the first mission priority, and one aggregate score hides the target size
at which a module stops working.

- Serves: `motion-sot-evaluation` -- [Extent envelope](../design/spec.md#67-small-target-extent-envelope)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: sot-suite, motion-suite, scenario-pack-contract.
- User-visible outcome: Each tracking and motion result carries an extent envelope by bin and a
  smallest supported extent, with real encounters and scale-reduction cases as separate curves.
- Scope boundary: Bins from the pinned scenario pack and floors from the scenario. Pixels always,
  angular extent only with a measured field of view, distance only with a measured range. No
  conversion from an assumed object size and no new primary metric.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the view to both suites over their per-frame and per-event results, with
  hand-built encounters at known extents and point-only labels binned by plausible extent.
- Acceptance gates: Hand-computed bin counts, intervals, statuses and the supported extent match.
  A bin under the encounter minimum is `insufficient_data`, a generated case never fills a real
  bin, and a module that proposes everywhere gains no smaller supported extent. No supported bin
  is reported as a result, never as an error.
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

#### motion-sot-evaluation-audit (optional)

Each suite scores saved evidence through a shared core, and a denominator or time weight defined
twice would make two suites disagree on one run.

- Serves: `motion-sot-evaluation` -- [Metric-suite validity](../design/spec.md#6-metric-suite-validity-and-primary-g0-metrics)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every suite scores through one core, with each denominator and time weight
  defined once.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/evaluator/`, `tests/evaluator/`, `src/ss_track/suites/`,
  `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from the
  denominators, time weights and exclusions each suite applies, and from what
  `development-decision-status` reads from them.
- Acceptance gates: Hand-computed fixture metrics stay exact, and each suite's exclusions appear in
  its output. Every finding is fixed, routed to a task or dropped with its reason, and `make
  quality` passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Reference tracker -- `reference-tracker`

#### reference-sot-tracker

The benchmark needs a simple, inspectable baseline.

- Serves: `reference-tracker` -- [Reference tracker](../design/spec.md#78-tdd-reference-tracker-and-stagewise-development)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: lockstep-runner, sot-suite.
- User-visible outcome: A deterministic seeded tracker and its motion proposal front end run through
  the contract in two declared versions, without and with global-motion compensation of the
  frame, so G0a has a real comparison that matters for a moving observer.
- Scope boundary: The single-camera path. The staged multi-source tracker belongs to M3.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference/`.
- Execution path: Add a bounded motion proposal, a constant-velocity Kalman model, geometry gates and
  tentative, confirmed, lost and reacquired states.
- Acceptance gates: The G0a reference tracker row of the acceptance matrix passes on rerun with one
  seed. A predicted stale box cannot pass as a measured detection. On a fixture with a translating
  camera and a static scene, the uncompensated version proposes background and the compensated
  version does not, and neither result is assumed to carry over to real footage.
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

#### reference-tracker-audit (optional)

A baseline only helps if it stays simple and deterministic, and a load setting added later can bend
it.

- Serves: `reference-tracker` -- [Reference tracker](../design/spec.md#78-tdd-reference-tracker-and-stagewise-development)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: The reference tracker stays small enough to inspect, with one deterministic
  path under every setting.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  the load setting touches, every source of randomness or wall-clock time, and what can be shared
  with `mesh-reference-tracker`.
- Acceptance gates: Seeded runs stay identical, the load setting preserves lockstep outputs, and
  continuity, lost and re-entry, identity and deadline fixtures pass. Every finding is fixed, routed
  to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result
  when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page
  `current/reference-tracker.md`.

### Comparison report -- `comparison-report`

#### local-comparison-report

Maintainers need to inspect two versions and see every exclusion.

- Serves: `comparison-report` -- [Comparison dashboard](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: development-decision-status, extent-envelope-view.
- User-visible outcome: `ss-track compare` writes a local HTML and JSON report, or refuses with a
  reason.
- Scope boundary: Local report with visibility retained. Shareable export uses `visibility-gate`.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Build the report from saved metrics with compatible and incompatible fixtures,
  including frame-linked failure references.
- Acceptance gates: An incompatible cohort is refused with its reason, and the report never edits or
  recomputes source metrics. Generated cases appear in their own slice by transform, never in a
  field aggregate or an encounter count, and undelivered frames and unverified completeness are
  shown. Each run's extent envelope appears by bin with its exposure, real and generated curves
  apart, and observer platform and camera control appear beside every score.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### g0a-pipeline-run

The whole offline path must work on real labelled video.

- Serves: `comparison-report` -- [Delivery gates](../design/spec.md#3-scope-and-delivery-gates)
- Agent status: RUN NEEDED
- Milestone: M1
- Dependencies: local-comparison-report, reference-sot-tracker, motion-suite,
  label-pilot-encounters, generated-case-labels.
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

#### robustness-severity-sweep (optional)

A pass or fail on one generated case does not show where a module starts to degrade.

- Serves: `comparison-report` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: local-comparison-report, generated-case-labels.
- User-visible outcome: A recipe declares graded levels of one parameter, including the factor of a
  scale-reduction case, and the local report shows each module's quality against that severity.
- Scope boundary: One parameter, one encounter set and one saved metric per curve. No composite
  score or field claim.
- Data and artifact paths: `src/ss_track/corpus/`, `src/ss_track/report/`, `tests/corpus/`,
  `tests/report/`.
- Execution path: Expand a `levels` list into ordinary cases at build, then plot saved metrics
  without recomputing them.
- Acceptance gates: A sweep expands to the same bundles as hand-declared cases. A hand-built curve
  matches its source metrics exactly, and a run that faulted at one level stays visible at that
  level.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### comparison-report-audit (optional)

A report joins runs, cohorts, exclusions and visibility, and the join is where an exclusion
disappears or restricted data reaches public output.

- Serves: `comparison-report` -- [Comparison dashboard](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: A report shows every exclusion and every limit it rests on, and nothing
  restricted can reach public output by any route.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<run-id>/`,
  `$DATA_DIR/run/<run-id>/`, `src/ss_track/contract/`, `tests/contract/`, `src/ss_track/corpus/`,
  `tests/corpus/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  value a report shows and the sealed record it comes from, every route to public output, and the
  cohort refusal reasons.
- Acceptance gates: An incompatible cohort is refused with its reason, each displayed value traces
  to a sealed record, and a restricted fixture reaches no public output. Every finding is fixed,
  routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid
  result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Operator session evaluation -- `operator-session-evaluation`

#### operator-session-contract

A module can report a lost target, but it cannot ask the operator for anything, and the runner can
hand it only the first selection.

- Serves: `operator-session-evaluation` -- [Operator session](../design/spec.md#169-operator-session-evaluation)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: lockstep-runner.
- User-visible outcome: A scenario declares an operator script, a module emits prompts, and the
  runner answers them with scripted actions that every module of a comparison is offered alike.
- Scope boundary: `OperatorPrompt` and `OperatorAction` as an additive event contract version, the
  operator script as a `declaration` contract that the scenario pins in its cohort key, and causal
  release of actions in lockstep replay. Paced release of an action follows `paced-frame-release`.
  No console, no human timing model and no change to `FrameResult`.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/runner/`, `tests/contract/`,
  `tests/runner/`, `scenarios/`.
- Execution path: Add the events and the script reader. The runner derives each action from frozen
  labels, the declared delay and the seeded seed-quality perturbation. An action names the frame
  its geometry belongs to, which is the frame of its cause, and is released one response delay
  later. Add fixture modules that prompt correctly, never prompt and prompt constantly.
- Acceptance gates: No action is released before the prompt or sustained failure that caused it,
  and a causal test that changes later frames leaves earlier actions unchanged. Every action
  carries the frame its geometry belongs to, and a fixture shows that it reaches the module one
  response delay after that frame. Two runs of one module with one script and seed receive
  identical actions. A scenario with no script runs as before, a changed script changes the
  cohort key, and a prompt makes no frame unscorable.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### operator-workload-suite

Coverage alone cannot tell a module that tracks on its own from one an operator must rescue every
few seconds, or from one that fails without saying so.

- Serves: `operator-session-evaluation` -- [Operator session](../design/spec.md#169-operator-session-evaluation)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: operator-session-contract, sot-suite, motion-suite, local-comparison-report.
- User-visible outcome: A report shows assisted and unassisted lock coverage, interventions per
  tracked minute, hand-back delay, silent failures and unwarranted prompts for each module.
- Scope boundary: `operator-v1-dev` over saved bundles. The script is a deterministic stand-in and
  gives no human-factors result. Alert burden reuses the motion suite's matching unchanged.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `src/ss_track/report/`,
  `tests/report/`.
- Execution path: Add the suite with hand-audited recovered-loss, wrong-target, silent-failure and
  unwarranted-request fixtures, and a session timeline in the local report.
- Acceptance gates: Every count and denominator matches its hand-audited fixture. A reselection
  counts as a loss at its time in assisted and unassisted coverage. A module that never prompts is
  scored with its silent failures shown, and assistance that raises no coverage is a reported
  result.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### operator-session-evaluation-audit (optional)

The script, the runner and the suite each decide when an operator would have acted, and two
answers to that question would make one session score two ways.

- Serves: `operator-session-evaluation` -- [Operator session](../design/spec.md#169-operator-session-evaluation)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: One rule decides when a scripted operator acts, and every intervention in
  a report traces to the event that caused it.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/runner/`,
  `src/ss_track/suites/`, `src/ss_track/report/`, `tests/contract/`, `tests/runner/`,
  `tests/suites/`, `tests/report/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  the definition of a sustained failure in the tracking suite, the runner and this suite, and from
  every path by which an action could reach a module early.
- Acceptance gates: Recovered-loss, wrong-target, silent-failure and unwarranted-request fixtures
  keep their counts, and no action precedes its cause on the lockstep or paced path. Every finding
  is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding
  nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Self-supervised video corpus -- `self-supervised-corpus`

#### corpus-selection-evaluation

A larger selected pool may conceal missed small birds or exclude hard negatives.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: none.
- User-visible outcome: A report compares model-assisted selection with a random or uniform
  baseline and exposes missed cases and resource cost at a matched review budget.
- Scope boundary: Independently reviewed audit samples and stratified uncertainty; no field accuracy,
  generalization or verified species claim from model proposals alone.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Define a reproducible evaluation protocol before running, score reviewed random
  samples including unselected material, and report diversity, negatives, recall, cost and exclusions.
  Read each window's reviewed observation from its `declaration/corpus-review` or freeze record
  ([review and freeze](current/corpus/review-and-freeze.md#decisions)); `unknown` and unreviewed
  windows count as unknown, never as absent.
  Compare `ssl-diverse` with the `uniform` run of the same pool and audit seed
  ([selection](current/corpus/discovery-runs.md#selection)) under the `selection_pass` review
  protocol ([selection pass](current/corpus/review-and-freeze.md#selection-pass)), keep each
  pass's findings outside the audit and its disagreements beside the estimate, and also list a
  window both runs selected whose two passes disagree when no review observed it, which the
  comparison does not yet report. Report misses by kind, including a
  target present for a whole stream, which background deviation compares against itself, and
  confusers that motion ranks high. Record whether the audit review was independent and blinded.
  A review or freeze states that with `independence` and `blinding` when the reviewer declared it,
  and leaves both unrecorded when it does not. A stated value is a declaration, not a verification.
  Capture measured compute cost alongside the comparison; discovery runs do not record it. The
  comparison already reports each collection's estimates, shared-stratum covariance and the weighted
  combined population
  ([evaluating selection](current/corpus/discovery-runs.md#evaluating-selection)). Keep that report.
  Do not reimplement it, and do not treat it as field prevalence. The
  [reviewed pilot](current/corpus.md#reviewed-pilot) is the input: explain its lower `ssl-diverse`
  recall with each method's stream and group coverage, since that selection covered 19 streams
  against 34, and report whether the misses are coverage or ranking.
- Acceptance gates: Hand-calculated fixtures verify denominators, sampling weights, uncertainty and
  unavailable strata; empty or insufficient evidence produces an explicit inconclusive result.
  A fixture lists two passes that disagree on a window no review observed, without changing the
  estimate. Negative gains remain valid and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).

#### corpus-scale-pilot

A large corpus needs evidence that selection can run within the owner's available resources.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Research: yes
- Dependencies: corpus-selection-evaluation.
- User-visible outcome: An authorized pilot produces a measured, reproducible corpus or explains why
  available video, quality, cost or resources do not support it.
- Scope boundary: Only approved sources, processing and storage budgets; no acquisition beyond the
  agreed list or unattended spend.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Use the approved corpus-size and diversity targets, candidate sampling, human
  review and baseline protocol; measure ingest, storage, CPU or GPU compute and completeness; retain
  run pins. The embedding worker records float32 rows only and refuses mixed precision; a GPU run
  either measures float32 or adds a float16 or autocast mode as a `record/discovery-run` minor
  with its own reproducibility check. A tile grid multiplies embedding cost by its tile count, so
  choose the grid from measured cost and small-target scale. `discover verify` compares recomputed
  scores and the `ssl-diverse` similarity exactly; run it on a second host or architecture, and if a
  near-tie flips there, quantize the similarity under a new method revision. The link review's
  `background-cosine` thresholds were measured on one real recording and synthetic scenes
  ([measured thresholds](current/corpus/leakage-review.md#measured-thresholds)): measure them on
  reviewed related and unrelated pairs of the pilot's footage, including sessions of one site in
  other light and the tile grid the pilot chooses, and revise the table under a new method revision
  when a related pair falls below it; repeat the review on the second host and quantize its
  similarity too if a flag flips. The fingerprint compares every pair of windows in Python, so
  measure its time at the pilot's stream count with the build's report and the review. Freezing
  verifies the discovery run against its pool version's staged frames, so measure the storage of
  keeping the pool's frames until its frozen versions are frozen. The pilot's GPU embedding worker
  averaged 53-56% GPU utilization, with half the 2-second samples below 50%, while the worker used
  several CPU cores; measure where worker time goes at scale and reduce the CPU-side preprocessing
  cost, without changing rows, if it dominates. Measure how the BT.601 fallback changes scores and
  selection on the pilot's untagged sources, and the memory `discover blind` needs for the audit at
  scale; the pilot's 104-window packet peaked at 6.3 GB. Include each source that
  `authorize-airborne-observer-sources` has approved, and report selection, review and counts
  by observer platform, so that a pool with no airborne-observer encounter says so.
- Acceptance gates: Corpus verification, rights and grouping checks pass; the report states
  selection recall, uncertainty, negative coverage and matched-budget baseline results, including
  missing evidence. Insufficient resources or a negative selection result is a valid negative;
  `make ci` passes. Every disposable kind the pilot leaves, such as superseded frames, downloads and
  host-specific environments, is removable through
  [data clean](current/corpus.md#cleaning-the-data-root) with a stated restore path.
- Documentation target: [Corpus](current/corpus.md).

#### corpus-wetland-evidence (optional)

WetlandBirds annotations and software can inform future cases, but their outputs need provenance.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: An operator can inspect and map WetlandBirds annotations and, when suitable,
  run its software as separately identified evidence for future corpus cases.
- Scope boundary: Fixture-based mapping and an isolated, pinned optional integration; no promotion
  of model outputs or upstream annotations to independently reviewed truth and no locked training.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `contracts/`,
  `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Inspect the upstream software and annotation semantics, pin its revision, audit
  code, dependencies and weight licenses, then map annotations to verified video and frame identities.
  If running its software is justified and authorized, isolate its environment and retain model,
  preprocessing and weight provenance; otherwise report why it is unavailable. Contract any new
  interchangeable evidence and preserve original splits without adopting them as local authority.
- Acceptance gates: Offline fixtures cover frame mapping, unmatched and ambiguous identities,
  provenance, isolation and refusal of missing terms; upstream labels cannot affect blinded audit or
  become frozen truth. An evidence-backed decision not to execute the software is valid; `make ci`
  passes. Its isolated environment, weights and intermediate outputs are a registered
  [data clean](current/corpus.md#cleaning-the-data-root) kind with a restore path and a test.
- Documentation target: [Corpus](current/corpus.md).

#### corpus-motion-memory-pressure (optional)

Adaptive motion scoring checks memory before scheduling streams, but already-running workers can
continue after unrelated processes consume the reserved headroom. A long high-resolution stream can
therefore exhaust memory before the next scheduling check; the current policy is an estimate, not a
hard memory guarantee.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: The operator can bound or stop motion work when memory pressure rises during
  a stream, with a structured refusal rather than silently accepting partial scores.
- Scope boundary: Local worker resource enforcement and cancellation; preserve integer scores,
  sealed results and a serial fallback on hosts without enforceable limits.
- Data and artifact paths: `src/ss_track/core/`, `src/ss_track/corpus/selection/`,
  `tests/corpus/selection/`, and `$DATA_DIR/self-supervised-corpus/` for measured evidence.
- Execution path: Evaluate portable process supervision or operating-system memory limits; detect
  pressure while a stream is active, stop safely when needed, and document platform limitations.
- Acceptance gates: Deterministic tests simulate falling headroom and worker termination, prove no
  partial result is accepted or child left running, and retain serial/parallel score equality;
  `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).

#### corpus-discovery-progress (optional)

A real discovery run can occupy the GPU for hours without reporting its phase or progress. During
`pilot-diverse-v2-20261109`, only external GPU sampling showed activity, so an operator could not
tell which extractor or stream was running or estimate remaining work.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: An operator can see the current discovery phase and completed versus total
  work while a long run is active, with unknown quantities clearly marked.
- Scope boundary: Local, bounded progress reporting; no change to scores, selection, deterministic
  artifacts, the single command-result record, or disclosure of blinded review decisions.
- Data and artifact paths: `src/ss_track/corpus/discovery/`, `src/ss_track/corpus/siblings/`,
  `tests/corpus/`, and the operator's configured output; no new external service.
- Execution path: Instrument extraction and scoring at useful phase and stream or batch boundaries;
  keep progress separate from the command result and ensure disabled or unavailable progress does
  not change the run or block it.
- Acceptance gates: Network-free tests exercise progress, disabled output, failures and unchanged
  sealed records; the existing command-result contract and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).

#### discovery-package-split (optional)

The corpus package holds two capabilities in one tree. Source import takes helpers from review
export, so a change to review can break import, and the discover command module carries more than
argument parsing.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: Corpus provenance and corpus discovery are separate area packages, with
  imports in one direction, from discovery to provenance.
- Scope boundary: A move of the inventory, acquisition, pool, sibling, selection, discovery,
  review, link and evaluation modules to their own area package, with their tests. The write-once
  and declaration-byte helpers that source import takes from review export move to the side that
  owns them. No command name, record, contract, hash or refusal code changes.
- Data and artifact paths: `src/ss_track/corpus/`, `src/ss_track/discover/`,
  `src/ss_track/commands/`, `tests/corpus/`, `tests/discover/`.
- Execution path: Move packages with their tests, split the discover command module by subcommand
  family so that handlers hold parsing only, and add an import-boundary test. Split the
  interactive link review and audit review modules, which are well over the size guideline, where
  a functional seam exists.
- Acceptance gates: No module of the provenance package imports the discovery package. Every
  sealed fixture reads to the same bytes, `discover verify` passes on a fixture run recorded
  before the move, and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).

#### self-supervised-corpus-audit (optional)

The full corpus formation path needs one review across sibling integrations and reviewer decisions.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: The complete workflow preserves source rights, frame identity, sampling
  evidence, review authority and split isolation across its seams.
- Scope boundary: Group audit over this group's paths, contracts, external version pins, tests and
  limitations; no new acquisition or claimed field performance.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `contracts/`, `$DATA_DIR/self-supervised-corpus/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits), including
  stopped runs, unavailable models, unselected negatives and duplicate or revoked source terms.
- Acceptance gates: Each finding is fixed, routed or dropped with its reason, verified evidence is
  reproducible and `make quality` passes; finding nothing is valid when scope is recorded.
- Documentation target: [Corpus](current/corpus.md).

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
- Execution path: Add the host profile as a `record` contract. Read system facts behind a replaceable
  source that `board-telemetry-sources` can share, with recorded fixture hosts,
  including Raspberry Pi `vcgencmd` evidence.
- Acceptance gates: Recorded hosts produce expected profiles. An unavailable feature yields
  `UNSUPPORTED` or `MEASURE_REQUIRED`.
- Documentation target: [Current implementation](current.md#areas), new page `current/bench.md`.

#### hardware-probe-adaptive-launch-audit (optional)

A probe that fills a value it could not read makes every later trial start from a guess.

- Serves: `hardware-probe-adaptive-launch` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Recorded and live probes share one path, and a fact a host could not show
  stays unknown.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`, `$DATA_DIR/probe/<host-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  field a probe reports, what happens when its source is absent, and what the joint-mode probe will
  reuse.
- Acceptance gates: Recorded and live fixtures agree, an unreadable fact stays unknown, and
  `UNSUPPORTED` and `MEASURE_REQUIRED` stay distinct. Every finding is fixed, routed to a task or
  dropped with its reason, and `make quality` passes. Finding nothing is a valid result when the
  record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Controlled bench, timing and energy -- `controlled-bench-timing-energy`

#### power-trace-ingest

Energy claims need raw traces and honest integration.

- Serves: `controlled-bench-timing-energy` -- [Electrical power](../design/spec.md#794-electrical-power-thermal-state-and-motion)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: run-bundle-store.
- User-visible outcome: A meter trace becomes joules over an exact marked interval, with uncertainty.
- Scope boundary: File-based trace ingest through a declared `power-trace` contract, trapezoid
  integration, gaps, saturation and marker-based
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
- Execution path: Add the protocol and `HardwareTrial` as contracts, and fixtures that replay recorded
  traces.
- Acceptance gates: Fixtures reproduce timing, resource and energy estimates with explicit units and
  uncertainty. Missing instruments invalidate only affected claims. Every invalid attempt remains
  in the bundle; ranking-specific repetition rules never gate a basic bench measurement.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### controlled-bench-timing-energy-audit (optional)

Trace ingest, the energy suite and the trial protocol must agree on units, clocks and validity, or
an energy number outlives the evidence behind it.

- Serves: `controlled-bench-timing-energy` -- [Electrical power](../design/spec.md#794-electrical-power-thermal-state-and-motion)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every energy and timing estimate traces to hashed raw evidence through one
  integration path, with its uncertainty and validity.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/energy/`, `tests/energy/`, `src/ss_track/suites/`,
  `tests/suites/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  units and clock handling across ingest and suite, how validity travels from trial to result, and
  any energy calculation outside the suite.
- Acceptance gates: Fixture estimates recompute exactly from retained raw traces, and an invalid
  trial cannot yield a valid estimate. Every finding is fixed, routed to a task or dropped with its
  reason, and `make quality` passes. Finding nothing is a valid result when the record states what
  was reviewed.
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

#### hardware-selection-audit (optional)

A selection record is read long after it is made, so anything it leaves unstated becomes an
unsupported claim.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: A selection states what was measured, rejected and left unmeasured, from
  retained evidence alone.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/selection/`, `tests/selection/`, `scenarios/stands/`,
  `$DATA_DIR/selection/<selection-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from how
  a record reaches its choice, and from every input that is not a retained measurement.
- Acceptance gates: Only measured configurations are chosen, and a selection with none qualifying
  says so. Every finding is fixed, routed to a task or dropped with its reason, and `make quality`
  passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page
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

#### sensor-joint-mode-probe-audit (optional)

A joint probe repeats much of the host probe, and separate passes can still be mistaken for joint
evidence.

- Serves: `sensor-joint-mode-probe` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Joint-mode evidence shares the probe's path and cannot be mistaken for
  separate passes.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from code
  shared with `host-capability-probe`, and from how sustained load is shown in the result.
- Acceptance gates: Every installed sensor yields a supported profile or an explicit fallback, and a
  separate pass never reports as joint. Every finding is fixed, routed to a task or dropped with its
  reason, and `make quality` passes. Finding nothing is a valid result when the record states what
  was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

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

#### camera-bench-characterization-audit (optional)

A camera setting that was requested can read as one that was measured unless the suite keeps them
apart.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Requested settings and measured performance never share a field.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  reported value and its raw evidence, and from what the suite repeats from the shared evaluator.
- Acceptance gates: Raw evidence is retained for every estimate, each estimate carries its
  uncertainty and validity, and no requested value reports as measured. Every finding is fixed,
  routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid
  result when the record states what was reviewed.
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
- Execution path: Extend the schema as an additive event contract version, without changing G0
  `FrameResult` meaning, with golden fixtures.
- Acceptance gates: `no_detection`, `out_of_view`, `disabled_by_policy`, `missing`, `stale` and
  `invalid` stay distinct. An untyped confidence field is rejected.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### g2-scenario-observation-bundles

The G0 scenario excludes G2 boundaries, so component comparisons need an explicit input contract.

- Serves: `sensor-adapter-frontends` -- [Specification](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: sensor-observation-contract, run-bundle-store, annotation-review-tools.
- User-visible outcome: Four boundary-specific scenarios freeze raw/observation inputs, producers,
  clocks, calibration, opportunity labels and epoch schedules into hashed bundles.
- Scope boundary: Extend the existing scenario and bundle code, including mixed-modality raw attachments,
  stream clock, calibration and raw-format fields, and permitted modalities in scenario rights. No
  second cohort-key implementation or live capture driver.
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
  silently. Frames convert like staged bundles, so a left-sited H.264 or HEVC source matches its bundle
  within a measured tolerance; a system `ffmpeg` conversion that misplaces chroma is not accepted.
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

#### extended-non-camera-front-ends (optional)

Section 16.5's minimum mesh is one non-camera source; a second or third one is only worth its
installed cost if it is measured to add evidence the first did not.

- Serves: `sensor-adapter-frontends` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: non-camera-front-end, select-mesh-sensors.
- User-visible outcome: Each additional selected non-camera source, beyond the Stand C minimum, emits
  typed observations through its own adapter.
- Scope boundary: One adapter per additionally selected, measured source. An unselected or unmeasured
  candidate stays out of scope, and this task adds no new evidence role beyond spec section 7.6.
- Data and artifact paths: `src/ss_track/frontends/`, `tests/frontends/`.
- Execution path: Repeat the `non-camera-front-end` pattern per added source, with raw-format
  provenance and recorded fixtures for each.
- Acceptance gates: Conformance fixtures pass per source, and the section 16.5 valid-negative-result
  rule applies: a source that adds no measured evidence over the installed set is documented and
  removed from the active configuration, not hidden.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### sensor-adapter-frontends-audit (optional)

Front ends, capture and fake drivers each implement one observation contract, and a fault handled in
only one of them hides until a live run.

- Serves: `sensor-adapter-frontends` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every source reaches the mesh through one observation type, with faults
  handled the same way on fake and live paths.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`, `src/ss_track/corpus/`,
  `tests/corpus/`, `src/ss_track/frontends/`, `tests/frontends/`, `src/ss_track/capture/`,
  `tests/capture/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  camera and non-camera front ends repeat, and from how skew, overflow, outage and recovery are
  handled on each path.
- Acceptance gates: Mixed-modality bundles and the four scenario boundaries pass conformance, and
  fake-driver capture covers each fault named by the capability. Every finding is fixed, routed to a
  task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result when
  the record states what was reviewed.
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

#### fusion-generated-fixtures

Fusion needs repeatable failures across streams, and no generated case acts on a whole encounter.

- Serves: `fusion-analysis` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay.
- User-visible outcome: Recipes perturb a whole encounter with skew, jitter, late and reordered
  packets, modality loss, degraded measurements, calibration errors, shared artifacts, duplicates,
  contradictions and health misreports.
- Scope boundary: The fusion fixtures of spec section 4.3, including sensor loss. Each declares
  whether its independent reference stays valid. Live capture faults belong to
  `synchronized-sensor-capture`.
- Data and artifact paths: `src/ss_track/fusion/`, `src/ss_track/corpus/`, `tests/fusion/`.
- Execution path: Extend recipes and transform revisions to observation bundles, reusing seeded
  draws and case membership.
- Acceptance gates: A rerun with one seed is byte-identical. A case stays in its encounter and
  split, and an altered geometry or time relation updates its reference or makes that metric
  `NOT_SCOREABLE`. Real and simulated failures stay separate report slices.
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
- Dependencies: late-fusion-baseline, plugin-evaluator-core, fusion-generated-fixtures.
- User-visible outcome: The `FIXED_OBSERVATION_FUSION` boundary reports association, false merges,
  deduplication and abstention.
- Scope boundary: Fixed hashed bundles, existence/class calibration where independently labelled, and
  stage timing. Unsupported quantities remain explicitly unscorable with coverage shown.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with byte-identical bundle fixtures.
- Acceptance gates: A changed front end forces a new cohort, and raw data access fails conformance.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### imm-motion-model-bank (optional)

A constant-velocity-only prediction loses hovering, perching and banking small targets, the largest
measured error source in the paper this design adapts.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: late-fusion-baseline, fusion-calibration-suite.
- User-visible outcome: A four-model IMM (near-stationary, constant-velocity, constant-acceleration,
  coordinated-turn) is available as a declared alternative to the single-model prediction.
- Scope boundary: The filter bank and its Markov mode matrix, tuned on development encounters only.
  Association, track existence and classification stay in their own tasks.
- Data and artifact paths: `src/ss_track/fusion/`, `tests/fusion/`.
- Execution path: Add the four-model bank behind the existing motion-model interface, with a
  dwell-time-derived Markov matrix. Add hand-audited fixtures for a hovering, a circling and a banking
  target alongside the existing continuity fixtures.
- Acceptance gates: Paired development comparison against the single-model baseline on identical
  bundles reports `improved_on_development_corpus`, `regressed_on_development_corpus` or
  `inconclusive` per [section 6.3](../design/spec.md#63-comparisons-and-decision-status); an
  insufficient encounter count reports `insufficient_data` instead of a claim.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### jipda-track-existence (optional)

A fixed miss-count drop rule throws a track away on a run of weak returns that a probability would
have survived.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: late-fusion-baseline, imm-motion-model-bank.
- User-visible outcome: Each track carries an existence probability, confirmed above and deleted below
  declared thresholds, instead of a hit/miss counter.
- Scope boundary: Joint integrated probabilistic data association (JIPDA) over the existing gated
  association. A PMBM path for denser clutter stays the unscheduled alternative in spec section 7.6.
- Data and artifact paths: `src/ss_track/fusion/`, `tests/fusion/`.
- Execution path: Add existence-probability update and confirm/delete thresholds behind the
  `late-fusion-baseline` association step, with hand-audited fixtures for a weak-return run that
  should survive and a run that should not.
- Acceptance gates: A rerun with one seed is byte-identical. Paired development comparison against the
  fixed-drop-rule baseline on identical bundles reports its status per section 6.3; a correlated-source
  or overlapping-gate fixture never inflates existence.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fusion-analysis-audit (optional)

Fusion can look better by seeing what had not yet arrived, and each of its tasks can let that in
differently.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Fusion sees only what had arrived by event time, on every path, and its
  calibrated evidence has one source.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`, `src/ss_track/fusion/`,
  `src/ss_track/corpus/`, `tests/fusion/`, `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every read of an observation and the clock it uses, what the fixtures and the baseline repeat, and
  where a raw score could bypass calibration.
- Acceptance gates: Fixed hashed bundles keep their results, a late observation cannot affect an
  earlier decision, and abstention and degraded-source fixtures pass. Every finding is fixed, routed
  to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result
  when the record states what was reviewed.
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

#### fixed-input-tracker-evaluation-audit (optional)

A tracker result only isolates the tracker while its inputs stay fixed and its cost stays separate.

- Serves: `fixed-input-tracker-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Tracker scores and costs rest on fixed hashed inputs alone.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every input the suite reads and how tracker-stage cost is separated from what feeds it.
- Acceptance gates: A changed input is refused rather than scored, and SOT and MOT identity,
  re-entry and prediction fixtures pass. Every finding is fixed, routed to a task or dropped with
  its reason, and `make quality` passes. Finding nothing is a valid result when the record states
  what was reviewed.
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

#### imm-jipda-mesh-variant (optional)

The single constant-velocity reference is deliberately simple; a maneuvering small target is where a
richer model should earn its keep, if it does.

- Serves: `multi-source-reference-tracker` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: mesh-reference-tracker, jipda-track-existence.
- User-visible outcome: A declared IMM-JIPDA variant of the mesh tracker runs beside the simple
  reference on identical frozen bundles.
- Scope boundary: Wiring the spec section 7.6 IMM/JIPDA candidates into the existing track-maintenance
  interface. It is a measured alternative, never a replacement default, and filters beyond the
  four-model bank stay out of scope.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference-mesh/`.
- Execution path: Add the variant behind the same contract as `mesh-reference-tracker`, and run the
  spec section 7.8 TDD fixture list plus the hovering/circling/banking fixtures from
  `imm-motion-model-bank`.
- Acceptance gates: `FIXED_OBSERVATION_TRACKER` scores the variant and the reference on byte-identical
  bundles; the comparison reports `improved_on_development_corpus`, `regressed_on_development_corpus`
  or `inconclusive` per section 6.3, never an assumed win.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### multi-source-reference-tracker-audit (optional)

This is the project's reference implementation, and it will have grown from the single-camera
baseline.

- Serves: `multi-source-reference-tracker` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: The mesh tracker stays a readable reference, with provenance kept from every
  observation to every output.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference-mesh/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  it repeats from `reference-sot-tracker`, every output with no recorded origin, and each deadline
  path.
- Acceptance gates: Hand-audited provenance, identity and deadline fixtures pass on frozen
  observation bundles. Every finding is fixed, routed to a task or dropped with its reason, and
  `make quality` passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Track classification -- `track-classification`

#### track-cue-fusion

A confirmed track with no class says nothing about whether it is the target class this scenario
cares about.

- Serves: `track-classification` -- [Track-level classification](../design/spec.md#167-track-level-classification)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: mesh-reference-tracker, fusion-calibration-suite.
- User-visible outcome: A confirmed mesh track carries a calibrated class posterior fused from
  whichever of motion-mode history, radar micro-Doppler and camera-crop classification are installed.
- Scope boundary: Fusing already-available per-cue evidence into one posterior. A new camera-crop
  model, species/subtype recognition and any actuation stay out of scope.
- Data and artifact paths: `src/ss_track/classification/`, `tests/classification/`.
- Execution path: Add a Bayesian cue-fusion step reading `TrackState` mode history,
  `SensorObservation` micro-Doppler features where radar is installed, and a camera-crop classifier
  output; fit each cue and the fused posterior on the disjoint calibration split.
- Acceptance gates: Known-class, unknown-subtype, too-small-object and confident-wrong-class fixtures
  from the G2 recognition/state row of the
  [acceptance matrix](../design/spec.md#13-acceptance-and-negative-result-matrix) pass. An uninstalled
  or uncalibrated cue abstains rather than inventing a class, and a cue that adds no measured gain is
  a valid, documented negative result.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### track-classification-audit (optional)

A class label fused from several cues can look confident while no single cue backs it, and only a
review across the whole group catches that.

- Serves: `track-classification` -- [Track-level classification](../design/spec.md#167-track-level-classification)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every class posterior traces to the specific installed, calibrated cues that
  produced it.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/classification/`, `tests/classification/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  cue's calibration population and from what happens when every cue is absent at once.
- Acceptance gates: Known-class, unknown-subtype and confident-wrong-class fixtures pass, and
  coverage/calibration are reported beside tracking quality, never as a hidden composite score. Every
  finding is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding
  nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Pointing guidance and quality measurement -- `pointing-guidance-evaluation`

#### sensor-pointing-guidance-law

A tracker that only reports where a target was says nothing about how well a camera or beam could
have stayed on it.

- Serves: `pointing-guidance-evaluation` -- [Guidance pointing law](../design/spec.md#168-guidance-pointing-law-and-quality-measurement)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: reference-sot-tracker.
- User-visible outcome: A declared pointing law computes a sensor-pointing angular command from the
  current track prediction, with a fixed-stare null and a plain-PN variant as required comparators.
- Scope boundary: The pointing command only, for a camera, gimbal or electronically-steered antenna.
  No vehicle, effector, munition or interceptor output exists in this module, and an output of that
  type fails conformance.
- Data and artifact paths: `src/ss_track/guidance/`, `tests/guidance/`.
- Execution path: Implement the feedforward-plus-pure-pursuit blend in angle domain, a plain-PN
  variant and the fixed-stare null, behind one pointing-law interface. Add hand-audited fixtures for
  a near-zero line-of-sight-rate case (where the feedforward term matters) and a lost-track case
  producing a declared search/coast state instead of a stale command.
- Acceptance gates: Deterministic fixtures reproduce hand-computed angles for each law variant. A lost
  or unavailable track yields an explicit abstain/search state, never a stale command presented as
  fresh. A conformance fixture asserts the output type is a sensor-pointing command and rejects any
  attempt to emit a vehicle or effector command.
- Documentation target: [Current implementation](current.md#areas), new page `current/guidance.md`.

#### pointing-guidance-quality-suite

A guidance law that was never scored on held frames is a demonstration, not evidence.

- Serves: `pointing-guidance-evaluation` -- [Guidance pointing law](../design/spec.md#168-guidance-pointing-law-and-quality-measurement)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: sensor-pointing-guidance-law, plugin-evaluator-core.
- User-visible outcome: A local report scores pointing coverage, angular lead error, reacquisition
  delay and latency sensitivity for each law variant against the required comparators, on identical
  bundles.
- Scope boundary: The section 9/16.8 action-dependent image-plane simulator and its four reported
  quantities. No physical gimbal, PTZ head or antenna is actuated or characterized; that stays future
  hardware work under spec section 16.4.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Extend the G0 reference-tracker fixtures with a declared high-resolution wide source
  and an action-dependent IFoV hook; add hand-audited within-envelope cruise, sudden-turn,
  near-stationary and induced-loss fixtures; compute the four quantities with their denominators and
  exclusions.
- Acceptance gates: Hand-audited fixtures reproduce expected coverage, angular-error and reacquisition
  values. A target leaving the source recording's own field of view is a failure or `ABORT`, never an
  exclusion. The paired comparison against the fixed-stare null and the plain-PN baseline reports its
  status per section 6.3.
- Documentation target: [Current implementation](current.md#areas), page `current/guidance.md`.

#### pointing-guidance-evaluation-audit (optional)

A guidance law judged only by its own report can hide a command type it should never emit.

- Serves: `pointing-guidance-evaluation` -- [Guidance pointing law](../design/spec.md#168-guidance-pointing-law-and-quality-measurement)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every pointing command traces to a declared law variant and a scored fixture,
  with no path to a vehicle or effector output.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/guidance/`, `tests/guidance/`, `src/ss_track/suites/`,
  `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from the
  pointing-command output type on every path, and from what the suite repeats from the shared G3
  simulator and `plugin-evaluator-core`.
- Acceptance gates: No path emits a vehicle, munition or effector command. Coverage, angular-error and
  reacquisition fixtures pass, and `make quality` passes. Finding nothing is a valid result when the
  record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/guidance.md`.

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

#### g2-sensor-set-evaluation-audit (optional)

Comparing sensor sets means little unless one frozen fusion rule runs every set and the achieved
result stays apart from the ceiling.

- Serves: `g2-sensor-set-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every sensor set runs through one frozen rule, with achieved quality and the
  observability ceiling kept apart.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from how
  a set is enumerated and what differs between runs of two sets.
- Acceptance gates: Single, paired, all-installed and leave-one-out sets run through one rule, and
  the two quality values never merge. Every finding is fixed, routed to a task or dropped with its
  reason, and `make quality` passes. Finding nothing is a valid result when the record states what
  was reviewed.
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

#### installed-system-evaluation-audit (optional)

A whole-system result sits beside component results, and a panel that blends them would claim what
no trial measured.

- Serves: `installed-system-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Component and whole-system results stay separate in every panel, each from
  one trial.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `src/ss_track/report/`,
  `tests/report/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from how
  same-trial evidence is joined, and from what `g2-boundary-report` shares with the local report.
- Acceptance gates: Four local panels keep their boundaries, and quality, timing and energy of one
  row come from one trial. Every finding is fixed, routed to a task or dropped with its reason, and
  `make quality` passes. Finding nothing is a valid result when the record states what was reviewed.
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

#### mot-trackeval-audit (optional)

An adapter is only trusted while TrackEval computes the metrics and the adapter computes none.

- Serves: `mot-trackeval` -- [TrackEval adapter](../design/spec.md#8-trackeval-adapter-and-upgrade-policy)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: TrackEval alone computes MOT metrics, from a byte-exact export in a pinned
  environment.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  anything the adapter calculates itself, and from how the pin is enforced.
- Acceptance gates: Byte-exact per-class export fixtures and hand-audited MOT results hold. Every
  finding is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding
  nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Autonomous target recognition -- `target-recognition`

#### recognition-suite

Phase 2 replaces the operator's confirmation with the system's own declaration, and nothing yet
scores a declaration, an abstention or an unknown class.

- Serves: `target-recognition` -- [Target recognition](../design/spec.md#193-autonomous-target-recognition)
- Agent status: CLEAR
- Milestone: M7
- Dependencies: tracker-epoch-suite, fusion-calibration-suite, scenario-pack-contract,
  extent-envelope-view.
- User-visible outcome: A recognizer's `RecognitionResult` events are scored for declaration recall
  at a fixed false-declaration burden, time to declaration, abstention, calibration and open-set
  behavior.
- Scope boundary: The `RecognitionResult` event with the spec section 19.3 fields as an additive
  contract version, and the suite over frozen track and observation bundles. The scoring unit is
  the expert-labelled instance. The target set, known non-targets, unknown set, minimum
  identifiable extent, identifiable duration, declaration deadline and burden come from the
  scenario pack. No model, no training, and no behavior or individual identity.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/suites/`, `tests/contract/`,
  `tests/suites/`.
- Execution path: Add the event and the suite with hand-built known-target, look-alike,
  unknown-class, too-small, untracked, late and reversed-declaration fixtures. Choose the operating
  point on development encounters only, and report each result by extent bin.
- Acceptance gates: Hand-computed recall over eligible instances, burden, both delays,
  risk-coverage, instability and calibration match. An untracked target and a late declaration are
  misses, an unknown-set track declared as a target counts against the burden, and a reversal
  does not replace the first declaration. Exposure too short for the declared burden names no
  operating point, and a class with fewer than 10 encounter groups reports `insufficient_data`.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/recognition.md`.

#### reference-recognizer

A suite with no baseline cannot show whether fine-grained recognition is possible at the extents
the mesh observes.

- Serves: `target-recognition` -- [Target recognition](../design/spec.md#193-autonomous-target-recognition)
- Agent status: RUN NEEDED
- Milestone: M7
- Research: yes
- Dependencies: recognition-suite, track-cue-fusion, label-recognition-material.
- User-visible outcome: A pinned reference recognizer declares, rejects or abstains on confirmed
  tracks, with its quality by extent bin and its compute cost.
- Scope boundary: One small pinned model on confirmed-track regions, with the coarse posterior of
  `track-cue-fusion` as its comparator. Any fitting uses development encounters only, and
  probabilities use the calibration split. It is a baseline and sets no accuracy target.
- Data and artifact paths: `modules/reference-recognizer/`, `src/ss_track/recognition/`,
  `tests/recognition/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Keep the model and its dependencies under `modules/`, outside the core lock,
  with a recorded compute manifest and the portable CPU reference execution. Declared run: the
  recognition scenario on the expert-labelled material.
- Acceptance gates: The paired comparison against the coarse posterior reports its status per
  [section 6.3](../design/spec.md#63-comparisons-and-decision-status). A recognizer no better than
  the comparator, or a target set not identifiable at the corpus extents, is a valid negative result
  and keeps its evidence. Model weights and caches are a registered [data
  clean](current/corpus.md#cleaning-the-data-root) kind with a restore path and a test.
- Documentation target: [Current implementation](current.md#areas), page `current/recognition.md`.

#### target-recognition-audit (optional)

A declaration joins a track, a class posterior and a calibration, and a label that reaches fitting
by any of them makes the result look better than it is.

- Serves: `target-recognition` -- [Target recognition](../design/spec.md#193-autonomous-target-recognition)
- Agent status: CLEAR
- Milestone: M7
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every declaration traces to expert labels it was never fitted on, and an
  unknown class cannot become a target.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/suites/`,
  `src/ss_track/recognition/`, `modules/reference-recognizer/`, `tests/suites/`,
  `tests/recognition/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every read of a class label, the split each one comes from, and what the suite repeats from
  `track-cue-fusion` and the calibration suite.
- Acceptance gates: Known-target, look-alike, unknown-class and too-small fixtures keep their
  results, and a fitting run that names a calibration or locked encounter is refused. Every finding
  is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding nothing
  is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/recognition.md`.

### Compute variants -- `tensor-compute-backends`

#### compute-manifest-contract

A run that says it used an accelerator proves nothing unless the run records what executed where.

- Serves: `tensor-compute-backends` -- [Compute variants](../design/spec.md#194-compute-variants-and-energy-per-decision)
- Agent status: CLEAR
- Milestone: M7
- Dependencies: event-schema-contract, host-capability-probe.
- User-visible outcome: Every run names one compute variant and carries a compute manifest with
  its model, precision, backend, device, partition and fallback policy.
- Scope boundary: The manifest as a `record` contract with the spec section 7.3 fields, `opaque`
  with a reason where a black box hides one, and the variant identity in the cohort key. Analog
  and in-sensor stages use the same record. No runtime is added here.
- Data and artifact paths: `contracts/record/compute-manifest/`, `src/ss_track/contract/`,
  `tests/contract/`.
- Execution path: Add the contract, its registry entry and golden fixtures for a CPU reference, a
  declared mixed-device profile and an opaque variant.
- Acceptance gates: A manifest with an undeclared partition or a missing model hash is refused,
  an opaque field needs its reason, and a changed precision, backend or partition changes the
  variant identity. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### backend-capability-probe

A listed device or runtime provider does not show that a graph runs on it.

- Serves: `tensor-compute-backends` -- [Compute variants](../design/spec.md#194-compute-variants-and-energy-per-decision)
- Agent status: CLEAR
- Milestone: M7
- Dependencies: compute-manifest-contract, host-capability-probe.
- User-visible outcome: `ss-track hardware-probe` compiles and runs a representative graph for a
  requested variant and reports `SUPPORTED`, `UNSUPPORTED` or `MEASURE_REQUIRED` with the
  partition it observed.
- Scope boundary: A backend adapter interface, the pinned CPU reference execution, and recorded
  fixture backends. A real accelerated runtime stays under `modules/`, outside the core lock, and
  arrives with the variant that needs it.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`, `modules/`.
- Execution path: Add the adapter interface and the probe step with fixture backends that lack an
  operator, fall back silently and run fully.
- Acceptance gates: An accelerator-only request that needs CPU fallback is `UNSUPPORTED`, a
  declared mixed profile is accepted with its observed partition, and discovery alone never
  yields `SUPPORTED`. A frame-attributed undeclared fallback is a `MODULE_FAULT` under spec
  section 7.3.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### compute-variant-suite

A faster variant is no gain when it changes the answers or draws more over a mission.

- Serves: `tensor-compute-backends` -- [Compute variants](../design/spec.md#194-compute-variants-and-energy-per-decision)
- Agent status: CLEAR
- Milestone: M7
- Dependencies: backend-capability-probe, energy-metric-suite, development-decision-status,
  paced-frame-release.
- User-visible outcome: A report compares each supported variant with the CPU reference on one
  frozen workload: quality difference, latency, energy per scheduled decision and installed idle
  power.
- Scope boundary: The spec section 19.4 measures over saved bundles and traces, with
  `quality_equivalent` only under a predeclared margin. One host, workload, schedule and meter
  boundary per comparison. No operator microbenchmark as a result.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with recorded traces of known joules, a marked idle interval, a
  cold start and a variant that emits few results.
- Acceptance gates: Hand-calculated energy per decision, idle power and latency percentiles
  match. Energy divides by scheduled decisions, so a variant that emits few results gains
  nothing. An unverified backend's timing and energy are `UNSUPPORTED`, and a variant outside the
  margin is reported as a separate quality-cost point.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### tensor-compute-backends-audit (optional)

The manifest, the probe and the suite each state what ran where, and a run credited to a device it
did not use would pass all three separately.

- Serves: `tensor-compute-backends` -- [Compute variants](../design/spec.md#194-compute-variants-and-energy-per-decision)
- Agent status: CLEAR
- Milestone: M7
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: A variant's quality, timing and energy all rest on one verified statement
  of what executed.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `contracts/record/compute-manifest/`, `src/ss_track/contract/`,
  `src/ss_track/probe/`, `src/ss_track/suites/`, `tests/contract/`, `tests/probe/`,
  `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every place a device or partition is named, and from each energy figure and the interval it
  divides.
- Acceptance gates: Fallback fixtures keep their statuses, energy per decision recomputes from
  retained traces, and no result names a device its manifest does not show. Every finding is fixed,
  routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid
  result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Resource-aware sensing -- `resource-aware-sensing`

#### platform-energy-budget

A payload's joules mean little without the battery and the flight power they come out of.

- Serves: `resource-aware-sensing` -- [Platform energy budget](../design/spec.md#710-platform-energy-budget)
- Agent status: CLEAR
- Milestone: M7
- Dependencies: energy-metric-suite.
- User-visible outcome: A scenario declares a platform energy budget, and a report states measured
  payload energy as a fraction of its allowance, with model-derived endurance shown apart.
- Scope boundary: The budget as a `declaration` contract with the origin of each figure, the
  fraction, margin and peak checks over saved energy results, and one named endurance model. No
  propulsion measurement and no battery model beyond the declared figures.
- Data and artifact paths: `src/ss_track/energy/`, `tests/energy/`, `contracts/`, `scenarios/`.
- Execution path: Add the declaration, the calculation over `energy-metric-suite` results, and
  table-driven fixtures with measured, datasheet and assumed figures.
- Acceptance gates: Hand-calculated fractions, margins and overruns match. An unmeasured energy
  yields no fraction, a model-derived value never appears in a measured column, and a budget with
  only datasheet or assumed figures is labelled a design comparison.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### acquisition-policy-contract

A policy can look efficient by deciding with information it could not have had.

- Serves: `resource-aware-sensing` -- [Energy-budgeted acquisition](../design/spec.md#195-energy-budgeted-acquisition)
- Agent status: CLEAR
- Milestone: M7
- Dependencies: event-time-replay, sensor-observation-contract, platform-energy-budget.
- User-visible outcome: A policy module emits one `AcquisitionDecision` before each action, the
  runner applies it to recorded streams, and `BudgetState` tracks the declared window and limits.
- Scope boundary: The decision and budget events, the spec section 19.5 action space over
  installed sensors, camera rate and region, recognizer and tracker, causal enforcement in
  replay, wake latency and wake energy from a mode profile, and the energy tier of every result.
  Replay suppresses inputs only, so a result is `not_measurable` with no mode profile and
  `profile_derived` with one. A `measured` tier needs a live paired trial.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/runner/`, `tests/contract/`,
  `tests/runner/`.
- Execution path: Extend the event contract and the replay path, with a fixture mode profile and
  fixture policies that read the future, skip everything, exceed the budget and toggle a sensor
  faster than its wake latency.
- Acceptance gates: A causal test changes later observations and holds every earlier decision
  unchanged. A decision that names an uninstalled component or an unmeasured mode is refused, a
  skipped true event stays a miss in the fixed denominator, and a budget overrun is recorded as a
  violation. A sensor asked for data before its wake latency has passed returns a missing
  observation and is charged its wake energy, and every result states its energy tier.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### policy-comparator-suite

An adaptive policy means nothing until the fixed configurations it must beat have run on the same
encounters.

- Serves: `resource-aware-sensing` -- [Energy-budgeted acquisition](../design/spec.md#195-energy-budgeted-acquisition)
- Agent status: CLEAR
- Milestone: M7
- Dependencies: acquisition-policy-contract, late-fusion-baseline, installed-system-suite.
- User-visible outcome: `ss-track policy sweep` runs always-on, fixed-rate, fixed-subset,
  random-skip and event-triggered comparators, and reports quality, coverage, deadlines and budget
  use at one fixed task denominator.
- Scope boundary: The mandatory comparators of spec section 7.7, the labelled oracle upper bound,
  and the claim rule of spec section 19.5. Quality and process latency come from replay, a
  `profile_derived` energy supports a design comparison, and a saving needs `measured` trials. No
  learned controller.
- Data and artifact paths: `src/ss_track/policy/`, `src/ss_track/suites/`, `tests/policy/`,
  `tests/suites/`.
- Execution path: Add the comparators behind one policy interface and the suite, with skip-heavy,
  deadline, peak and rolling-budget fixtures.
- Acceptance gates: Hand-audited fixtures reproduce each comparator's misses, violations and
  budget use. A saving is reported only when the quality interval clears the predeclared margin
  and the whole energy interval lies below zero by more than the meter uncertainty. Any other
  outcome is `inconclusive` or `no_saving`. A `profile_derived` figure never appears in a measured
  column, and the oracle row is labelled a diagnostic.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### voi-reference-policy (optional)

A threshold rule reacts to uncertainty but does not weigh what an action costs against what it
would gain.

- Serves: `resource-aware-sensing` -- [Acquisition policy](../design/spec.md#77-resource-aware-acquisition-and-processing-policy)
- Agent status: CLEAR
- Milestone: M7
- Research: yes
- Dependencies: policy-comparator-suite, measure-sensor-power-modes.
- User-visible outcome: A one-step value-of-information policy chooses among feasible actions
  under the declared deadline, peak and rolling-energy limits, beside the mandatory comparators.
- Scope boundary: A calibrated one-step estimate fitted on development and calibration encounters
  only. A budgeted planner, a bandit and a learned controller stay out of scope.
- Data and artifact paths: `src/ss_track/policy/`, `tests/policy/`.
- Execution path: Add the policy behind the comparator interface, record predicted and realized
  task loss, energy and latency for every feasible action, and measure prediction error on
  encounters the fit never saw.
- Acceptance gates: The paired comparison against the best fixed configuration reports its status
  per [section 6.3](../design/spec.md#63-comparisons-and-decision-status) at matched quality. An
  inaccurate cost or benefit model is shown even when its choices succeeded, and no gain is
  claimed from a gain-per-joule ratio alone.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### resource-aware-sensing-audit (optional)

A budget, a decision and an energy result each carry a notion of what was measured, and a modelled
figure that crosses between them becomes a claim.

- Serves: `resource-aware-sensing` -- [Acquisition policy](../design/spec.md#77-resource-aware-acquisition-and-processing-policy)
- Agent status: CLEAR
- Milestone: M7
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every policy result keeps its fixed denominator, and no modelled or
  suppressed-stream figure reads as measured energy.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/energy/`, `src/ss_track/policy/`,
  `src/ss_track/runner/`, `src/ss_track/suites/`, `tests/energy/`, `tests/policy/`,
  `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every value a decision can read and when it became available, and from each energy figure and its
  origin.
- Acceptance gates: The causal replay test holds, each comparator keeps its hand-audited misses, and
  an unmeasured energy yields no fraction and no saving. Every finding is fixed, routed to a task or
  dropped with its reason, and `make quality` passes. Finding nothing is a valid result when the
  record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Stand-off following evaluation -- `standoff-following-evaluation`

#### following-simulator

A following law cannot be judged on recorded video, because the recording shows only the path its
operator flew.

- Serves: `standoff-following-evaluation` -- [Stand-off following](../design/spec.md#196-stand-off-following-evaluation)
- Agent status: CLEAR
- Milestone: M8
- Research: yes
- Dependencies: plugin-evaluator-core, scenario-pack-contract, platform-energy-budget.
- User-visible outcome: `ss-track follow evaluate` moves a simulated observer under a following
  law against reviewed or synthetic target trajectories, and records every step in a run bundle.
- Scope boundary: A kinematic observer in a local level frame with declared speed, acceleration
  and turn limits, a sensor envelope, a seeded wind disturbance, targets that do not react, and
  the `FollowingCommand` event in the `CLOSED_LOOP_SIM` lane. A law receives an estimated target
  state under a declared error model of range error, bearing error and latency, and every
  violation is scored on the true range. No vehicle dynamics model and no flight-controller,
  autopilot or radio interface.
- Data and artifact paths: `src/ss_track/following/`, `tests/following/`, `scenarios/`,
  `$DATA_DIR/run/<run-id>/`.
- Execution path: Add a fixed-step deterministic simulator with a declared support region, and
  straight, turning, hovering and nest-return fixture trajectories.
- Acceptance gates: A rerun with one seed is byte-identical, and replaying logged commands
  reproduces the path exactly. A law that tries to read the true target state fails conformance.
  A trajectory that leaves support is a failure or `ABORT`, never an exclusion. An import-boundary
  test shows that the package depends on no vehicle interface.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/following.md`.

#### standoff-following-law

The reference implementation has no control law, and a law taken from pursuit guidance would close
on the target it is meant to leave undisturbed.

- Serves: `standoff-following-evaluation` -- [Stand-off following](../design/spec.md#196-stand-off-following-evaluation)
- Agent status: CLEAR
- Milestone: M8
- Research: yes
- Dependencies: following-simulator.
- User-visible outcome: A reference law holds a stand-off range and bearing with a bounded closing
  speed, beside a stationary observer and a pursuit law clamped at the minimum stand-off.
- Scope boundary: Three laws behind one interface that emit `FollowingCommand` only, reading the
  tracker state, the platform state and the envelope. No law closes inside the minimum stand-off
  by design, and none has contact or capture as its objective.
- Data and artifact paths: `src/ss_track/following/`, `tests/following/`.
- Execution path: Add the six rules of the spec section 19.6 reference law and both comparators,
  with hand-audited fixtures for a steady target, a target that turns toward the observer, a lost
  track, an exclusion zone on the direct path and a set-point under the margin.
- Acceptance gates: Hand-computed commands match for each law and each rule. A scenario whose
  stand-off is under `d_min` plus the margin is refused before the run. A lost or stale track
  yields `HOLD`, `CLIMB_AWAY` or `ABORT`, never a command toward the last position. A target that
  turns toward the observer makes the law open the range, no command closes inside `d_alert`, and
  a conformance fixture rejects any command type other than `FollowingCommand`.
- Documentation target: [Current implementation](current.md#areas), page `current/following.md`.

#### following-quality-suite

A law that keeps the target in view by crowding it has failed, and a coverage number alone would
call it a success.

- Serves: `standoff-following-evaluation` -- [Stand-off following](../design/spec.md#196-stand-off-following-evaluation)
- Agent status: CLEAR
- Milestone: M8
- Dependencies: standoff-following-law, development-decision-status, visibility-gate.
- User-visible outcome: A report shows observation coverage, envelope violations, terminal
  observation, aborts and model-derived energy for each law on identical trajectories.
- Scope boundary: The spec section 19.6 quantities over saved simulation bundles, with a fixture
  envelope, including the error tolerance over declared grades of range error and latency. The
  mission pack is evaluated only with the envelope that `define-non-disturbance-envelope`
  supplies. No disturbance claim and no field result.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `src/ss_track/report/`,
  `tests/report/`.
- Execution path: Add the suite and a report panel, with a fixture law that violates the minimum
  stand-off and a paired comparison against the stationary observer.
- Acceptance gates: Hand-audited coverage, violations on the true range, error tolerance and
  aborts match. Any violation fails its encounter and blocks an improved status. A terminal zone
  is named by its identifier and never by coordinates, and a restricted pack's result is refused
  by a shareable export.
- Documentation target: [Current implementation](current.md#areas), page `current/following.md`.

#### standoff-following-evaluation-audit (optional)

The simulator, the laws and the suite each read the envelope, and one of them reading it loosely
would let a violation pass as coverage.

- Serves: `standoff-following-evaluation` -- [Stand-off following](../design/spec.md#196-stand-off-following-evaluation)
- Agent status: CLEAR
- Milestone: M8
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: One reading of the envelope decides every violation, and no path leads
  from a following law to a vehicle.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/following/`, `src/ss_track/suites/`,
  `src/ss_track/report/`, `tests/following/`, `tests/suites/`, `tests/report/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every comparison against an envelope value, every output type a law can emit, and each place a
  zone position could reach a report.
- Acceptance gates: The violating fixture law fails on every path, no module imports a vehicle
  interface, and no coordinate of a terminal zone appears in any output. Every finding is fixed,
  routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid
  result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/following.md`.

### Autonomous mission evaluation -- `autonomous-mission-evaluation`

#### autonomy-level-contract

A result obtained with an operator confirming every target can be read as an autonomous one unless
the run states which decisions a person took.

- Serves: `autonomous-mission-evaluation` -- [Autonomy levels](../design/spec.md#192-autonomy-chain-and-autonomy-levels)
- Agent status: CLEAR
- Milestone: M9
- Dependencies: operator-session-contract, recognition-suite.
- User-visible outcome: A scenario declares one autonomy level, the operator script acts only as
  that level permits, and every result and report names the level.
- Scope boundary: `A0_OPERATOR_SEEDED` to `A3_AUTONOMOUS` in the scenario and its cohort key, the
  confirmation and veto behavior of the script, and unanswered prompts at A3. No new operator
  model.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/runner/`, `tests/contract/`,
  `tests/runner/`.
- Execution path: Extend the scenario and the operator script, with fixtures for a confirmed
  proposal, a vetoed declaration, a veto after its window and an unanswered prompt.
- Acceptance gates: A changed level changes the cohort key, and a comparison across levels is
  refused unless it is declared as a level comparison. No action is released at A3, a veto after
  its window has no effect, and a prompt changes no denominator at any level.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### mission-evidence-tables

A mission simulation is only as honest as the numbers it draws from, and a guessed number looks
like a measured one once it sits in a table.

- Serves: `autonomous-mission-evaluation` -- [Autonomous mission](../design/spec.md#197-autonomous-mission-evaluation)
- Agent status: CLEAR
- Milestone: M9
- Dependencies: extent-envelope-view, recognition-suite, compute-variant-suite,
  acquisition-policy-contract, platform-energy-budget.
- User-visible outcome: `ss-track mission evaluate` reads evidence tables built from saved suite
  results, each with its origin and the hash of the run it came from.
- Scope boundary: A `declaration` contract for the spec section 19.7 tables, a builder that fills
  a table from saved results without recomputing them, and the origins `measured`, `datasheet`
  and `assumed`. No interpolation across an empty bin: an empty cell stays empty and is reported.
- Data and artifact paths: `contracts/declaration/mission-evidence/`, `src/ss_track/mission/`,
  `tests/mission/`, `scenarios/`.
- Execution path: Add the contract and the builder with fixture results, a missing bin, a mixed
  origin and a source run whose hash has changed.
- Acceptance gates: A `measured` cell with no source hash is refused, a changed source run is
  refused, and an empty bin is never filled from its neighbors. A table with any `datasheet` or
  `assumed` cell marks every result that reads it `design_only`.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/mission.md`.

#### mission-simulator

Each suite scores one decision on frozen input, and none shows whether the decisions complete a
mission together.

- Serves: `autonomous-mission-evaluation` -- [Autonomous mission](../design/spec.md#197-autonomous-mission-evaluation)
- Agent status: CLEAR
- Milestone: M9
- Research: yes
- Dependencies: following-simulator, standoff-following-law, mission-evidence-tables,
  autonomy-level-contract.
- User-visible outcome: A mission episode runs acquisition, recognition, the acquisition policy
  and following in one closed loop, and ends in exactly one outcome.
- Scope boundary: The kinematic simulator of `following-simulator` with surrogate perception
  drawn from the evidence tables under a recorded seed, range turned into extent through the
  measured angular resolution and the pack's declared target size, and the outcome precedence of
  spec section 19.7. No image rendering, no reacting target and no vehicle interface.
- Data and artifact paths: `src/ss_track/mission/`, `tests/mission/`, `scenarios/`,
  `$DATA_DIR/run/<run-id>/`.
- Execution path: Add the episode loop over the existing simulator and laws, with one fixture
  episode per outcome and tables of probability 0 and 1.
- Acceptance gates: Tables of probability 0 and 1 give hand-computed outcomes, a fixed seed gives
  byte-identical bundles, and each fixture episode ends in its expected outcome under the
  precedence. A table with known probabilities reproduces its expected fractions within the
  declared tolerance, and the stated independence of draws appears in every result.
- Documentation target: [Current implementation](current.md#areas), page `current/mission.md`.

#### mission-outcome-suite

A success rate at one distance hides what the mission's two constraints cost each other.

- Serves: `autonomous-mission-evaluation` -- [Autonomous mission](../design/spec.md#197-autonomous-mission-evaluation)
- Agent status: CLEAR
- Milestone: M9
- Dependencies: mission-simulator, following-quality-suite, operator-workload-suite.
- User-visible outcome: A report shows outcome fractions per autonomy level, interventions per
  mission at A1 and A2, and the stand-off trade-off of recall, time to declaration, energy and
  outcomes against distance.
- Scope boundary: The spec section 19.7 quantities over saved episode bundles, with intervals
  clustered by trajectory. No field, range or disturbance claim, and no recomputation of a
  surrogate's source result.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `src/ss_track/report/`,
  `tests/report/`.
- Execution path: Add the suite and a report panel, with fixture episodes at three stand-off
  levels and two autonomy levels.
- Acceptance gates: Hand-computed fractions, intervals and trade-off points match. A stand-off
  under the margin is refused, a `design_only` result is labelled in every panel, and a restricted
  pack's result is refused by a shareable export.
- Documentation target: [Current implementation](current.md#areas), page `current/mission.md`.

#### autonomous-mission-run

Phase 2 ends on a mission result for the mission pack, including one that says the mission is not
feasible with the installed sensors.

- Serves: `autonomous-mission-evaluation` -- [Autonomous mission](../design/spec.md#197-autonomous-mission-evaluation)
- Agent status: RUN NEEDED
- Milestone: M9
- Dependencies: mission-outcome-suite, define-non-disturbance-envelope,
  declare-platform-energy-budget.
- User-visible outcome: The mission pack has outcome fractions at `A1_OPERATOR_CONFIRMED` and
  `A3_AUTONOMOUS` and a stand-off trade-off, with each table's origin shown.
- Scope boundary: The approved envelope, the declared budget and whatever measured tables exist.
  A table still `assumed` or `datasheet` keeps the result `design_only`. No flight and no claim
  about a living subject.
- Data and artifact paths: `scenarios/`, `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Declared run of the mission scenario through `ss-track mission evaluate` at the
  declared stand-off and autonomy levels.
- Acceptance gates: Every Phase 2 mission row of the acceptance matrix passes, and recompute matches
  stored results. A result that no permitted stand-off leaves an identifiable extent, or that no
  policy meets the budget, is reported with its evidence and returns to hardware selection. Episode
  scratch is a registered [data clean](current/corpus.md#cleaning-the-data-root) kind with a restore
  path and a test.
- Documentation target: [Current implementation](current.md#areas), page `current/mission.md`.

#### autonomous-mission-evaluation-audit (optional)

The mission result reads numbers from every other Phase 2 suite, and one table that drifts from
its source would change the outcome with nothing to show it.

- Serves: `autonomous-mission-evaluation` -- [Autonomous mission](../design/spec.md#197-autonomous-mission-evaluation)
- Agent status: CLEAR
- Milestone: M9
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every mission outcome traces to source results by hash, and no modelled
  or assumed figure reads as measured.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/mission/`, `src/ss_track/suites/`,
  `src/ss_track/report/`, `tests/mission/`, `tests/suites/`, `tests/report/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  table cell and its source, the definition of a violation here and in the following suite, and
  every place an origin label is shown.
- Acceptance gates: Outcome fixtures keep their precedence, a changed source run is refused, and
  `design_only` appears wherever an unmeasured table is read. Every finding is fixed, routed to a
  task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result when
  the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/mission.md`.

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
  Setup energy never enters ranked energy. Per-run caches and container state are a registered
  [data clean](current/corpus.md#cleaning-the-data-root) kind with a test.
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

#### paced-thermal-trial-audit (optional)

A thermal claim needs heat to be the only difference, and a negative result must survive every
refactor.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Heat is the only difference between compared runs, and a negative outcome
  stays reported.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/thermal/`, `tests/thermal/`, `src/ss_track/suites/`,
  `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  difference between cool, hot and capped runs, and from how throttling is told from temperature.
- Acceptance gates: Hand-audited fixtures hold on identical frames, a hot run with no throttling
  stays `not_tested`, and a failed bet stays in the report. Every finding is fixed, routed to a task
  or dropped with its reason, and `make quality` passes. Finding nothing is a valid result when the
  record states what was reviewed.
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

#### benchmark-ranking-audit (optional)

A rank is the most quoted output of the project, so every route around its minimum requirements must
be closed.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: One rule produces every rank, and a row below the minimum stays unranked.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/ranking/`, `tests/ranking/`, `scenarios/`,
  `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<snapshot-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  route from a score to an order, and from what the snapshot shares with the local report.
- Acceptance gates: Scores recompute exactly, an inconclusive or refused cohort yields no rank, and
  a snapshot re-run gives the same bytes. Every finding is fixed, routed to a task or dropped with
  its reason, and `make quality` passes. Finding nothing is a valid result when the record states
  what was reviewed.
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
- Scope boundary: The suite, adapter contract and same-stimulus cohort key. A device that exposes
  telemetry rather than events uses a `telemetry-ingest` profile. Bench hardware is a human
  task.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `modules/`.
- Execution path: Add fixture events from two simulated devices.
- Acceptance gates: A device with no output path is `UNSUPPORTED`. Only same-stimulus, same-class,
  same-boundary cases are compared; incompatible or missing references are refused. Results
  are unranked and never pooled into a hardware-agnostic ranking.
- Documentation target: [Current implementation](current.md#areas), new page `current/bench.md`.

#### device-bench-evaluation-audit (optional)

Device cases sit near ranked results, and must not gain a rank by sharing their code.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: CLEAR
- Milestone: M5
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Device results stay unranked, and missing device output stays `UNSUPPORTED`.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `modules/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  the suite shares with ranked paths, and from each case with no operator seed.
- Acceptance gates: Same-stimulus fixtures stay valid, incompatible references are refused, and no
  device result reaches a rank. Every finding is fixed, routed to a task or dropped with its reason,
  and `make quality` passes. Finding nothing is a valid result when the record states what was
  reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Telemetry ingest -- `telemetry-ingest`

#### telemetry-bundle-store (optional)

Telemetry has nowhere to live as evidence, because import takes only video.

- Serves: `telemetry-ingest` -- [Telemetry bundles](../design/spec.md#182-telemetry-bundles)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: none.
- User-visible outcome: `ss-track telemetry import`, `stage` and `verify` turn a declared source into
  a sealed bundle of raw typed columns.
- Scope boundary: Contracts for the source declaration and the source and bundle records, the column
  store, and a declared CSV reader as the first format. No profiles, analysis or live capture.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/`,
  `$DATA_DIR/import/<source-sha256>/`, `$DATA_DIR/telemetry/<bundle-sha256>/`.
- Execution path: Reuse `sealing.py` and `sealed.py`, the locks, scratch and publish-by-rename of
  `corpus/storage/`, and the source-terms checks by generalizing them, with no parallel copy. Store
  one little-endian file per field under a sealed index.
- Acceptance gates: Two stagings across data roots, and on x86-64 and arm64, give one hash. A float
  column round-trips bit-exact, including NaN payloads. A flipped column byte fails `verify` by
  name. Rights and retention refuse as they do for a recording. Staging scratch and decoded
  intermediates are registered [data clean](current/corpus.md#cleaning-the-data-root) kinds with
  restore paths and tests.
- Documentation target: [Current implementation](current.md#areas), new page `current/telemetry.md`.

#### telemetry-profiles (optional)

A field name means nothing across firmware, so a value needs a canonical channel, unit and clock.

- Serves: `telemetry-ingest` -- [Profiles](../design/spec.md#183-profiles-and-canonical-channels)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-bundle-store.
- User-visible outcome: A versioned profile maps source fields to canonical channels at read, and
  `telemetry report` lists unmapped, absent and drifted fields.
- Scope boundary: Channel catalog and profile contracts, the observed-schema hash and the comparison.
  No format reader. A profile changes no bundle.
- Data and artifact paths: `contracts/telemetry/`, `src/ss_track/telemetry/`, `tests/telemetry/`.
- Execution path: Add the catalog and one profile over the CSV reader, with fixtures for each outcome
  of spec section 18.4.
- Acceptance gates: An unmapped field stays listed. An absent mapped field makes its channels
  `NOT_MEASURABLE`. A changed type or declared unit is `TELEMETRY_SCHEMA_DRIFT`. A new profile version
  fixing a unit changes no bundle hash, and a result names the profile version. A software-reported
  rail cannot become a calibrated `PowerSample`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### flight-log-readers (optional)

PX4 and ArduPilot logs carry their own schema, so one reader each covers every firmware.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: ULog and DataFlash logs stage into bundles, with dropouts, parameters and
  logged text retained.
- Scope boundary: Readers written from the format definitions with the standard library and NumPy.
  Example profiles for battery, attitude and position channels. No vehicle-health verdict.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `pyproject.toml`.
- Execution path: Walk framing once, then decode each message type as one array in bounded chunks.
  Generate logs in tests, and keep `pyulog` in the dev extra as an oracle.
- Acceptance gates: Values match the oracle and hand tables, across nested formats, multi-instance
  topics, absent trailing padding, `FMT`, `UNIT`, `MULT` and `FMTU`. An unknown incompatible flag
  refuses, an unknown message is skipped and counted, and a log cut mid-message loses only that
  message. The measured decode rate on each CI architecture is recorded.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### board-telemetry-sources (optional)

A board's counters explain timing and throttling, and each vendor exposes them differently.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles, host-capability-probe.
- User-visible outcome: A recorded or sampled hwmon, thermal, cpufreq, devfreq and powercap tree,
  `vcgencmd` output and `tegrastats` lines become bundles, with profiles for Raspberry Pi 5, Jetson
  and a generic x86 host.
- Scope boundary: Unprivileged reads through a replaceable root, sharing one source with
  `host-capability-probe`. Accelerator vendor tools stay out until a selected host needs one.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/telemetry/`.
- Execution path: Add recorded-tree fixtures, select chips by `name` and channels by label, and keep
  raw ABI integers in columns with their units in the profile.
- Acceptance gates: Hand-computed values match, including `get_throttled` bits and an `energy_uj`
  wrap. Renumbered hwmon directories change nothing. `tegrastats` lines with absent engines parse with
  those channels absent. A value re-read within `update_interval` is not a new sample. A root-only
  source is `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### mavlink-log-reader (optional)

A ground station's telemetry log needs an external dictionary, and its time is arrival time.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A `.tlog` stages into a bundle under a pinned MAVLink XML dialect.
- Scope boundary: Reading MAVLink 1 and 2 frames only. Nothing is ever sent, so signing verification
  is out of scope.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/external/`.
- Execution path: Compile a dialect to record layouts, applying wire order and `CRC_EXTRA`, then reuse
  the array decode path.
- Acceptance gates: Hand vectors cover field reordering, truncated trailing zeros, extension fields
  and a signed frame. A `CRC_EXTRA` mismatch is named as a dictionary mismatch. An unknown message id
  and an unknown incompatible flag are counted. Log times are recorded as arrival times.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### blackbox-log-reader (optional)

Blackbox logs hold high-rate flight data with no checksum, so damage must stay visible.

- Serves: `telemetry-ingest` -- [Drift, loss and gaps](../design/spec.md#184-drift-loss-and-gaps)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A Betaflight Blackbox file stages each session into a bundle.
- Scope boundary: The documented encodings and predictors, written from the public description. iNav
  differences are out of scope until a sample exists.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`.
- Execution path: Parse `H` field lines into a per-frame schema, then reverse each encoding and
  predictor, and add hand-encoded fixtures.
- Acceptance gates: Every encoding and predictor matches a hand-computed frame. A dropped byte rejects
  that frame and following `P` frames until the next `I`, with the counts recorded. Sessions in one
  file stay separate, and rejected frames are never interpolated.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### mcap-log-reader (optional)

ROS 2 bags and other robotics logs use MCAP, which carries each channel's schema in the file.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: An MCAP file stages into a bundle, with one observed schema per channel.
- Scope boundary: Channels with `protobuf` or `jsonschema` schemas, and a `cdr` subset for fixed
  layouts. Zstd and LZ4 sit in an optional extra. Image and point-cloud payloads stay opaque blobs
  with their hashes.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `pyproject.toml`.
- Execution path: Read opcode-framed records, with the summary section when present and a scan when
  not. Keep `mcap` in the dev extra as an oracle.
- Acceptance gates: Chunked and unchunked files match the oracle. A CRC mismatch refuses, an unknown
  record is skipped and counted, `log_time` and `publish_time` stay separate, and a file with no
  summary reads by scanning.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### declared-binary-layouts (optional)

A simple sensor should need a declaration, not a new reader.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A profile declares a fixed record or TLV layout, or reads an IIO
  `scan_elements` tree, and the source stages with no new code.
- Scope boundary: Fixed records, tagged length-value frames, a magic word, and bit fields with a
  shift. A format needing more is refused with a reason and gets a reader.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/telemetry/`.
- Execution path: Compile a layout to a NumPy dtype, parse the IIO `type` grammar, and add one radar
  TLV profile pinned to its SDK version.
- Acceptance gates: Hand cases cover `le:s12/16>>4`, big-endian, repeats and channel order. A TLV
  fixture passes with no code beyond the profile. An unknown TLV type is skipped and counted. A
  declared size that disagrees with a frame refuses.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### camera-telemetry-readers (optional)

A camera's motion and exposure metadata can explain blur and loss, and it arrives beside the video.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A GoPro GPMF track and a libcamera per-frame metadata sidecar stage into
  bundles linked to their video source.
- Scope boundary: Reading only. Tying samples to frames follows section 5 clock rules. Other camera
  vendors wait for a sample.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`.
- Execution path: Read the `gpmd` track, parse KLV with `SCAL`, `SIUN`, `TYPE` and `TSMP`, and keep
  `py-gpmf-parser` in the dev extra as an oracle.
- Acceptance gates: Hand KLV fixtures cover nesting, scale, complex types and alignment. Payload time
  never assumes a uniform rate inside a payload. GNSS channels are `sensitive`. A `SensorTimestamp`
  from a pipeline that fills it from DMA time is not labelled as exposure time.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### live-telemetry-capture (optional)

Real-time streams must lose data visibly, and must never slow what they observe.

- Serves: `telemetry-ingest` -- [Live streams](../design/spec.md#185-live-streams)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: board-telemetry-sources, declared-binary-layouts, mavlink-log-reader.
- User-visible outcome: `ss-track telemetry record` writes sealed segments from a sysfs poll, IIO
  buffer, serial link or UDP mirror, with loss accounting.
- Scope boundary: Passive sources through bounded queues. Sending anything to a source is out of
  scope. Synchronized multi-sensor capture stays with `synchronized-sensor-capture`.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`,
  `$DATA_DIR/telemetry/<bundle-sha256>/`.
- Execution path: Use replaceable sources and fake clocks, add a declared capture contract, and
  measure the sustainable rate per host.
- Acceptance gates: Overflow, disconnect and recovery fixtures account for all loss with time ranges.
  A killed process leaves only complete segments. A fixture source shows nothing was written to it. A
  declared rate above the measured one is `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### telemetry-analysis-report (optional)

Stored columns help nobody until they answer what ran, what was lost and what changed.

- Serves: `telemetry-ingest` -- [Drift, loss and gaps](../design/spec.md#184-drift-loss-and-gaps)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: flight-log-readers.
- User-visible outcome: `ss-track telemetry report` gives per-channel rates, gaps, dropouts, ranges
  and throttle and thermal timelines, and compares the schema and rates of two bundles.
  `telemetry export` writes Parquet, Arrow or CSV.
- Scope boundary: Local HTML and JSON, descriptive statistics only. No safety, airworthiness or
  health verdict. `pyarrow` is an optional extra, and an export is never evidence.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Compute from columns through a named profile, and add two fixture firmware versions
  of one log.
- Acceptance gates: Hand-computed rates and gap lists match. Two firmware fixtures show their schema
  difference exactly. A restricted bundle refuses a shareable export without leaking a value, and a
  shareable export holds no `sensitive` channel uncoarsened. Exported values equal the columns.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### telemetry-corpus-streams (optional)

Platform telemetry beside a video encounter must obey the same split and rights rules.

- Serves: `telemetry-ingest` -- [Boundary](../design/spec.md#186-boundary)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles, g2-scenario-observation-bundles.
- User-visible outcome: A telemetry bundle joins an encounter as a platform-state stream, and replay
  releases it at its availability time.
- Scope boundary: Split, rights and clock rules for one more stream kind. A platform-state sample
  stays context and is never an object detection.
- Data and artifact paths: `src/ss_track/corpus/`, `src/ss_track/telemetry/`, `tests/corpus/`.
- Execution path: Extend the corpus declaration by an optional field under a minor contract version,
  and extend the frame set to name telemetry bundles.
- Acceptance gates: A corpus using no telemetry keeps every hash. A telemetry stream inherits its
  encounter's split, and a source crossing splits is `SPLIT_LEAKAGE`. With no declared clock relation,
  alignment with video is `NOT_MEASURABLE`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### telemetry-ingest-audit (optional)

Readers, stores and reports arrive one format at a time, which is where a reader-specific rule and
a filled gap are most likely to appear.

- Serves: `telemetry-ingest` -- [Telemetry bundles](../design/spec.md#182-telemetry-bundles)
- Agent status: CLEAR
- Milestone: M6
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every reader follows one interface and one rule for time, loss and drift,
  and nothing fills a gap.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/`,
  `$DATA_DIR/import/<source-sha256>/`, `$DATA_DIR/telemetry/<bundle-sha256>/`,
  `contracts/telemetry/`, `pyproject.toml`, `contracts/external/`, `$DATA_DIR/run/<run-id>/`,
  `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  the readers repeat, which reader could become a declared layout, and how each one reports loss and
  clock source.
- Acceptance gates: Readers match an independent reader on generated logs, bundles hash identically
  across hosts, and drift, loss and truncation are reported and never filled. Every finding is
  fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is
  a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

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
- Execution path: Parse wrapped fields, then add the checks with failing fixtures. Read an audit's
  `every other agent task in this group` as a dependency on each of them.
- Acceptance gates: Fixtures reject unknown IDs, cycles and required tasks that depend on optional work,
  and accept valid cross-lane dependencies. A blocked earlier task is never reported as ready, and an
  audit is not ready while another agent task of its group is open.
- Documentation target: [Governance](current/governance.md).

#### current-corpus-page-split (optional)

The corpus page has grown far past an orientation, so a reader cannot find a rule, and two of its
sections can state one rule differently.

- Serves: `documentation-integrity` -- [Planning integrity](../design/spec.md#documentation-and-planning-integrity)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: `current/corpus.md` is a short orientation and index, and each topic has
  one focused page under `current/corpus/`.
- Scope boundary: A move of text with its anchors. No behavior statement changes. Anchors that a
  closed record links stay resolvable, because a closed record is not rewritten.
- Data and artifact paths: `docs/impl/current/corpus.md`, `docs/impl/current/corpus/`,
  `docs/impl/plan.md`, `docs/design/`, `docs/impl/workloads/`.
- Execution path: Split along the page's second-level sections, keep one statement of each rule,
  and update every inbound link in the plan, the specification, the guides and the workloads.
- Acceptance gates: `make lint-doc-links` and `make lint-md` pass, no rule is stated on two pages,
  and every record link still resolves.
- Documentation target: [Corpus](current/corpus.md).

#### documentation-integrity-audit (optional)

A rule stated in prose can drift from the checker, and a rule nobody can check is one nobody keeps.

- Serves: `documentation-integrity` -- [Planning integrity](../design/spec.md#documentation-and-planning-integrity)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Each rule in `AGENTS.md` that a machine can check is checked, and each check
  has a failing fixture.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/quality/plan_model.py`,
  `src/ss_track/quality/plan_integrity.py`, `tests/quality/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  `AGENTS.md`, the planning workflow and the planning integrity section of the specification
  against `plan_integrity.py`, `plan_model.py`, `plan_summary.py` and `doc_links.py`.
- Acceptance gates: Every checked rule has a failing fixture, every stated rule is checked or named
  as human judgment, and the checker is tightened or unchanged. Every finding is fixed, routed to a
  task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result when
  the record states what was reviewed.
- Documentation target: [Governance](current/governance.md).

## Human-Assisted Tasks

Follow the [hardware support flow](../design/test-stands.md#selection-flow).
Acquisition and physical operation require the responsible person; agent tooling
prepares protocols, analyzes evidence and produces reviewable selection records.

### Corpus provenance -- `corpus-provenance`

#### define-locked-test-policy (optional)

A locked test needs a named custodian and access rules that no software can supply.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: none.
- User-visible outcome: A named custodian holds a written access policy, so a locked split can
  support a held-out claim.
- Scope boundary: The spec section 15 custodian and access inputs. Runner enforcement belongs to
  `locked-split-guard`.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/`, with the policy hash.
- Execution path: The owner names a custodian and records who may read, tune against or re-score
  locked material.
- Acceptance gates: A hashed policy exists before any locked evaluation. With no custodian, a
  `locked` split stays membership only and no held-out claim is made.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Annotation and selection -- `annotation-selection`

#### approve-mission-scenario-pack

The mission's classes, smallest scorable extents and strata are the owner's to state, and labels
frozen against a draft pack would have to be made again.

- Serves: `annotation-selection` -- [Mission and phases](../design/spec.md#mission-and-phases)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: scenario-pack-contract.
- User-visible outcome: The `aerial-small-objects` pack has owner-approved classes, roles, minimum
  extents, extent bins, floors and observer-platform strata, and its hash is recorded.
- Scope boundary: Phase 1 values only. Fine-grained species and drone types and the
  non-disturbance envelope are later human tasks and stay empty slots.
- Data and artifact paths: `scenarios/packs/`.
- Execution path: The owner reviews the draft against the pilot footage and states each value with
  its basis. An agent validates the pack and records its hash.
- Acceptance gates: The pack validates and every value has a stated basis. A value the owner
  cannot state stays unset, and each view that needs it is reported unavailable.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### label-pilot-encounters

G0a needs only one positive and one negative encounter, so it should not wait for the whole corpus.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: annotation-review-tools, approve-mission-scenario-pack.
- User-visible outcome: Two encounters have frozen labels, selections and masks.
- Scope boundary: The pilot encounters, including motion events. The pass also measures labelling
  time per encounter. Review every frame of the selected negative window for target absence, and
  leave any uncertain frames unknown; the initial selection used a one-frame-per-second survey.
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
- Dependencies: label-pilot-encounters.
- User-visible outcome: At least 10 independent encounter groups have frozen labels.
- Scope boundary: Labelling and review. The sample-size pilot may add groups, and larger corpora may
  use a declared review sample plus all difficult cases.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Two reviewers label and settle disagreements under a named authority.
- Acceptance gates: Validation passes, groups are independent by the spec section 4.1 rule, and the
  revision is frozen. Unlabelable objects stay `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Self-supervised video corpus -- `self-supervised-corpus`

#### authorize-airborne-observer-sources

The Phase 1 mission claim needs footage from a flying observer, and the reviewed pilot holds
almost none.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: HUMAN-GATED
- Dependencies: none.
- User-visible outcome: An approval record names each airborne-observer source the owner permits,
  with its terms, transfer budget and intended split, or states that none is available.
- Scope boundary: Sources whose camera flew, including the owner's own recordings and public
  collections such as the
  [Airborne Object Tracking dataset](https://registry.opendata.aws/airborne-object-tracking/) and
  [Det-Fly](https://github.com/Jake-WU/Det-Fly). Each candidate's license, annotation semantics
  and overlap with other sources are checked first. No capture is solicited to fill a stratum, and
  a source that ships as images waits for `frame-sequence-source-import`.
- Data and artifact paths: `docs/impl/workloads/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: An agent inventories each candidate's terms and upstream identity through the
  source inventory. The owner approves or declines each one and declares its observer platform.
- Acceptance gates: Every approved source has recorded terms, attribution and an observer
  platform. A declined or unavailable source is recorded with its reason, and with none approved
  the extent envelope states that it holds no airborne-observer encounter.
- Documentation target: [Corpus](current/corpus.md).

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
- Data and artifact paths: `$DATA_DIR/selection/<selection-id>/`, `$DATA_DIR/run/<run-id>/`,
  `scenarios/stands/`.
- Execution path: A person obtains approved candidates, starting from the compute-host options in the
  [mesh hardware shortlist](../design/mesh-hardware-shortlist.md); an agent runs probe, null-module and
  reference-tracker trials on each under the same declared workload and limits, then stages the fixed
  corpus on each from sources carried from x86-64 and compares them with `ss-track corpus compare`.
- Acceptance gates: Each measured candidate has traceable evidence, rejection reasons and a staged-hash
  comparison on the candidate itself. A comparison of `different` names each source and narrows that
  host's claim to the sources it does not name. A single available candidate is a provisional choice,
  not a comparative selection. No qualifying host is valid; revise the requirement before claiming
  support.
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
- Execution path: A person obtains approved candidates, starting from the datasheet-sourced candidates
  in the [mesh hardware shortlist](../design/mesh-hardware-shortlist.md), and documents raw formats,
  drivers, access conditions, independent reference needs and a minimum test for each required
  quantity.
- Acceptance gates: Every candidate has an executable measurement plan and a supported software need.
  Missing references or unaffordable candidates remain unmeasured with the limitation recorded.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

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

### Autonomous target recognition -- `target-recognition`

#### label-recognition-material

A species or drone type can be scored only against labels from someone able to identify it.

- Serves: `target-recognition` -- [Target recognition](../design/spec.md#193-autonomous-target-recognition)
- Agent status: HUMAN-GATED
- Milestone: M7
- Dependencies: scenario-pack-contract, annotation-review-tools, recognition-suite.
- User-visible outcome: The mission pack names its target set and unknown-class set, and reviewed
  tracks carry expert class labels in development, calibration and evaluation encounters.
- Scope boundary: Fine-grained class labels on visually identifiable material, the minimum
  identifiable extent and the false-declaration burden. No behavior label and no individual
  identity. Material nobody can identify stays `unknown`.
- Data and artifact paths: `scenarios/packs/`, `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: A person with the needed expertise labels and reviews under a named authority.
  An agent validates, freezes and hashes the revision.
- Acceptance gates: Validation passes, the three splits are disjoint by encounter, and each class
  states its label count. A class with too few labels is recorded as such and its claim stays
  closed.
- Documentation target: [Current implementation](current.md#areas), page `current/recognition.md`.

### Compute variants -- `tensor-compute-backends`

#### measure-compute-variants

Energy per decision is a property of a real device on a real supply.

- Serves: `tensor-compute-backends` -- [Compute variants](../design/spec.md#194-compute-variants-and-energy-per-decision)
- Agent status: BLOCKED BY HUMAN
- Milestone: M7
- Dependencies: compute-variant-suite, reference-recognizer, select-reference-host,
  calibrate-bench-instruments.
- User-visible outcome: The reference recognizer has measured quality, latency, energy per
  decision and idle power on the CPU reference and on each accelerated or analog variant the
  owner can supply.
- Scope boundary: The selected host under the spec section 7.9 protocol. No purchase is required,
  and zero accelerated variants is a stated result.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`, `modules/`.
- Execution path: A person installs each device and connects the meter. An agent probes each
  variant and runs the paced workload with marked intervals.
- Acceptance gates: Raw traces reproduce every figure with its uncertainty. An unsupported or
  unverified variant is recorded as such, and with no accelerated variant the CPU reference
  result stands alone.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Resource-aware sensing -- `resource-aware-sensing`

#### declare-platform-energy-budget

An energy budget is a statement about a real aircraft, and only its owner can make it.

- Serves: `resource-aware-sensing` -- [Platform energy budget](../design/spec.md#710-platform-energy-budget)
- Agent status: HUMAN-GATED
- Milestone: M7
- Dependencies: platform-energy-budget.
- User-visible outcome: A versioned budget states usable battery energy, propulsion power, payload
  mass and power allowance and mission duration for the intended platform, each with its origin.
- Scope boundary: Declared figures and their basis. No flight test is required, and an `assumed`
  figure stays labelled.
- Data and artifact paths: `scenarios/`, `$DATA_DIR/selection/<selection-id>/`.
- Execution path: The owner states each figure and its source. An agent validates the declaration
  and records its hash.
- Acceptance gates: Every figure has an origin. A budget with no measured figure is accepted as a
  design comparison only, and a figure the owner cannot state leaves the budget unavailable.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### measure-sensor-power-modes

Suppressing a recorded stream saves no energy, so a policy's saving needs each sensor's real
power in every mode.

- Serves: `resource-aware-sensing` -- [Acquisition policy](../design/spec.md#77-resource-aware-acquisition-and-processing-policy)
- Agent status: BLOCKED BY HUMAN
- Milestone: M7
- Dependencies: run-mesh-trials, acquisition-policy-contract.
- User-visible outcome: Each installed sensor has measured active, standby and off power and wake
  latency and energy at the installed-system boundary.
- Scope boundary: The selected mesh on Stand C under the spec section 7.9 protocol. A rail that
  cannot be separated stays shared.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person operates the stand, and an agent runs the protocol through each mode
  transition with the meter boundary fixed.
- Acceptance gates: Raw traces reproduce each estimate with its uncertainty. A mode that cannot be
  switched or measured is `NOT_MEASURABLE`, and every policy energy claim that needs it stays
  closed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Stand-off following evaluation -- `standoff-following-evaluation`

#### define-non-disturbance-envelope

How close an observer may come to a bird, its nest or another aircraft is a judgment about a
species and a site that no software can supply.

- Serves: `standoff-following-evaluation` -- [Scenario safety](../design/spec.md#11-scenario-safety-privacy-and-data-governance)
- Agent status: HUMAN-GATED
- Milestone: M8
- Dependencies: scenario-pack-contract, following-quality-suite.
- User-visible outcome: The mission pack carries an approved non-disturbance envelope, and the
  following laws have results against it.
- Scope boundary: Minimum stand-off, closing speed, approach directions, altitude band, exclusion
  zones, following time and end conditions for each living-subject class, and a collision-risk
  envelope for drone targets. Simulation only. A field flight needs its own approvals.
- Data and artifact paths: `scenarios/packs/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: A named responsible person states each value with its basis and signs the
  approval record. An agent validates the pack and runs the mission following scenario.
- Acceptance gates: Every value has a basis and an approver. Zone positions stay restricted. With
  no approved envelope the mission pack has no following result, and that is the stated outcome.
- Documentation target: [Current implementation](current.md#areas), page `current/following.md`.

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

### Telemetry ingest -- `telemetry-ingest`

#### collect-telemetry-samples (optional)

Generated logs prove a reader only against the format as understood, and real firmware is where that
understanding fails.

- Serves: `telemetry-ingest` -- [Telemetry evaluation](../design/spec.md#187-evaluation)
- Agent status: BLOCKED BY HUMAN
- Milestone: M6
- Dependencies: flight-log-readers, board-telemetry-sources.
- User-visible outcome: Authorized real logs from named boards and firmware pass each reader, or name
  exactly where it fails.
- Scope boundary: Owned or licensed samples from any available board, restricted by default. No
  purchase is required. A sensitive device stays restricted under the measurement-only scope.
- Data and artifact paths: `$DATA_DIR/import/<source-sha256>/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: A person supplies logs and their rights, and an agent stages them and records what
  each reader covered.
- Acceptance gates: Each sample passes or yields a named reader defect. With no available log, a
  reader stays documented as checked against generated fixtures only, which is a valid negative
  result.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.
