# Object Perception and Tracking Benchmark for Mobile Observation Systems

**Product specification for `ss-track`**  
**Evidence status:** No accuracy, latency, energy, field-range, or safety result has yet been
measured.

## 1. Purpose and design principles

Build a reproducible benchmark and test-driven development (TDD) framework for interchangeable
perception and tracking modules on mobile or stationary observation systems. An **object** is an
annotated instance of a declared class, such as a bird, mammal, pedestrian, scooter or vehicle; a
**target** is the selected instance in a single-object tracking (SOT) episode. A **detection**
localizes an object in a frame; a **track** associates one instance across frames; **recognition**
assigns a class or subtype where the evidence supports it. The framework covers motion proposals,
operator-seeded SOT, later automatic detection and classification, multi-object tracking (MOT),
state estimation, multi-sensor fusion, resource-aware sensing, and advisory or autonomous subsystem
evaluation. It reports **quality, calibrated uncertainty, timing, energy, and the evidence and
exclusions behind each number**. A dashboard compares only compatible runs and makes failures
visible.

The first milestone is an **offline, computer-vision-only** test: import authorized recorded video;
replay the same operator selection to two versions of a motion-proposal/tracking module; score both
against reviewed annotations; inspect a local comparison report. Camera, telemetry, real-time and
energy experiments follow. A later, separately scheduled capability may evaluate advisory tracking or
view-centering recommendations on recorded mobile-camera video. Such footage contains only the path
chosen by its operator; it cannot reveal an unobserved viewpoint or an object's response to an
alternative action.

The benchmark is the acceptance harness for later onboard modules on Raspberry Pi 5 and other hosts,
including constrained devices. It can eventually compare autonomous drone subsystems, but offline
scores do not authorize vehicle actuation, approach to a protected subject, or operation in a public
road or park. Closed-loop and field claims have separate gates.

The repository's scope is software development and hardware support design for two outcomes:
correct benchmarks and a reference sensor mesh object-tracking implementation. Software contracts,
measurement methods, reproducible reports and test-stand requirements belong here. Hardware
selection is a separate human-assisted evidence flow: requirements come from the software, and
measured choices, rejected alternatives and limitations return to current-state documentation.
Startup strategy, commercial terms, staffing, public entry policy, dispute operations, publication
approval and launch execution belong in an owner-managed organizational to-do outside this
repository's Git control. They are not software capabilities or implementation prerequisites.
Rights, access controls and measurement validity remain software/data contracts here.

### Design rules

1. **Evidence before ranking.** Every result names its evidence lane, scenario/domain, corpus,
   labels, metric suite, module, host/camera profile, energy measurement status/boundary and
   limitations.
2. **One truth set per comparison.** Input frames, operator seeds, eligibility masks and scoring
   rules are frozen before either module runs.
3. **No score by omission.** Module drops, abstentions, late outputs and crashes on scorable input
   remain failures. Only source/ground-truth facts can make input unscorable.
4. **Small-target honesty.** Point-only or uncertain objects are not forced into precise boxes;
   exclusion and uncertainty are visible in the report.
5. **No unsafe inference.** Perception scores on operator-controlled video are conditional on that
   sensor path. Bench results do not establish field behavior, safety or non-disturbance.
6. **Replaceable modules.** Data semantics are stable across Python and C++20; transports and
   internal algorithms may differ while conformance remains testable.
7. **Quality and cost stay paired.** Accuracy, calibrated confidence, latency, deadline misses,
   throughput and measured energy are reported together for a named workload; an efficiency gain
   cannot hide a loss of quality or coverage.
8. **Causal resource decisions.** An adaptive policy uses only information available before its
   decision. Later sensor quality and ground truth may evaluate the choice but cannot retroactively
   justify it. Skipped or failed sensing remains visible in task and resource denominators.

## 2. Evidence lanes and claims

Each run belongs to exactly one lane. Results from different lanes may be displayed side by side but
are not pooled into one performance estimate.

| Lane | Inputs | Supported claims | Excluded claims |
| --- | --- | --- | --- |
| `OFFLINE_REPLAY` | Immutable video and, when available, synchronized streams from any declared sensor; reviewed labels and optional operator telemetry | Perception and sensor-subset decisions conditional on streams actually recorded and the recorded path; process-local time/throughput and measured host energy only with a declared boundary | Autonomous camera control, unrecorded sensor observations or counterfactual views, physical following, field safety, sensor power savings inferred from suppressing recorded data, glass-to-output latency without a measured capture clock |
| `SENSOR_BENCH` | Real cameras and optional other sensors, controlled object and independent reference trace, measured bench motion | Enabled-sensor pipeline behavior in the stated setup, resource and energy use, timing to the extent calibrated | Field detection distance or subject response |
| `EXTERNAL_EVENTS` | Events from another host/device matched to exact inputs and labels | Contract conformance; scored perception only when input identity and labels are verified; timing and energy only with valid measurement domains | Perception scores from unmatched telemetry; cross-host latency from unsynchronized clocks; energy inferred from uncalibrated software counters |
| `CLOSED_LOOP_SIM` (future) | Simulator or hardware-in-loop whose next observation depends on the action | Policy and subsystem performance within a stated model, support region and energy model | Real-world safety or transfer to real flight without separate evidence |

Historical operator-controlled footage is conditioned on the operator's camera path and may
underrepresent difficult losses because such footage can be missing, discarded or unusable. Each
recording declares `operator_steered`, `fixed_camera`, `autonomous_camera` or `unknown` control and,
when known, why it was retained. The report states this selection limit next to offline tracking
scores. Scenario packs define classes, annotation vocabulary, operational limits and access policy
for settings such as protected habitats, roads and laboratory benches; results from different packs
are stratified unless a predeclared common metric and sampling frame justify pooling.

## 3. Scope and delivery gates

| Gate | Required outcome | Explicit boundary |
| --- | --- | --- |
| **G0a -- pipeline validity** | Authorized development clips and invalid fixtures import; reviewed object labels and fixed seeds; oracle/null/fault and deterministic reference-tracker fixtures have expected results; two module versions produce an inspectable local report | No superiority, generalization, real-time, energy-efficiency or field-safety claim |
| **G0b -- within-corpus development decision** | Enough independent encounters, repeated same-version runs, paired metric differences, noise floor and predeclared classification rule | A decision on the development corpus only; not a public or field-performance leaderboard |
| **G1 -- controlled device evidence** | Camera hardware probe, functional baseline under normal paced Linux, stationary and motion/vibration bench, independent object trace, versioned section 7.9 hardware trial, measured capture/timing and explicit energy-measurement status, second-host event conformance; offline advisory diagnostics. PREEMPT_RT, vector/tensor paths and two-camera geometric/clock-alignment smoke tests are evaluated only when claimed | No live autonomous operation or field-range claim; validated fusion-quality claims belong to G2; an energy-efficiency claim additionally requires a calibrated meter and declared boundary |
| **G2 -- expanded perception and sensing** | Genuine MOT case with TrackEval adapter; class/subtype recognition and object state; four separately scored boundaries: sensor-set/front-end evidence, fixed-observation fusion/analysis, fixed-observation tracking, and the full installed system. Include deduplication, uncertainty calibration and resource-aware acquisition/processing; calibrated range only when independently labelled | Every claimed modality, fusion output, probability and energy trade-off needs valid labels, synchronization, resource evidence and its own metric suite. A system-level gain cannot be attributed to a component without a fixed-input component run |
| **G3 -- closed-loop research** | Action-dependent simulator or controlled hardware-in-loop with stated validity region and energy boundary | Separate domain-specific safety and operational authorization before any public-space or protected-subject field trial |

G0a is deliberately small; one positive and one negative encounter can prove the pipeline but cannot
prove improvement. G0b is not required to call G0a complete. G0 media is **development** material. A
locked test set exists only after rights, grouping, access and a test custodian are defined; no G0
report may call itself a held-out benchmark. The optional cohort comparison in
[section 16](#16-benchmark-extensions-hardware-selection-and-reference-sensor-mesh) does not change
what a G0 report may claim. Delivery milestones in the engine design implement bounded subsets of
these gates: M1 closes on G0a with two pilot encounters; M2 supplies host measurement and selection;
M3 evaluates the reference mesh at four boundaries. None claims all G1/G2 capabilities are shipped.
Thermal experiments and ranking are optional M4 work, and cross-device cases are optional M5 work.

Available laptops or small Linux boards may bootstrap development; no model is the assumed final
host. Final host and sensor configurations follow measured selection against versioned stand
requirements. Wide-field proposal plus narrow-field tracking is a hypothesis to test, not an assumed
gain. Initial cameras are rigidly fixed; vehicle mounting, power and gimbals are later engineering
work. Event, infrared and thermal cameras, audio, radar, lidar/time-of-flight, proximity, contact and
cooperative-tag sensors are candidate modalities, not assumed installed or capable at any range.
Their roles and limits are specified in section 7.6. Raspberry Pi and Rockchip devices are example
profiles whose exact revisions and supported modes must be probed, not benchmark schema assumptions.

Python is the main implementation language for corpus tooling, runner, evaluation and dashboard.
Onboard modules may begin in Python; C++20 is the preferred implementation for paths whose measured
deadline, energy or memory budgets require it. The cross-language commitment is to **event semantics
and conformance fixtures**, not identical internal code. The host profile records Linux preemption
mode, CPU instruction extensions and available compute devices from the start. Scalar, vector and
tensor implementations are explicit, separately identified variants against a portable reference
execution. A binary event format alone does not prove a latency bound.

## 4. Corpus, rights, splits and annotation

### 4.1 Corpus identity and input handling

A corpus version contains immutable source-media hashes, source rights and sensitivity, independent
encounter grouping and split, scenario-pack class taxonomy, annotation revision, canonical decode
policy, generated-case recipes and transform revisions. A metric suite is versioned separately. Each
sequence records container/codec, original and decoded dimensions, display rotation, pixel format,
frame index and PTS, timestamp quality (`measured`, `derived`, `missing`),
camera/lens/exposure/focus/FOV when known, camera-control mode, lighting/background/motion notes,
object pixel extent and measured versus estimated versus unknown range. Never infer measured range
from lens metadata alone. Class names and hierarchy live in the scenario pack; stable class IDs and
instance/track IDs are distinct. The generic contract must not require a biological species or a
drone.

A multi-sensor encounter identifies **every declared sensor stream**, including camera, audio,
radar, range, trigger/contact and platform-state streams, by source hash and modality-specific raw
format, sample rate or event schedule, capture/exposure interval, arrival time and clock domain. It
stores calibration revisions, intrinsics/extrinsics where meaningful, coordinate transforms with
uncertainty, and measured clock offset/drift with uncertainty; unknown calibration is explicit.
Audio channel geometry, radar measurement convention (for example range, azimuth and radial
velocity) and trigger/contact location and sensitivity are part of the profile, not inferred from a
device label. The sensor profile declares whether its evidence is direct object evidence, a local
contact/occupancy trigger, a cooperative-tag observation or platform/environment context; its field
of regard, sensitivity/visibility conditions, nominal latency, acquisition/standby/off/wake modes,
physical mass/mount/active-emitter requirements, and whether its range has been independently
measured. Source stream health, availability, **recorded capture-policy state** and missing-data
causes are separate immutable provenance fields. A benchmark candidate's choice to skip a sensor is
a run-specific `AcquisitionDecision`, not a source gap or scene-level absence. A common encounter
timeline is built from source event time with an audited uncertainty, while the raw event order
remains recoverable.

Stored PTS alone is `derived`, because a file cannot show that its times came from a capture clock.
`measured` also requires declared capture-clock evidence, and `missing` means at least one frame
stores no PTS. Import records these states and never fills in a timestamp.

The corpus declares a canonical decoder, its version/options and output pixel format. The canonical
decode is strict: a source is refused when decoding shows truncation or corruption that a tolerant
decoder would conceal, and a source whose completeness cannot be established says so in its record.
G0 modules consume one staged, immutable decoded-frame bundle. This makes their actual input
identical without requiring cross-platform decoders to produce identical pixels. The bundle hash
covers the source hash, decode policy, pixel layout and per-frame hashes, and no corpus or sequence
name, so two stagings of one source under one policy give one hash. The decode policy includes the
conversion to the output pixel format, and a bundle records the stored color tags that conversion
used, without inventing a tag the source lacks. Later external
modules may consume the same bundle or original packets. The latter path matches source hash,
packet/frame identity and PTS, and validates a declared sample of decoded pixels under a measured
tolerance. If exact input correspondence cannot be established, `EXTERNAL_EVENTS` reports contract
conformance only.

For fusion suites, a staged bundle preserves all raw or canonicalized streams and each event's
**availability time**. Replay releases an event only when it would have arrived, respecting the
declared clock and queue model; a policy cannot inspect a later measurement before choosing an
action. A recorded sensor-subset ablation can suppress a stream as input to the module, but cannot
invent observations that were never captured or establish physical sensor-off energy without a
measured hardware profile. The frozen task reference is constructed independently from all candidate
module outputs and remains scorable when a policy elects not to use a sensor.

Split by **independent encounter group**, not frame: related sequences from the same capture
session, site, time, operator, camera trajectory and likely object instance remain together. Manual
grouping is sufficient for the first small corpus; near-duplicate detection is added when volume
justifies it. Generated perturbations inherit the parent's split. A locked set cannot be used for
threshold tuning or module selection; accesses and re-scoring are audited. A public-space or
protected-habitat capture is never solicited merely to fill a benchmark bin.

All synchronized modalities, derived streams, simulated dropouts and sensor-subset views of one
encounter inherit the **same split and encounter ID**. Development, probability/cost calibration and
locked-test material are disjoint by encounter; a separate calibration subset is required before a
calibrated probability or adaptive-policy claim. Calibration and policy thresholds are frozen before
locked evaluation.

A corpus version declares this structure directly. An independent encounter group names one split,
`development`, `calibration` or `locked`, and holds encounters, and an encounter holds its streams. A
stream is one sensor's frames of one encounter, taken from one source and frame window, and its
`stream_id` is unique in the corpus. A source belongs to one group, because groups that share a
recording are not independent, and a source frame belongs to one stream, because a frame counted
twice distorts anything aggregated by encounter. Sharing a source is detected by byte hash, and a
remux is detected after staging: two groups holding a run of identical decoded frames are refused,
because a different container does not make different evidence. A uniform or repeated frame shared by
independent clips is not such a run. A re-encoded copy stays a different source until near-duplicate
detection exists. Declaring `locked` records membership only: it creates no locked test and grants no
held-out claim. A development scenario that names a locked stream is refused, and a locked evaluation
needs the section 15 custodian and access policy, with each read recorded.

A corpus version may name the version it supersedes. Material already evaluated in one split has been
seen, so a source that a new version places in another split is refused, as is one moved to another
group. New sources are accepted, and the build reports what was added, removed and kept. This compares
only versions linked by that declaration, so a version that names no predecessor says so in its
result.

Staging ends with one sealed frame-set record that names every stream and generated-case bundle hash
of a corpus version and the source records they rest on. A scenario pins that one hash rather than a
list of bundles, and a bundle no frame set names is not part of the corpus.

A corpus also declares its **scenario rights**: the widest sharing it intends and the highest
sensitivity it accepts. A build that asks more of any source than its recorded rights allow is
refused and names each conflict. It compares only these two ordered facts; holder, basis and
retention stay recorded terms. A public source in a restricted corpus stays recorded as public while
the corpus remains restricted. A corpus version states the rights of the source records it was built
from, so a source re-imported under other terms needs a new corpus version.

A recording also declares when its retention ends, or that it has no end, and whether derived frames
are permitted. A source past its retention date is refused at build, staging and verification, and a
generated case of a source that forbids derived frames is a rights conflict. Refusal does not delete
anything: removing expired material stays an operator action. `corpus verify` re-reads the source
records it pins, so a verified corpus is one whose rights still hold, not only one whose frames are
intact.

### 4.2 Annotation contract

For each selected target instance and frame, the status is exactly one of `visible`,
`partially_occluded`, `fully_occluded`, `out_of_view`, `absent` or `unknown`. `out_of_view` means
that instance is known to have left the recorded field of view; `absent` is confirmed absence in a
negative interval. The protocol uses a box over the **visible extent**; an optional amodal estimate
is a distinct field and is never substituted silently. Geometry is `box`, `point_only` or
`unlocalizable`. Every box/point carries a localization uncertainty estimate and annotator ID;
point-only labels also carry a reviewed maximum plausible target extent if they are to contribute to
the primary localization score. An uncertainty too large for meaningful identity resolution is
marked `unlocalizable`.

All visible objects in the G0 scoring classes receive an instance ID or an explicit
`identity_ambiguous` label, so a track on another object can be distinguished from a correct target
track. Objects outside the scoring class set are marked `distractor`, `ignore_region` or `unknown`
under a versioned scenario policy; these terms are not silently equated. Motion-event onset, onset
uncertainty, target visibility, camera motion (`static`, `translation_or_pan`, `shake`, `unknown`),
selection quality and re-entry are recorded. Semantic states such as walking, riding, gliding or
stationary use a later scenario-specific vocabulary; image-plane displacement alone does not
establish physical state.

The operator selection stores original click/box coordinates, source frame/time, intended target if
adjudicated, seed-quality category and any correction. Competing modules receive exactly the same
selection. A fixed, versioned set of perturbed spatial/temporal seeds may be added as a robustness
view; the real operator seed remains primary. Two annotators review the entire small G0 material,
resolving disagreements with a recorded rationale or retaining `unknown`. Larger corpora may use a
predeclared review sample plus all difficult cases. Ground truth, episode eligibility and exclusion
masks are frozen and hashed **before** module execution.

Label coordinates use the stored orientation that modules receive. Display rotation is a recorded
fact, so a tool that shows a rotated view maps coordinates back before a label is validated, and a
label that declares any other orientation is refused.

A generated case takes its labels from its parent's frozen revision through the stored label
transform, as a hashed revision of its own that nobody edits by hand. Frozen labels also check the
rectangle a case rests on: a plate frame that shows a target inside that rectangle is refused, and a
target the rectangle does not cover stays `unknown` rather than becoming `absent`.

Fusion labels distinguish the object/event's **scene-level identity** from visibility or
detectability in each sensor. A camera may see an object while a microphone has no attributable
sound, a PIR sensor may have no thermal contrast, and a ground-contact sensor cannot observe a
freely flying object. Annotate per-modality field-of-regard and opportunity,
visibility/detectability and negative intervals, cross-sensor identity only when independently
adjudicated, and reference geometry/range/velocity only when a separate valid reference supports it.
An oracle union of independently labelled sensor opportunities is an **observability upper bound**,
not a fused-system score. A single microphone is not assumed to yield direction or range; a radar
return is not a class label; a cooperative tag detects only tagged subjects. Ambiguous association,
correlated evidence and uncertain reference identity remain explicit rather than becoming confident
fused truth.

### 4.3 Deterministic cases and negative evidence

Initial generated fixtures cover target absence, moving background (for example vegetation, crowds
or traffic), camera shake, blur, dropped/duplicated frames and short occlusion. Further cases
(compression, variable frame rate, multiple similar objects, out-of-view/re-entry, sensor loss)
enter with their owning capability. Each case stores parent sequence, transform, seed and label
transform. Geometry-changing cases update geometry/calibration or invalidate dependent labels.
Synthetic cases test failure mechanisms and are never counted as independent field encounters.

A corpus version declares each generated case under its parent stream, so a case states no split,
encounter or group: it inherits all three and adds nothing to any group, encounter or stream count.
It is staged as a frame bundle derived from its parent's staged frames, and modules read it as they
read a stream. Its hash covers the parent bundle, transform revision, seed, parameters, label
transform and frames, and no corpus or case name, so one recipe over one parent gives identical
bytes. A transform that would produce other bytes takes a new revision, and a stored case of another
revision is refused rather than regenerated. A case that changes no frame of its parent is refused,
because it would test nothing while claiming to.

Labels follow pixels. A case keeps each frame's source index, so a shifted frame translates its
labels, a removed frame takes no label, and a repeated frame takes the labels of the frame it shows.
A repeated frame keeps its own presentation time, which stops being a measured capture time, so such
a case is at best `derived`. Absence, occlusion and moving-background cases act on a declared
rectangle. That rectangle is the operator's claim: a label inside it takes the case's status, and a
label that only overlaps it loses its geometry rather than keeping a box that may be wrong.

A case does not claim realism and does not chain from another case. A section 4.1 source term decides
whether derived frames may exist at all.

With frozen labels, a case can follow a target's own track instead of one rectangle: an occluder that
crosses the target, a removal that follows it, a similar object beside it, and out-of-view and
re-entry intervals. These cases need no operator rectangle, so they carry no such claim.

A recipe may declare a graded list of one parameter, which expands to one case per level. The local
report then shows each module's quality against that severity, so a comparison shows where a module
degrades, not only whether it does. The curve is one parameter on one encounter set. It is a
diagnostic, it enters no composite score, and it is never field evidence.

Fusion fixtures add controlled timestamp skew, jitter, late and out-of-order packets, complete or
intermittent modality loss, degraded/noisy measurements, calibration perturbation, shared artifacts,
duplicate source events, contradictory observations and sensor-health misreports. These act on a
whole encounter, because a fusion failure is a relation between streams. A generated
perturbation declares whether the independent reference remains valid; any altered physical geometry
or time relation updates the dependent calibration and labels or makes that metric `NOT_SCOREABLE`.
Real and simulated failures remain separate report slices.

## 5. Module contract, execution and fault semantics

The canonical contract is semantic and versioned. `.proto` files define event types from the start.
In G0, the transport is a staged frame bundle plus one protobuf-JSON-mapped JSON Lines `FrameResult`
per frame; the file format is human-inspectable and validated against the schema. Binary protobuf
framing is introduced when a first C++20 module or second host needs it, and must pass the same
conformance fixtures. Frame delivery, wire events, analytics storage and clock synchronization are
independent versioned concerns. No video frame is required to pass through protobuf.

Required record families are `RunManifest`, `FrameRef`, `TargetSelection`, `FrameResult`,
`Detection`, `TrackState`, `AdvisoryAction`, `SensorSample`, `ResourceSample`, `PowerSample`,
`RunEvent`, and `ValidationResult`. G1 hardware trials add `HardwareTrial`, `InstrumentRecord` and
`CalibrationRecord` with the section 7.9 evidence and uncertainty fields. Later G2 suites add
`SensorObservation`, `FusionEpoch`, `FusionResult`, `FusedObservation`, `TrackerEpoch`,
`TrackerResult`, `AcquisitionDecision` and `BudgetState` without changing G0 `FrameResult`
semantics. `RunManifest` identifies corpus/split/annotation/mask, scenario pack and class map,
metric suite, module binary/configuration, schema, decoder, host, kernel/scheduler profile, active
compute variant and evaluator revisions. A compute variant identifies its scalar or vector kernel
and ISA, or its tensor graph/model, precision, backend and device, as applicable; the detailed
provenance contract is in section 7. `FrameRef` identifies stream, source-media hash, zero-based frame
index, the frame whose pixels it shows, PTS, decoded dimensions/pixel format, transform, time evidence
and staged-bundle access.
`Detection` carries class ID, confidence and geometry; `TrackState` carries instance/track ID,
presence confidence and geometry. `FrameResult` acknowledges exactly one input frame and contains
zero or more outputs; an empty valid result is different from a missing result. `PowerSample`
declares instrument, measurement boundary, synchronized voltage/current or measured watts,
timestamp/clock domain, calibration, sample-quality flags and uncertainty; derived joules retain the
integration method and exact interval. `ResourceSample` declares counter scope, unit, clock, source
and validity or multiplexing status. Every event has a stable ID and source frame or explicit
unframed interval. Retried IDs are idempotent.

`SensorObservation` references staged raw data or a derived measurement and identifies its modality,
evidence role, stream, calibration, capture interval, arrival time, clock uncertainty, coordinate
frame, units, quality flags, field-of-regard/coverage state, provenance/correlation group and source
event ID. Its typed measurement may be a box/point, bearing, range, Doppler/radial velocity,
acoustic event/direction, thermal/event-camera activity, local trigger/contact or platform-state
sample; unavailable dimensions remain absent. An available sensor's `no_detection` **inside a valid
field of regard** is distinct from `out_of_view`, a candidate policy's `disabled_by_policy`, and
source `missing`, `stale` or `invalid`; none alone proves scene-level absence. A scheduled
`FusionEpoch` names its reference time, permitted source-time window, **observation availability
cutoff** `t_fuse` and output deadline. An `AcquisitionDecision` is made at `t_decide <= t_fuse` using
only evidence then available. Exactly one `FusionResult` acknowledges each scheduled epoch,
including a valid empty/skip result; a missing or late result is scored under the fixed task
schedule. Each fused record lists every contributing source ID **once**, source age/uncertainty,
association and correlation group, accepted/rejected source reasons, output frame, state/geometry
estimate, and the specific uncertainty type it reports. A class posterior, detection-correctness
probability, track-existence probability, localization covariance and clock uncertainty are distinct
quantities and must not share an untyped `confidence` field. Reuse of the same correlated visual or
derived evidence cannot be counted as independent support. Raw video, event-camera, audio, radar and
other high-rate samples remain out of protobuf as versioned bundle data.

`RunManifest` also declares exactly one G2 `evaluation_boundary`: `SENSOR_SET_FRONT_END`,
`FIXED_OBSERVATION_FUSION`, `FIXED_OBSERVATION_TRACKER` or `FULL_INSTALLED_SYSTEM`. It pins the
allowed input types, input and upstream-artifact hashes, stage producer/configuration, schedule and
output deadline. A fixed-input module cannot read raw streams, labels or future observations outside
its declared boundary. A tracker run receives a versioned `TrackerEpoch` schedule with reference
time, permitted observation IDs, availability cutoff, optional identical seed and output deadline.
It emits exactly one `TrackerResult` acknowledgment per epoch, containing zero or more `TrackState`
records or explicit `lost`/abstain; each state distinguishes measured update from prediction-only
continuation and carries source lineage. This does not change G0 `FrameResult`. A monolithic module
that cannot expose a fixed-input component boundary can be scored as a full pipeline, but cannot
claim that its fusion or tracking component alone improved.

`AcquisitionDecision` is emitted **before** the selected sensor or expensive processing action and
records the available context, feasible actions, predicted task gain or loss, estimated
latency/energy/risk, current budget, chosen action and reason. `BudgetState` records energy-window
consumption and hard limits. Later quality features, accepted measurements and actual resource use
are separate post-action events. When a source is disabled, fails, or returns late, the runner still
keeps the same frozen task denominator and records the reason. A fusion module may abstain or
request operator review, but cannot declare a difficult epoch unscorable.

Canonical boxes are top-left `x,y,width,height` in pixels, with half-open extents, in a named raw or
transformed image space. A point has pixel coordinates and uncertainty.
Resizing/cropping/undistortion names a versioned transform and inverse or explicitly declares
non-invertibility. Sensor values use SI units and named coordinate frames. Cross-camera target
identity is never inferred from timestamps alone.

Sensor observations may have incompatible geometry or no spatial geometry at all. A bearing-only,
class-only, local trigger or tag observation must not be converted to a 3D position or shared
instance ID without a declared association model and sufficient calibrated geometry. Platform
IMU/GNSS, light, wind or motor-state samples may correct ego-motion, observability and noise models;
they are not independent object detections. Fusion adapters validate transform composition, time
gates, measurement covariance units and positive semidefiniteness where covariance is claimed. A
calibrated posterior is tied to a named event and ground-truth definition, not inferred from an
arbitrary model score.

G0 uses **lockstep replay**: the runner stages the canonical decoded frames, sends or exposes every
frame in a fixed order, and waits for each `FrameResult`. A per-frame wall-clock timeout is a
liveness guard, not a measured real-time deadline. G0 modules may return an explicit empty proposal
set or `lost` state, but they may not silently skip frames. Subprocess/network lifecycle messages
(`HELLO`, `CONFIG`, `FRAME`, `EVENT`, `FLUSH`, `DONE`, `ERROR`) and bounded queues enter at G1. In
paced G1 runs, module-side drops, late answers, queue overflow and backpressure are counted and
scored against the fixed input schedule. A paced run releases each frame's bytes to the module at
its scheduled time, and no future frame is readable by the module, so offline preprocessing cannot
pass as streaming behavior. A third-party module runs in a pinned container with no network, no
label path and declared resource limits.

The runner owns validity, not the module. `RUNNER_INVALID` (for example wrong source hash, broken
bundle, corrupt precomputed mask) invalidates the complete comparison. A module crash, timeout,
malformed output, unsupported schema after an accepted handshake, or premature stop is
`MODULE_FAULT`: the run remains reportable, and all remaining scorable input receives missing-output
failures. `UNSUPPORTED` may be returned before a run begins for an unavailable camera/mode/contract.
`NOT_SCOREABLE` arises only from frozen source/ground-truth limitations. A module cannot declare its
own difficult frames ineligible. Every report shows counts and elapsed exposure for these statuses.

A corpus refusal that shows broken or undeclared input, such as a corrupted frame, a tampered record,
an unstaged bundle or a bundle conflict, is `RUNNER_INVALID` and never a module fault. A frame that a
generated case removed never reaches a module: it is not scheduled, takes no `FrameResult` and enters
no denominator, and the report shows its count and exposure as undelivered. This differs from a
module-side drop of a delivered frame, which stays a miss. A paced run verifies frames before their
release time, or reports verification as runner time, so hashing cannot pass as module latency.

Time fields distinguish media PTS, camera/driver buffer time, receive time, processing start/end,
event publication and display. Every clock value declares its domain, source and uncertainty;
offset/drift calibration is recorded when clocks are compared. Offline PTS is media time, not
capture time. A cross-host or glass-to-output latency is `NOT_MEASURABLE` without adequate alignment
and a physical reference. The [Linux V4L2 buffer
documentation](https://docs.kernel.org/userspace-api/media/v4l/buffer.html) notes that the driver
defines the timestamp source within the frame; a UVC buffer timestamp is not automatically a
mid-exposure timestamp.

Schema evolution permits additive fields within a major version, never field-number reuse or changed
units/enum meanings. Golden fixtures cover absent optional fields, unknown fields, old/new readers,
malformed payloads, coordinates, timestamps, class/track identity, power units and Python/C++ round
trips when C++ support is added. Every run records schema and transport revisions.

Fusion conformance fixtures additionally cover asynchronous event order, delayed duplicates and
idempotency, missing-versus-negative-versus-out-of-view observations, clock-domain mismatch, stale
calibration, impossible covariance, source-provenance cycles, correlated-source reuse, output after
an epoch deadline and policy decisions that refer to future data. Fixed-input fusion and tracker
fixtures also check that a candidate cannot access labels, raw streams outside its boundary or
observations after the cutoff. A malformed fusion or tracker event is a module fault under the same
accounting rules. Source data that cannot meet a declared alignment tolerance makes that fusion
profile `UNSUPPORTED` before the run. An actual capture/clock failure during a run is recorded as
source `missing`/`invalid`; a candidate's deliberate skip is `disabled_by_policy`. Both retain the
fixed task denominator and may cause a miss or uncertain output. Only a **frozen reference
insufficiency** can make that task epoch `NOT_SCOREABLE`; no source is silently aligned or excluded
after the run begins.

## 6. Metric-suite validity and primary G0 metrics

Each metric has a versioned definition with thresholds, matching order, exposure weights,
denominators, missing-data policy, confidence interval method and known limits. The dashboard reads
these outputs; it never recomputes them. A score is `VALID`, `NOT_SCOREABLE`, `UNSUPPORTED`,
`NOT_MEASURABLE` for a timing/energy claim lacking required instrumentation, or part of a
`RUNNER_INVALID` comparison. A `VALID` zero and an unavailable score are visibly different.

The frozen annotation mask defines scorable input **before** modules run. On scorable input, an
empty/lost/abstaining `FrameResult`, a missing result, a late result under a paced deadline, or a
module fault is a miss with a reason. An unscorable source interval is never inferred from module
behavior. All reports include annotated time, scorable time, point-only time,
uncertain/occluded/out-of-view time, media gaps, module misses and fault time, by encounter and in
aggregate.

### 6.1 Operator-selected tracking: `sot-v2-dev`

An episode begins at a fixed operator selection. The selected object instance is the target even if
the seed is imprecise; seed quality is reported separately. A frame is localization-scorable when
the target is `visible` or `partially_occluded`, its identity is unambiguous and reviewed
geometry/uncertainty meets the annotation protocol. `fully_occluded`, `out_of_view`, `absent` and
`unknown` frames remain in the corpus but are not localization denominators; absence and re-entry
are evaluated separately. A partially occluded box describes **visible extent**. This SOT suite is
class-agnostic; class recognition is scored separately.

The development-suite hit rule is deterministic and may be revised **only by a new suite version
before locked evaluation**. Let `c_gt` and `c_pred` be the ground-truth and predicted centers, `s_gt
= sqrt(w_gt * h_gt)` the ground-truth box scale, and `u` the reviewed localization uncertainty
radius. A box is a hit when both `distance(c_pred, c_gt) <= max(0.5 * s_gt, 2 * u, 2 px)` and `0.5
<= s_pred / s_gt <= 2`, where `s_pred = sqrt(w_pred * h_pred)`. A point-only label is a hit when
`distance(c_pred, c_gt) <= max(2 * u, 2 px)` and its larger predicted-box dimension is at most twice
the reviewed maximum plausible object dimension; a point prediction has no size condition. If a
trustworthy uncertainty or extent cannot be annotated, that frame contributes to a
**point-localization diagnostic**, not the primary lock score. A prediction on a clearly annotated
other instance is an identity failure even if its position passes the distance tolerance.
Identity-ambiguous cases are frozen as unscorable and their exposure is reported. These thresholds
are engineering defaults for G0 development, not evidence of task or control adequacy.

For each scorable frame `i`, define a media-time weight `q_i = min(t_(i+1) - t_i, 2m)` from PTS,
where `t_(i+1)` is the **next decoded frame's** PTS, including when that next frame is unscorable,
and `m` is the median positive interval over all decoded frames in the episode; the final decoded
frame uses `m`. A larger source gap is recorded separately rather than giving one frame unlimited
weight. Missing, duplicate or non-increasing PTS makes time-based scores unavailable until
corrected. The **primary G0 tracking measure** for episode `j` is observable lock coverage `C_j =
sum_i(q_i * hit_i) / sum_i(q_i)`, with the same fixed scorable frames in both sums. An episode with
no scorable frame is `NOT_SCOREABLE`, never a numeric zero. Average scorable episode values within
each encounter, then compare encounters; no long clip silently dominates. The report shows box and
point contributions separately and the fraction of all annotated target time that was scorable. A
module cannot increase `C_j` by dropping a difficult frame because its weight remains in the
denominator.

The required 3 s and 10 s view is a **secondary, conditional horizon-retention** measure. A failure
run becomes sustained when misses continue for at least 0.20 s of media time; the failure time is
the first miss in that run. A reinitialization counts as loss at its time. Retention at horizon `H =
3 s` or `H = 10 s` is the fraction with no sustained failure through `H`, among episodes whose
ground truth remains localization-scorable through `H` and whose media extends that far. Show the
numerator, denominator and every exclusion reason; never describe it as retention for all
encounters. A miss shorter than 0.20 s still lowers `C_j`. A null module has `C_j = 0`; its time to
sustained loss is the start of an episode long enough to establish the 0.20 s gap. An episode ending
before a possible gap can be resolved is insufficient for that horizon, not a success.

Also report time to first sustained loss with the number of episodes still observable at each time,
IoU success AUC on box frames, center-error distribution, per-size/seed/camera-motion slices, false
continuation when the target is not visible, and re-entry/reacquisition in a separate suite. A
Kaplan-Meier curve may be exploratory only: target exit and clip end in operator-steered video can
be informative censoring, so it is **not** the primary G0 ranking or a field-survival estimate.
Scores against each annotator's labels form an annotation-sensitivity band.

### 6.2 Motion proposals: `motion-v1-dev`

G0 measures whether a CV module places an operator-selectable proposal on an in-scope object
exhibiting an annotatable **image-plane movement cue relative to its local background**. This is
motion-proposal evaluation, not general object detection or a claim about physical activity state;
no class recognition is required. An eligible ground-truth event has a reviewed instance ID and
scenario class, first annotator-detectable onset interval, duration, geometry/uncertainty and
camera-motion label. Onset uncertainty is retained rather than collapsed to a single exact time.

Each frame may contain zero or more scored proposals with center/box and confidence. At each
declared confidence threshold, form candidate proposal-ground-truth edges that pass the tracking
spatial tolerance and size bound when geometry supports them. Choose a one-to-one assignment with
maximum cardinality, then minimum summed normalized center error; break remaining ties by higher
proposal confidence and stable proposal/object IDs. This matching order is part of the metric-suite
version. The earliest matched proposal within 1.0 s of the onset interval is a detected event in the
**development** suite. Report event recall at that window, detection-delay interval/distribution and
a confidence operating curve. Recall for all in-scope objects and for the later operator-selected
target are separate views. A proposal on another annotated in-scope object is a valid proposal, not
a selected-target hit. Proposals unmatched to an in-scope object, including duplicates after
one-to-one matching, count as operator-burden proposals; report them separately for confirmed
object-absent sequences and background exposure in object-present sequences, both per minute of
valid media time. Distractor and ignore-region policy is fixed by the scenario pack; unknown regions
are counted as unscored exposure. Slice by class, camera motion, object pixel size and image speed.
The 1.0 s window is a G0 development default; the operator-relevant window must be set before locked
evaluation.

### 6.3 Comparisons and decision status

G0a reports scores and failure examples but makes no improvement claim. G0b needs at least **10
independent encounter groups** as an initial internal decision gate; this is an engineering minimum,
not a power calculation or a public-performance sample size. Run the same version/configuration at
least three times to measure repeatability. Define the noise floor for a metric as the largest
absolute encounter-aggregated difference among these same-version rerun pairs. Compare A and B on
paired encounter values and report a 95% encounter-cluster bootstrap interval, the number of
encounters, the number of seeds and annotation sensitivity. No single clip may be treated as
independent frames for uncertainty.

The predeclared G0b status is `improved_on_development_corpus` only when the entire paired interval
for a metric is above both zero and the measured noise floor; `regressed_on_development_corpus` is
symmetric. If the interval overlaps either bound, report `inconclusive`. If the encounter count,
annotation or timing validity is inadequate, report `insufficient_data`. Failure to reject a
difference is **not** equivalence. Tracking, motion proposals, absence behavior, latency and energy
have separate statuses; there is no automatic overall winner. The one exception is the predeclared
rank inside a matched cohort in [section 16.1](#161-cohort-ranking), which sets its own
sample rule. A later held-out or field claim requires a new sample-size plan and locked protocol.

Scores are sliced by object class and pixel size (including a small-object view), box versus point
geometry, seed quality, camera control and motion, background, illumination and independently
measured range if available. The dashboard never ranks systems by closest approach. Domain-specific
constraints and costs are shown without mixing unlike classes or operating environments.

### 6.4 Later metric suites

| Task | Required measures and preconditions |
| --- | --- |
| Target absence and re-entry | False confident continuation per not-visible second, correct abstention, re-detection delay and identity continuity; do not merge into G0 visible-frame coverage |
| Object activity/state | Per-state precision/recall and transition delay against a scenario-defined vocabulary (for example `walking`, `riding`, `gliding`, `stationary`, `unknown`); never infer physical state from raw image displacement alone |
| Object detection and recognition | Class-wise precision/recall, calibration and abstention/risk-coverage; fine-grained subtype scoring only on expert-labelled, visually identifiable material |
| MOT | HOTA with DetA/AssA/LocA through pinned TrackEval; IDF1/MOTA as diagnostics, with class/ignore policy and tiny-target slices |
| Multi-sensor motion and tracking | Motion-event recall/delay and false proposals; SOT lock and MOT output metrics; compare each sensor alone with fused output on the same encounter; report time/geometry validity and source coverage |
| Cross-sensor deduplication | Duplicate-output, missed-association and false-merge rates against reviewed event identity, with source-event provenance and time uncertainty |
| Calibrated uncertainty | Detection-correctness and track-existence reliability, proper probability scores, conditional location-region coverage and sharpness where reference geometry exists; class/posterior calibration and risk-coverage are separate |
| Adaptive sensing and processing | Task quality, source availability/activation, abstention, deadline misses, measured sensor-plus-compute energy and peak/rolling-budget violations at each declared operating point |
| Non-camera sensor evidence | Modality-specific event detection, occupancy/contact, bearing, localization, range or velocity only when that sensor's geometry, coverage and independent labels support the quantity; no implied cross-modal identity or object class |
| Stereo/range | Error, coverage and uncertainty calibration against an independent distance reference; do not score uncalibrated or unsynchronized pairs |
| Advisory policy | Agreement with recorded operator actions, conditional image-plane forecast error, rule violations and abstentions as **separate diagnostics**, never a fixed-video following-success score |
| Closed-loop subsystem (G3) | Task completion and constraint violations under action-dependent observations, with deadline misses and declared compute/sensor/vehicle joules per trial; report failure and abort rates, never infer field transfer from simulation alone |

### 6.5 Fusion probability and resource-policy evaluation

Every probability names its event, conditioning information, reference outcome and calibration
population. A detector's raw score is not automatically a probability of object presence; class
probability, detection correctness after spatial matching, track existence and localization
uncertainty are scored separately. Report reliability diagrams and Brier score or negative
log-likelihood for defined binary/class outcomes, with expected calibration error only as a
diagnostic; report coverage **with** the width/area of prediction regions when a geometric posterior
and independent reference are available. Risk-coverage curves show errors together with the
proportion of scheduled inputs that received a usable answer. A high-confidence wrong association,
duplicate track or confident output on absence is explicitly counted. Optional probabilistic MOT
scoring requires a fully specified multi-object posterior; TrackEval's HOTA remains the canonical
deterministic MOT output score.

Detection probability `P_D` is empirical event recall over the predeclared eligible events at a
**fixed false-proposal burden or false-alarm operating point**, stratified by class, object
extent/range when measured, lighting, motion and modality condition. It is not a model's per-output
confidence. Report numerator, denominator, uncertainty interval and the operating threshold; a small
number of events yields an `insufficient_data` **claim status**, not a precise probability. False
negatives from sensor skipping, classifier abstention and missed deadlines remain in the fixed task
denominator. Conditional accuracy among emitted results is shown only with coverage, and no metric
rewards a policy for avoiding hard inputs.

For every fusion/policy comparison, replay the same synchronized encounters and compare each
available single-sensor path, fixed always-on fusion, fixed-rate/periodic and random skip, and
declared time-shared mixtures across the feasible modes. Offline input-subset ablations produce
paired **quality and process-latency** comparisons; their physical sensor-energy status is
`NOT_MEASURABLE` without a measured on/off profile. Only a controlled trial with a calibrated, fixed
installed-system boundary and real sensor modes may form a **measured quality-energy-latency
frontier** or support an energy-gain claim. Then report adaptive-policy quality at matched
complete-system energy and deadline constraints, or energy at matched quality; use paired
encounter-level differences and predeclared uncertainty/margins. A task gain is claimed only at the
stated false-alarm/coverage condition and without a hidden degradation in calibration,
high-confidence error, availability or deadline performance. Do not transplant a numeric gain or
confidence threshold from a navigation study into this benchmark.

### 6.6 Four independent G2 evaluation boundaries

G2 has four separately versioned suites with **fixed task exposure and independent scene truth**. An
improvement at one boundary is attributed only to the stage that was allowed to change. A sensor
family can be registered through the generic contract, but a score for "all sensors" means **all
installed, simultaneously feasible and declared sensors in that scenario**, not every conceivable
modality. Predeclare the feasible single-sensor, paired, all-installed and leave-one-out sets; use a
justified fractional design if exhaustive subsets are impractical. Do not assume that combining
sensors must improve quality. Every comparison reports the intersection of genuinely comparable
opportunities and the full fixed task denominator so that lack of a sensor is not hidden.

| Boundary | Frozen input and candidate output | Primary evidence and metrics | Attribution and cost limit |
| --- | --- | --- | --- |
| `SENSOR_SET_FRONT_END` | Raw streams, sensor opportunity labels and a fixed, versioned reference late-fusion/association rule; candidate sensor adapters/front ends emit typed `SensorObservation` events. Run each feasible declared subset through the **same** reference rule | Per-sensor event recall/delay, false alarms per observed time/area, localization/range/angle error and calibration where valid; actual fused proposal recall at fixed false-alarm burden, duplicate/false-merge rates, complementary coverage, all-installed and leave-one-out marginal effects. Show the label-derived oracle union only as an observability ceiling | Measures front-end and sensor-set evidence under one reference rule, not a candidate fusion algorithm. Report acquisition and stage-local compute cost only where separately metered; a shared rail cannot be assigned to a sensor |
| `FIXED_OBSERVATION_FUSION` | Immutable, hashed `SensorObservation` bundle, field-of-regard/availability states, calibration, event order and epoch schedule; candidate emits `FusionResult`/`FusedObservation` | Association precision/recall, missed links, false merges, deduplication, existence/class probability scores, abstention/coverage, state or geometry error/calibration when reference permits, output latency and faults. Compare to the pinned late-fusion baseline and single-source inputs | Isolates the fusion/analysis module. A changed front end or calibration creates a new bundle/cohort; score only fusion-stage compute cost, with energy `NOT_MEASURABLE` if no separate boundary exists |
| `FIXED_OBSERVATION_TRACKER` | Immutable, hashed single-source or fused observation stream, optional identical operator seed and `TrackerEpoch` schedule; candidate emits `TrackerResult`/`TrackState` or explicit lost/abstain | G0-compatible SOT lock and re-entry measures or genuine MOT HOTA/DetA/AssA/LocA, ID switches and fragmentation; state forecast error, existence calibration, coverage, latency and deadline misses when labels allow | Isolates track maintenance, association over time and prediction. Candidates that inspect pixels or produce their own detections are a larger pipeline unless the identical additional input is frozen and declared. Report only tracker-stage compute cost |
| `FULL_INSTALLED_SYSTEM` | Live/recorded raw capture through adapters, fusion, tracker, recognition and acquisition policy on a named installed configuration; candidate emits final tracks/events and resource evidence | End-to-end task quality at fixed false-alarm burden, calibrated uncertainty, sensor availability, glass-to-output time when measured, deadline misses, peak/rolling limits and quality-latency-energy frontier. Include stationary, controlled motion/vibration, outage and recovery slices | Only boundary that can support a **complete-system** joule or physical sensor on/off saving claim with a calibrated fixed meter boundary. This score alone cannot identify which internal stage caused a gain |

The first three boundaries use **identical upstream bytes, labels and release/deadline schedule**
within their cohort; `FULL_INSTALLED_SYSTEM` may compare predeclared modality sets or policies at
identical encounter opportunities and an identical installed-system meter boundary. A precomputed
event bundle is re-versioned and rehashed after any upstream change. Missing acknowledgments, late
results and deliberate skips remain in each boundary's fixed denominator. A raw-input monolith may
have a valid full-system score without any component score. TrackEval applies to MOT output at the
tracker and system boundaries; it does not measure sensor complementarity, fusion probability or
joules.

## 7. Hardware profiles, sensor fusion, compute optimization, real-time behavior and energy

### 7.1 Probe and adaptive launch

`ss-track hardware-probe` enumerates the actual CPU model/architecture/cores and OS-enabled user-space
instruction features, RAM, OS/kernel and preemption configuration, scheduler/affinity/`mlockall`
availability, frequency governor, **every installed sensor's** identity/interface/supported mode and
active/standby/off/wake behavior, shared USB/CSI/network topology and bandwidth, available compute
devices and runtimes, storage throughput, calibration files, and thermal/throttling indicators. For
a physical modality it verifies its declared evidence role, field of regard, clock/capture quality,
calibration validity, data rate and available power-control state; mere discovery does not imply
that it can observe a declared object. It tests **simultaneous** requested sensor modes for
sustained frames/samples, timestamp quality, bus contention, memory and CPU/accelerator load;
separate successful single-sensor probes do not establish a joint mode. The protocol predeclares a
sustained trial duration, maximum frame/event-loss rate, time-alignment error and thermal state for
a `SUPPORTED` joint profile under section 7.9. For a requested tensor graph it also probes supported
operations, shapes, layouts, precision, device memory, model compilation and execution of
representative inputs; merely listing a GPU/NPU or a runtime provider is insufficient. It runs
bounded capability trials and returns structured `SUPPORTED`, `UNSUPPORTED` or `MEASURE_REQUIRED`
reasons for each module/sensor/compute configuration. A data sheet or compiler target flag alone
does not certify a sustainable mode. The launch plan records enabled sensors and acquisition modes,
resolution/sample rate, pixel format, queue capacity, thread count, batch size, memory/bandwidth
limits, selected compute variant, actual graph partition and any declared fallback. Its selection
policy uses only host capabilities, development-set calibration and predeclared workload
constraints, never locked-test labels or scores. It never enables an unsupported instruction path.
Raspberry Pi 5 and other devices are probed independently; a missing accelerator follows a tested
portable CPU path or yields `UNSUPPORTED` before the run.

### 7.2 Scalar and vector CPU module paths

Hand-written C++20 image, statistics and association kernels have a portable scalar reference
implementation and golden input/output fixtures. Scalar optimization candidates include fewer
full-frame passes, channel-selective processing, integral images for window statistics, precomputed
scale factors, bounded buffers and cache-aware layouts. A change to the algorithm or its output
semantics is a named module/configuration variant and must pass task-level quality evaluation; a
faster kernel is not automatically a quality-equivalent replacement. An optimization is retained for
a named host/workload only after correctness and measured latency, throughput, memory or energy
evidence.

CPU vector paths are optional, isolated build/runtime variants. **Arm Advanced SIMD/Neon** is the
first candidate for suitable Raspberry Pi 5 pixel/statistics kernels. Other possible Arm paths
include dot-product, FP16/BF16, I8MM and **SVE/SVE2**. SVE code must be vector-length agnostic,
handle tail lanes correctly and record the effective thread vector length; no Raspberry Pi 5 SVE
support is assumed. Other host families may use x86 SSE/AVX2/AVX-512 or RISC-V Vector where
available. Dispatch requires the executable's target and the operating system's usable feature state
to agree: Arm `AT_HWCAP`/`AT_HWCAP2`, x86 CPUID **and** enabled extended state for AVX-family paths,
or the appropriate Linux RISC-V capability probe. A separately compiled path and tested scalar
fallback prevent an unsupported instruction from executing. The portable binary must not require an
optional extension merely to start. Compiler auto-vectorization, library kernels and intrinsics are
alternatives to measure, not performance claims.

Record compiler/version/flags, binary hash, relevant library builds, requested and actual dispatch
path, feature probe, thread placement and vector length where applicable. Kernel fixtures cover odd
widths/strides, unaligned buffers, borders/crops, tail lanes, small/empty regions, multiple pixel
formats, integer overflow/saturation and floating-point tolerances. Compare full detection/tracking
output and quality as well as kernel values against the scalar reference on a frozen workload. A
`quality_equivalent` label requires predeclared per-output tolerance and task-level non-inferiority
margins on sufficient independent encounters; small G0a fixtures alone cannot establish it.
Otherwise retain the path as a separately scored quality-cost variant. A vector path may be slower
or consume more energy for small regions; such a negative result remains reportable.

### 7.3 Tensor graphs and heterogeneous compute backends

Framework-owned tensor models and graph operators have a **pinned portable CPU reference execution**
in a declared runtime; they do not require a second hand-written scalar C++20 implementation. An
external black-box model without such a reference may still be scored against task labels, but
cannot claim kernel/graph equivalence to a missing reference. An optional accelerated execution may
use CPU tensor instructions/libraries, GPU, NPU, FPGA or another available device through a
versioned backend adapter. CPU matrix extensions such as Arm SME or x86 AMX are optional backend
paths only after their ISA and operating-system state or permission is verified. The benchmark does
not require every candidate runtime or device to be implemented. The adapter separates graph/model
semantics from device execution and reports unsupported graph portions. Its pre-run capability check
compiles and executes a representative graph with the intended input shapes, batch, precision and
memory limit. Runtime provider discovery or device enumeration alone is insufficient because an
execution provider can partition a graph and fall back to CPU.

The compute manifest records model/weights and graph hashes; runtime, backend, compiler, driver and
firmware versions; device and memory identifiers; input/output shapes, layout, batch, data type,
quantization scheme and calibration-data revision; declared operator partition and fallback policy;
compilation/cache state; and actual device assignment or profiling evidence. It also records
pre/postprocessing revisions, host<->device transfers, zero-copy claims, thread settings and power
boundary. For an external black box, unavailable internal fields are explicitly `opaque` with a
reason and the strongest available executable/package or endpoint version identity; task scores
remain possible, but graph-equivalence, exact-reproduction and unverifiable accelerator-partition
claims are withheld. Do not label a run "NPU" or "GPU" solely because the device is present. If a
backend cannot prove its intended operator coverage, it may run only under a declared mixed-device
profile with observed CPU fallback and its full cost.

If pre-run probing shows that a requested accelerator-only profile needs undeclared CPU fallback,
that profile is `UNSUPPORTED`; a declared mixed-device or CPU profile may be selected before input
begins. During a run, an undeclared fallback attributable to a frame is `MODULE_FAULT` from the
first affected frame, with the remaining scorable input handled under section 5. If only aggregate post-run
evidence reveals an unlocalized fallback, keep task outputs and fault evidence visible, but mark
accelerator-specific timing/energy results `UNSUPPORTED` with reason `backend_unverified` and
exclude the run from that compute cohort. Neither case is silently credited as acceleration.

Exact integer kernels require exact outputs when their specified arithmetic is exact.
Floating-point, FP16/BF16, mixed precision and INT8/other quantized paths declare numerical
tolerances **before** execution, and report task-level detection/tracking/recognition changes,
coverage and failures alongside tensor differences. Quantization calibration and threshold selection
use development data only. A changed model, calibration, precision or operator partition is a
distinct compute variant, even when its output is within tolerance. `quality_equivalent` uses the
same predeclared output and task-level non-inferiority rule as section 7.2; an equivalence failure remains
a valid separately scored result. Compare both cold-start cost (load/compile/first result) and
warmed sustained behavior. Microbenchmarks of isolated operators or kernels are diagnostic; the
primary timing and energy evidence is end to end, including preprocessing, copies/synchronization,
queueing, inference, postprocessing, output publication and any fallback. Asynchronous device work
must be synchronized at the declared completion boundary before an output or elapsed time is
counted. Fixed batch and concurrent-stream workload definitions prevent throughput gains from
concealing missed per-frame deadlines.

### 7.4 Linux real-time profile and timing evidence

The module boundary and runner are designed from the start for bounded, timestamped,
backpressure-aware execution. Hot paths should avoid unbounded queues and allocations, synchronous
logging and uncontrolled retries; persistent buffers and watchdog behavior are explicit. G0 lockstep
replay remains independent of scheduling claims. G1 requires paced input on normal Linux; a separate
`CONFIG_PREEMPT_RT` profile is optional and evaluated when claimed. The probe checks the running
kernel configuration and whether scheduling policy, priorities, affinity and memory locking can
actually be applied. An unavailable or unauthorized PREEMPT_RT profile is `UNSUPPORTED` for that
profile, never silently emulated and does not block normal G1. Real-time priority is not enabled by
default and must not starve capture, telemetry or system housekeeping.

A real-time claim is a measured deadline claim for a named camera mode, frame rate, workload,
compute variant, kernel, scheduler policy, affinity, CPU governor, thermal state and sustained
duration. Run repeat trials including declared concurrent camera/telemetry and I/O load. For
heterogeneous backends, record device queueing, transfers and synchronization; CPU scheduler
settings do not bound opaque accelerator-driver or firmware latency. Report
acquisition-to-publication latency when physically calibrated, otherwise exact available segments;
also report scheduling jitter, queue occupancy, p50/p95/p99/p99.9 and maximum latency, deadline-miss
count and proportion, dropped/late frames, throughput and throttling. Comparisons between normal and
PREEMPT_RT profiles keep the same hardware, compute variant and workload. PREEMPT_RT is a
latency-control mechanism, not an intrinsic acceleration or a hard guarantee on arbitrary USB,
firmware or application paths. A fixed frequency can improve timing repeatability but may increase
energy; record the trade-off.

The platform references for scheduling, instruction dispatch and tensor-provider behavior are listed
in section 14.

### 7.5 Controlled bench and energy measurement

G1 bench trials use a controlled, non-sensitive object whose trajectory is measured independently of
the camera under test (for example a motion-stage encoder or separate calibrated reference camera).
A fiducial measured only by the tested camera is not independent ground truth. Run stationary and
controlled motion/vibration conditions, with repeated trials, declared warm-up, camera mode,
exposure/focus/FOV, object pixel/angular extent, lighting, queue/drop counts, host load and
throttling state. Synthetic vibration is labelled synthetic unless its spectrum came from an
instrumented platform. Display-screen targets are labelled because refresh and moire can change
results.

A power measurement declares its **boundary**: module/CPU rail, accelerator rail when separately
measurable, full computer, a **fixed installed-system boundary** containing every compared sensor
plus computer and transport, or vehicle. A paired sensor-policy energy claim uses the same
installed-system meter boundary in both arms, including sensor active, standby, off and wake costs
even when a sensor is disabled by one policy. Record meter model, calibration, sample rate,
timestamp alignment, voltage/current or watts, sensor uncertainty, missing samples, warm-up and run
interval. A sensor-fusion energy claim includes acquisition, transport, memory/accelerator transfers
and processing inside that boundary; report startup/wake and warmed steady-state intervals
separately. Integrate measured power over the declared interval to joules. If a rail is shared,
report shared-rail energy rather than assigning it to one process. An idle-baseline subtraction is a
separately labelled incremental estimate, never the only result. Sensor-off savings require a
measured on/off mode; suppressing a recorded stream in software is an input ablation, not a power
measurement. Runs without adequate instrumentation report energy `NOT_MEASURABLE`; CPU utilization,
device utilization or thermal readings are not substituted for joules.

Show total joules, mean/peak watts with the peak measurement bandwidth, joules per scheduled input
frame for video or per scheduled **task epoch** for asynchronous sensing, joules per delivered
output, and joules per second of scheduled observation, always with scheduled/delivered counts,
scorable exposure, quality and deadline-miss denominators. Joules per correct track-second or true
detection may be shown only as a secondary conditional diagnostic, with a zero-denominator status;
it cannot reward a system that emits few results. Host and meter/installed-system boundaries define
separate energy cohorts; the enabled sensor subset is an explicit factor **within** a fixed-boundary
cohort. The dashboard presents quality-latency-energy trade-offs or Pareto views within matched
cohorts rather than one universal weighted score. The rank in
[section 16.1](#161-cohort-ranking) is a floor followed by an energy order inside one cohort,
not a weighted score. section 7.9 supplies the normative instrument,
integration and uncertainty procedure for these quantities.

For glass-to-output latency, measure the camera-mode glass-to-buffer offset using a physical
optical/timing reference seen by the camera and recorded against the reference clock; a driver
buffer timestamp alone is insufficient. Cross-host latency additionally needs clock-offset/drift
uncertainty below the claimed resolution. Otherwise report process-local or buffer-to-output time
with its exact name. Before opening a stereo-range suite, compute an uncertainty budget from
measured focal length in pixels `f_px`, baseline `B`, disparity error `sigma_d` and range `Z`,
including the leading approximation `sigma_Z ~ Z^2 * sigma_d / (f_px * B)`. Add calibration and
synchronization error terms, then verify with independent measured distances. If the predeclared
tolerance is not achievable, the mode is `UNSUPPORTED` for range even if both cameras stream
successfully.

### 7.6 Multi-sensor fusion and uncertainty

The first fusion reference is a transparent **late-fusion** path: modality-specific motion
proposals/detections or tracklets enter an event-time association step, then a fused existence,
class or state estimate is emitted with source provenance. Feature-level or learned fusion is a
separately scored variant, not a hidden prerequisite. The adapter gates association using calibrated
spatial and temporal uncertainty and preserves an explicit `unassociated` result; a false merge is
worse than admitting ambiguity. Two cameras may supply complementary fields of view or stereo
geometry after calibration. An acoustic event can suggest activity or, with a calibrated array,
direction; it cannot be assigned to a visible instance solely by time coincidence. Radar may provide
range, angle or radial velocity according to its actual mode; W-band is a frequency designation, not
evidence that a particular module can resolve a small object at the benchmark's target range.

For every fused output, expose the contribution of each source, sensor age, transform/clock
uncertainty, association probability or decision, and reason for accepting, down-weighting or
rejecting a measurement. Calibration uses a disjoint calibration split and appropriate reference
labels: probability of correct detection/identity, class posterior, track existence and geometric
covariance are fitted and validated separately. Post-processing quality indicators (for example
blur, SNR, radar return quality, association residual, track age and sensor health) may adjust
uncertainty **after** that modality has run. Correlated camera views, multiple crops from one frame,
or a tracklet and the detections that produced it are not treated as independent observations. Where
dependence cannot be modelled, use a conservative fusion rule or refrain from a calibrated posterior
claim. Unreliable, stale or conflicting measurements may be rejected or yield an explicit
uncertain/abstaining output, while the original task event remains in the scoring denominator.

#### Sensor-family registry and feasible observation roles

The adapter registry is **open to any sensor with a physically meaningful measurement model and the
section 5 contract**. It is not a claim that every family is useful for every object or that all families
must be installed. For the initial small-bird scenario (approximately 15 cm body and 10-100 m
research distances), rank feasibility by measured object extent/signal, field of regard, platform
motion/noise, timing and installed-system energy. Published performance on larger birds, stationary
towers, specialised ground instruments or humans does not establish detection at 100 m with a
compact payload. The following roles determine which G2 suites may be opened:

| Family and principle | Potential observation and first front end | Applicability and validity limit |
| --- | --- | --- |
| Visible wide/narrow or stereo cameras (reflected light) | Frame difference/background model, ego-motion-compensated optical flow or a declared detector; boxes/points/bearings, stereo range only with calibration | **First airborne baseline.** Object pixel extent, motion blur, illumination, FOV loss and disparity uncertainty determine usable range; wide/narrow gains and 100 m performance must be measured on the actual optics. A [published stereo bird study](https://jeb.biologists.org/content/jexbio/218/16/2496.full.pdf) used specialised long optics, so it cannot validate a Pi camera profile |
| Event camera (asynchronous brightness change) | Time-surface or event-cluster motion proposals with background/ego-motion compensation | Candidate for fast moving targets; moving background, texture, lighting and event rate can dominate. [EV-Flying](https://openaccess.thecvf.com/content/CVPR2025W/EventVision/html/Magrini_EV-Flying_an_Event-based_Dataset_for_In-The-Wild_Recognition_of_Flying_Objects_CVPRW_2025_paper.html) includes bird events but does not establish this system's range or energy |
| NIR/SWIR, multispectral or polarimetric imaging (reflected light) | Registered per-band contrast/feature proposals, then a separately scored multimodal detector | Candidate when spectral contrast is validated. Active illumination, filters and extra optics add mass, power and alignment cost; NIR/SWIR are not passive thermal measurements. Cross-band matching needs measured timing/geometry. A [field comparison of spectral imagers](https://www.osti.gov/servlets/purl/1342469) illustrates modality-dependent visibility and false returns |
| Thermal LWIR/MWIR imager or coarse thermopile array (emitted heat) | Contrast/background and temporal proposals, with temperature/scene quality flags | Candidate for low-light observation, but thermal pixels, optics, sky/ground contrast and weather govern small-target visibility. Coarse thermopiles are local occupancy triggers, not assumed 100 m trackers; thermal appearance alone does not establish species. A [field thermal study of small songbirds](https://pmc.ncbi.nlm.nih.gov/articles/PMC4705634/) used specialised narrow-FOV equipment, not a compact-payload validation |
| Microphone or synchronized acoustic array (sound emission) | Band-limited event detection; with calibrated geometry, beamforming/GCC-PHAT or time-difference-of-arrival bearing/location | Only a **calling or otherwise audible** object supplies direct evidence; silence is not absence. A single microphone has no justified range or bearing. [Flight-call localization](https://pmc.ncbi.nlm.nih.gov/articles/PMC5513243/) used a distributed array; propeller/wind noise and acoustic association must be measured separately for an onboard array |
| Radar, including CW/FMCW, scanning or passive radar (RF scatter) | Mode-specific detection/CFAR, range-Doppler and angle estimation; wingbeat micro-Doppler only if actually resolved | Candidate range/radial-velocity cue. Cross section, beamwidth, clutter, false returns, transmit/receive mode, antenna and full-system power dominate feasibility; W-band names a frequency region, not a performance guarantee. [24/94 GHz bird measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC6255807/) do not establish 100 m performance for a smaller bird or the proposed payload |
| Lidar/scanning laser and ToF/depth camera (active optical range) | Return clustering, temporal background subtraction and geometric association | Potential 3D cue only where a sufficiently dense return hits the small target. Commodity compact ToF modules are predominantly near-field; [a representative ToF module](https://ai.benewake.com/en/resources/technical-documents/tfmini-s-datasheet/) cannot be treated as a 100 m bird sensor. Specialised long-range lidar is a different equipment class. Account for active-emitter operation and power |
| PIR, passive thermal-motion, microwave Doppler presence or IR break-beam (zone crossing) | Debounced threshold/change event, with mapped coverage zone and refractory period | **Local trigger/flight corridor or perch**, not an identity, range or 100 m free-flight track. PIR requires usable thermal contrast and can miss small/fast animals; a [wild-bird camera-trap study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6065333/) shows that size and distance matter. Microwave presence and break-beam signals likewise need a bounded observed zone |
| Ultrasonic/sonar range (active acoustic echo) | Thresholded echo/range with multipath and temperature flags | Near-field obstacle or instrumented corridor cue, not an assumed 100 m bird detector. A [representative weather-resistant ultrasonic sensor](https://maxbotix.com/products/mb7566) is specified for metre-scale operation; flight noise and small-object echo strength need direct testing |
| Contact/vibration/pressure sensors: perch accelerometer, load cell, piezoelectric switch, ground geophone/seismic | Contact/footfall or substrate-vibration event detection, with location/coupling and negative-zone status | **Perch, nest platform or ground contact only.** They do not observe an untagged bird in open air at 100 m. Use them as local triggers or independent bench/field reference when the contact zone is known; soil/perch coupling and weather vibration must be tested. [Bird perch load-cell](https://pmc.ncbi.nlm.nih.gov/articles/PMC12795351/) and [terrestrial geophone footfall](https://besjournals.onlinelibrary.wiley.com/doi/full/10.1002/2688-8319.70072) experiments concern physical contact |
| Cooperative RFID/UWB/radio/GNSS tag receiver | Tag ID, time and geometry according to the actual radio system | Only for **instrumented subjects** and governed studies; useful reference/association evidence but never a score for detecting untagged subjects. [Motus radio telemetry](https://motus.org/resources/how-motus-works/) is one example. Tagging and tag power/weight are scenario constraints |
| Platform and environmental sensing: IMU, visual odometry, GNSS, compass, barometer, motor RPM/current, wind, light, temperature, humidity | Ego-motion, pose, exposure/noise/clutter and sensor-health context | **Supporting evidence**, not a direct object detector. Use to compensate camera/radar motion, predict sensor observability and acquisition cost, and stratify results. A platform signal cannot be counted as an independent object sighting |

For each proposed family, the scenario profile states `AIRBORNE_CANDIDATE`, `NEAR_FIELD_OR_CONTACT`,
`COOPERATIVE_ONLY` or `CONTEXT_ONLY`, plus an **evidence-backed envelope** of object size, distance,
field of regard, lighting/weather/platform state and observed detection/false-alarm counts.
`AIRBORNE_CANDIDATE` is a hypothesis to test, not a validated range claim. Unmeasured cells are
`MEASURE_REQUIRED`; physically unsupported task/mode pairs are `UNSUPPORTED`. A new sensor adapter
must supply raw-format provenance, typed observation and uncertainty, clock/geometry/coverage
calibration, explicit negative and failure events, an installed power-mode profile and conformance
fixtures. If a modality lacks an independent reference for its claimed quantity, only its supported
event-level outputs are scored. Chemical traces, eDNA and coarse environmental counters can indicate
presence over a broader area/time interval but cannot furnish an individual real-time track under
this task contract; they require a separately defined task before scoring.

#### Reference and optional fusion algorithms

G2's mandatory reference path is a **deterministic, transparent late-fusion baseline**. Each front
end converts its raw signal to typed observations; a bounded event-time reorder buffer releases only
events available by `t_fuse`; frame/pose transforms and clock uncertainty are applied before
spatial-temporal gating. The baseline groups admissible measurements by compatible geometry and
provenance, performs gated one-to-one association where identity is resolvable, retains unmatched
evidence, and outputs an explicit fused/ambiguous/empty result. It computes existence using a
calibrated per-sensor detection/false-alarm model and a stated dependence model. For a sensor that
was active, healthy, in coverage and actually observed `no_detection`, negative evidence may update
existence through context-dependent `P_D(x, context)`; `missing`, `disabled_by_policy` and
`out_of_view` contribute **no** negative observation. Raw detector scores are never summed as
independent probabilities. A class posterior is updated only from calibrated class evidence and is
kept separate from existence and geometry.

Replaceable algorithms may include Kalman filtering for a linear common-state model; EKF/UKF for
nonlinear bearing/range geometry; particle filtering for multimodal states; JPDA or multi-hypothesis
tracking for ambiguous multi-object associations; and feature-level or learned fusion when a
governed training split supports it. Covariance intersection is permitted only for **same-state
estimates with unknown cross-correlation and defensible input covariance**, not for arbitrary class
scores or all mixed-sensor measurements. A random-finite-set/labeled multi-Bernoulli path is
optional for uncertain object count. All candidates use the same event-time, availability,
state-space, provenance, output and evaluation contracts. A learned path reports data/weights,
training split, calibration, missing-modality behavior, compute/energy cost and no hidden future
context. A mathematically more complex algorithm is accepted only when matched-scenario evidence
improves a declared quality-cost point; no candidate family is a mandatory dependency for G0/G1.

### 7.7 Resource-aware acquisition and processing policy

A later policy chooses among versioned, feasible **actions** at each decision time: sensor subset
and mode/rate, camera field or region of interest, algorithm/model/backend/precision, full
re-detection versus track update, optional classifier, defer or skip an expensive update. Each
action has a declared acquisition and processing path; a skip records what was not run and does not
imply the object is absent. A low-cost continuity path is defined for each claimed deployment
profile, with an explicit `lost` or abstain result when even that path cannot run. The policy
interface is algorithm-neutral: rule-based, predictive and learned policies all emit the same
decision and resource events.

Decision-time context may include the last valid track/existence distribution, scene preview already
available, expected object size, previous sensor health, motion, queue/load, temperature and
remaining energy budget. It cannot include current measurements from a sensor/action that has not
run or future video. Development-only profiling may estimate each feasible action's **marginal task
benefit, probability of an incorrect confident output, latency and complete sensor-plus-compute
energy** under that context. Post-action quality features update output uncertainty, not the prior
choice. The policy minimizes predeclared expected task loss and resource cost under hard per-epoch
deadline, memory/bandwidth, peak power/current, thermal and rolling energy constraints; the exact
optimizer is a replaceable implementation. A ratio such as gain per joule alone is insufficient
because nearly free, uninformative skipping could dominate it. A declared fallback action handles
unmet constraints without concealing a miss.

The mandatory policy comparators are **always-on feasible**, fixed-period/rate, fixed sensor subset,
random skip with a frozen seed, and a transparent uncertainty/event-triggered rule that activates an
expensive mode when predicted track uncertainty, observability loss or event risk crosses a
development-set threshold. The first adaptive reference policy can use a calibrated one-step **value
of information (VOI)** estimate: for each feasible action, estimate the expected reduction in
predeclared tracking/detection/classification loss against its complete acquisition, wake, transport
and processing joules and latency; choose under hard deadline, peak, rolling-energy, thermal and
memory limits. A budgeted MDP/POMDP, bandit or learned controller is optional behind the same
action/result contract and must report its state, training provenance and out-of-support behavior.
An oracle that selects using future measurements or ground truth is an explicitly labelled
diagnostic upper bound, never a deployable comparator. The objective and weights are declared before
locked evaluation; a gain-per-joule ratio alone cannot override minimum quality and false-alarm
constraints.

The scenario pins energy-window length and budget, feasible modes, deadline, minimum task coverage
or `P_D` target at a fixed false-alarm burden, calibration/integrity limit, and priority when
constraints conflict. The runner records **every feasible action's predicted task loss, energy,
latency and uncertainty**, the selected action, predicted versus realized cost and task outcome for
every decision, including wake-up overhead, dropped inputs and budget violations. Prediction error
is measured on held-out encounters; an inaccurate cost/benefit model is visible even when the
selected action happened to succeed. Model, cost predictor, probability calibrator and policy
thresholds are trained/tuned only on development/calibration encounters and frozen for locked
testing. Offline full-stream replay can compare **input selection and processing choices** if all
candidate raw data was recorded; it cannot establish sensor-on/off energy or a scene response to a
different active sensor. Physical energy savings and sustainable joint modes require measured bench
trials. Policy comparisons use the fixed baselines and, where measured, the frontier in section 6.5.
Every skipped true event is a miss; a policy fails its declared quality target or no-loss claim when
that miss contributes to a violation of the predeclared floor or margin.

### 7.8 TDD reference tracker and stagewise development

Implement a deliberately simple **reference tracker** as an executable module, not as an accuracy
oracle. G0a starts with one camera, an identical operator-provided target box and deterministic
frame order. The baseline uses a bounded region proposal or declared camera detector, a
constant-velocity image-plane Kalman prediction (with a specified process/measurement noise model),
uncertainty- and geometry-gated matching, a deterministic one-to-one assignment rule when multiple
instances are present, and explicit tentative/confirmed/lost/reacquired track states. If no credible
observation is available, it acknowledges the scheduled frame/epoch and emits `lost` rather than
preserving a confident stale box; a calibrated track-existence probability is added only after a
separate calibration suite supports it. Its seed, parameters, thresholds, numerical tolerances and
source revision are fixed in each run. The G0 baseline validates the runner, labels and score
calculations; it does not set a minimum target score for future models.

At G2, front ends, the deterministic late-fusion reference, track maintenance and the optional
resource policy are independently replaceable; section 6.6 isolates the first three and evaluates
the full pipeline separately. The G2 reference tracker consumes the same frozen `FusedObservation` or
single-source observation bundle as a candidate tracker; it cannot inspect unavailable raw
measurements. Its motion model stays in image coordinates until a separately calibrated
common/world-state model is enabled. Stereo/radar range, acoustic direction and contact triggers
therefore do not become interchangeable 2D boxes by convention. The `FusionResult` and
`TrackerResult` contracts preserve the exact source lineage of any track update and mark the
measurement's contribution versus prediction-only continuation. The report can compare the simple
reference with each candidate at the tracking and complete-system boundaries, while the fusion
baseline is compared at the fusion boundary; neither reference is claimed optimal.

TDD fixtures are hand-audited before an algorithm variant is accepted: perfect single-object
continuity; target absence and moving distractor; partial/complete occlusion and re-entry;
two-object crossing and duplicate proposals; camera shake/ego-motion error; wide/narrow switch with
calibrated and uncalibrated geometry; delayed, reordered and clock-skewed observations; correlated
duplicate sources; active `no_detection` versus `out_of_view`, source `missing` and
`disabled_by_policy`; contradictory camera/acoustic/radar or contact evidence; impossible covariance
and stale calibration; budget exhaustion, wake delay and missed deadline. Each fixture defines
expected acknowledgment count, lineage, allowed association/abstention, state transition, metric
numerator/denominator and resource accounting. A causal replay test changes future observations
while holding past events fixed and asserts that every earlier `AcquisitionDecision` is unchanged. A
sensor-subset test asserts that an uninstalled modality cannot silently supply evidence or joules.
The fixed-input fusion and tracker suites run on hashed bundles so a front-end change cannot
masquerade as a downstream improvement.

Every new fusion or tracking algorithm first adds or extends a failing conformance/quality fixture,
then implements the variant, then runs paired development encounters and the frozen negative cases.
Numerical equivalence, task quality, latency and energy are separate claims; passing fixtures proves
contract behavior only. Reference artifacts include event logs, intermediate state/posterior traces,
selected actions and hashes sufficient to reproduce a failure without exposing restricted media.

### 7.9 Hardware metrology and measurement algorithms

Hardware evidence follows a versioned **measurement protocol**, independent of a candidate module's
own counters. Before acquisition, declare the measurand and units; physical/electrical and software
boundary; camera/sensor and compute modes; workload and scheduled duration; instrument model/serial,
range, resolution, bandwidth, calibration/check date and uncertainty; clock domain/alignment;
warm-up and ambient conditions; repetitions and order; raw-trace retention; pass/fail tolerances;
and minimum precision required for the claim. Preflight checks include meter zero and known-load
response, time-marker alignment, target/reference calibration, free storage and sustainable joint
sensor modes. The exact tested physical assembly, optics, cable/transport, power source/regulator,
cooling and mount are photographed or inventoried in the host profile. A datasheet value is a
**design input**, not a measured result. Missing instruments yield `NOT_MEASURABLE` for the affected
quantity without erasing valid quality results.

The immutable `HardwareTrial` evidence bundle contains the protocol and host IDs; instrument and
calibration records; raw power, resource, sensor and reference traces with hashes; trial start/end
markers; event/clock alignment and uncertainty; sample gaps, saturation and counter-overflow flags;
the metric calculation revision; each estimate, unit, uncertainty and validity status; and the
reason for any invalid or inconclusive claim. `PowerSample` and `ResourceSample` are the time-series
records under this bundle, not substitutes for it. Every reported performance and power value in a
paired quality-energy point comes from the **same trial and output trace**. Instrumentation overhead
is measured by a paired instrument-on/off diagnostic where feasible; it is not silently subtracted
from the primary installed-system result.

#### 7.9.1 Common trial design and uncertainty

Run a declared idle/reference interval, cold-start or wake interval when relevant, warmed steady
interval, and a sustained interval long enough to expose the declared thermal/queue state. Keep the
input schedule, scene, sensor modes, host, software/firmware and environmental conditions fixed
across candidates; record unavoidable variation such as ambient temperature, supply voltage or
battery state of charge. Use at least three independent trials per G1 operating point as an initial
repeatability check, then increase repetitions according to a **predeclared precision or power
requirement**, especially for tail latency, rare drops or small energy differences. Balance or
randomize A/B order within matched blocks so a warming device or changing battery does not
systematically favor one variant. Do not choose a favorable stopping time after viewing results or
pair the fastest A run with the lowest-power B run. Keep every run, including thermal throttling,
undervoltage, crashes and late results, with its status.

Report per-trial values, pooled descriptive statistics and a paired difference with an uncertainty
interval built at the **independent trial/encounter block**, not by treating correlated video frames
or meter samples as independent replicates. Tail percentiles include their sample count and an
interval or an `insufficient_data` status when precision is not supported. Use a traceable
uncertainty budget with instrument accuracy/zero/drift, calibration target or reference trajectory,
quantization/bandwidth, clock offset/drift, numerical integration and between-trial variation;
include covariance when errors share a source. Give combined standard uncertainty and, when
reported, an expanded uncertainty with its stated coverage factor. A comparison whose uncertainty
overlaps a predeclared decision margin is `inconclusive`; it is not rounded into a gain. The method
follows [NIST uncertainty guidance](https://physics.nist.gov/cuu/pdf/tn1297.pdf), with test-specific
budgets rather than a universal percentage.

#### 7.9.2 Capture, optics and geometric sensing

The camera test fixes lens/zoom/focus/aperture, exposure, gain, pixel format, crop, binning,
resolution, frame rate, ISP/sharpening and decoder. A measured calibration chart and distance
establish effective focal length in delivered-image pixels `f_px`, distortion and field of view for
**each capture mode**; report calibration residual and spatial uncertainty. Predict body extent only
as `p_body ~ f_px L_projected / Z` and motion smear only as `p_smear ~ f_px |omega_relative|
t_exposure`, with object projection, angular motion and uncertainty stated. Verify both predictions
using a physical target of declared dimensions at independently surveyed distances (the initial
small-bird scenario uses 20, 50, 75 and 100 m where the site permits), rather than declaring
detection from pixel count alone. Preserve delivered-image crop/contrast, measured object pixels,
blur and illumination for the actual evaluation frames. If an optical sharpness claim is needed, use
a reproducible [ISO 12233
slanted-edge/e-SFR](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso%3A12233%3Aed-5%3Av1%3Aen)
chart at center and edge, retain the full SFR curve and report MTF50 with the exact delivered
processing path; sharpening can change the curve. A controlled linear/raw path may additionally use
[EMVA 1288
Linear](https://www.emva.org/standards-technology/emva-1288/emva-standard-1288-downloads-2/) for
photon-transfer noise/dynamic-range characterization. An ISP-processed/compressed USB stream reports
delivered-image contrast/SNR and settings unless an appropriate EMVA 1288 General procedure is
independently fulfilled; it never silently inherits a raw-sensor property. Range-stratified object
detection/tracking quality remains a separate task metric at a fixed false-alarm burden.

For each camera stream, count unique valid source-frame IDs in the **declared trial interval** `T`
and report delivered frame rate `N_valid/T`, duplicates and inter-frame gaps. A numerical
**source-drop fraction** `(N_scheduled - N_valid_matched)/N_scheduled` is valid only when an
authoritative trigger schedule or trustworthy device sequence counter defines `N_scheduled` and
one-to-one matched valid frames; free-running nominal requested FPS is not that schedule. Otherwise
report delivered FPS, gap distribution and `upstream_drop_unknown`, without a fabricated
capture-drop fraction. Use source IDs and capture/arrival/publication timestamps to distinguish
capture loss, transport loss, queue drop and module skip; unresolved causes remain `unknown`. Report
inter-frame interval residuals relative to a valid schedule when one exists, jitter distribution and
maximum gap. The nominal UVC/CSI or USB link rate and requested camera FPS are not delivered
throughput. Check joint camera modes with all intended streams and logging active. Because [V4L2
buffer timestamps](https://docs.kernel.org/userspace-api/media/v4l/buffer.html) have driver-defined
origins, measure exposure-to-buffer offset and jitter per mode using a timed LED/strobe plus an
electrical or photodiode reference in the same clock domain. With two cameras, image the common
marker to estimate exposure-midpoint skew, drift and rolling-shutter row timing; revalidate after
mode, exposure, driver or transport changes. Stereo range is scored only against independently
surveyed distances or trajectories, with bias, RMSE, high-quantile absolute error, valid-output
coverage and uncertainty by distance/speed/light. Predicted `Z^2` error growth in section 7.5 is
a feasibility check, not the measured result.

Other installed sensor families have modality-specific **independent physical stimuli and reference
measurements**, with fixed thresholds before test:

| Sensor | Controlled stimulus and reference | Measurements and algorithm |
| --- | --- | --- |
| Event camera | Programmed brightness steps and moving target under measured illumination, with an electrical trigger | ON/OFF event threshold, onset latency distribution, background event rate, hot/noisy pixels, event loss/saturation and event bytes/s; then moving-target detection/track quality. Nominal microsecond timestamp granularity alone is not latency evidence ([NIST event-camera latency method](https://www.nist.gov/publications/pixel-latency-measurements-event-cameras)) |
| Thermal imager/array | Calibrated blackbody or controlled temperature-contrast target of known angular size, followed by physical small-target scenes | Temperature contrast/noise and spatial resolvability by mode and environment; thermal noise-equivalent temperature difference, when valid, is **not** sufficient to infer small-object detection range ([thermal-imager measurement study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8434484/)) |
| Microphone/array | Known-position, level-calibrated speaker or recorded call under quiet, wind and platform-motor-noise conditions; surveyed geometry | Event recall at fixed false-alarm rate, onset delay, SNR, array time-difference/bearing bias and localization error/coverage where geometry supports it; silence is an opportunity/observability condition, not automatically an object miss ([flight-call array validation](https://pmc.ncbi.nlm.nih.gov/articles/PMC5513243/)) |
| Radar | Independent timed crossing or moving calibrated reflector/target with surveyed range, speed, angle and clutter/background conditions | Detection probability and false-track rate by size/aspect/range/background, range/angle/radial-speed bias and spread, update latency and missed scans; micro-Doppler quality only when actually resolved. Freeze threshold before test and measure **full radar-plus-host** power, not transmit power alone ([avian-radar field validation](https://pmc.ncbi.nlm.nih.gov/articles/PMC3774623/)) |
| Lidar/ToF/ultrasonic | Independent target distance, size, reflectance or acoustic impedance and incidence angle, with moving-target passes | Return/hit coverage, range bias/RMSE/uncertainty, false returns, scan or echo cadence, angular coverage and dropout under ambient conditions; compact-module range is independently verified before an airborne claim ([NIST 3D-imager range protocol](https://www.nist.gov/publications/characterization-range-performance-3d-imaging-system-nist-tn-1695)) |
| PIR, microwave presence, break-beam, contact and seismic | Known zone crossings or measured contact/footfall force, speed, temperature contrast, substrate and environmental motion | Trigger recall, false triggers per exposure, onset/wake delay, hysteresis/refractory behavior and mapped coverage; these are local-event tests and never converted to free-flight range by assumption ([wild-bird PIR test](https://pmc.ncbi.nlm.nih.gov/articles/PMC6065333/)) |
| IMU, pose, GNSS, light, wind and other context sensors | Calibrated rotation/translation, surveyed position, reference light/wind or known electrical input as appropriate | Bias, scale, noise/drift, sample interval, clock skew and dropout; evaluate how compensation changes perception quality, but never count context samples as object detections |

For every modality, record object/stimulus extent and physical distance, reference uncertainty,
coverage zone, rate, duty cycle, active-emitter state, transport mode and installed mass. A
reference speaker, reflector or heated target validates an **instrument response and geometry**, not
the class-specific behavior of an actual animal. Bench measurements that do not match field texture,
contrast, sound or radar cross section support a hardware capability statement only; field-range
detection claims need independently labelled field encounters under the corresponding scenario
rules.

#### 7.9.3 Timing, compute, memory and I/O

The runner records scheduled input, sensor exposure/capture, driver-buffer availability, receive,
queue entry/exit, preprocessing, CPU/accelerator start/end and fence completion, publication, and
optional display times with clock IDs. For two timestamps on a validated common monotonic clock,
segment latency is their difference; never sum overlapping CPU and device intervals or use
wall-clock adjustment as elapsed time. Prefer `CLOCK_MONOTONIC_RAW` for Linux process intervals when
available, while preserving the clock used by external sensor hardware. For cross-host or
glass-to-output claims, align an independent GPIO/LED/photodiode marker or calibrated
clock-offset/drift trace and propagate its uncertainty. If the alignment error is larger than the
predeclared latency resolution, report the narrower valid segment and mark the broader claim
`NOT_MEASURABLE`. A physical marker also calibrates camera sensor/driver delay; a software timestamp
at dequeue cannot substitute for it.

Measure per-stage and end-to-end p50/p95/p99/p99.9, maximum, throughput, queue occupancy, scheduling
jitter, and **deadline-miss fraction** `(late + missing scheduled outputs)/N_scheduled` over the
same run. Percentiles exclude no valid slow result; missing results are counted separately as misses
rather than silently removed from the denominator. A real-time claim states its **deadline and
observed violation count**, not an extrapolated worst-case bound from a finite sample. `rtla
timerlat`/`osnoise` or an equivalent kernel tracer may diagnose scheduler wake-up latency, but
[timerlat](https://docs.kernel.org/trace/timerlat-tracer.html) is not the camera-to-output
application latency. Record Linux kernel/preemption mode, task policy/priority/affinity, governor,
concurrent sensor and I/O load, thermal state and trial duration for every timing cohort.

Record process user/system CPU time and, where supported, cgroup CPU time/pressure; peak process RSS
and **cgroup-wide** memory peak, page faults/OOM/pressure, queue/buffer allocation, accelerator
memory, storage read/write bytes and latency, network/USB payload bytes and errors. Derive valid
delivered throughput as payload bytes or acknowledged events divided by scheduled observation time;
compare to the required rate under simultaneous sensor load. A nominal USB speed, CPU clock or
memory size is not a sustainable pipeline rate. Hardware cycles/instructions/cache or SIMD dispatch
evidence may diagnose a bottleneck, but `perf` events must record support, privilege, counter scope
and `time_enabled/time_running` multiplexing; estimated scaled counters are labelled diagnostic, not
a task-quality or joule measurement. [Linux cgroup
v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), [procfs high-water
memory](https://docs.kernel.org/filesystems/proc.html) and
[`perf_event_open`](https://man7.org/linux/man-pages/man2/perf_event_open.2.html) define the
relevant counter semantics. A compute comparison includes preprocessing, DMA/transfers,
synchronization, postprocessing, telemetry/logging and fallback, with cold and sustained phases
reported separately.

#### 7.9.4 Electrical power, thermal state and motion

For a power claim, place a calibrated external analyzer or synchronized voltage/current meter at a
**fixed, declared boundary** such as the Pi 5 USB-C/DC input, battery terminals, regulator output or
whole installed-sensor input. These boundaries include different regulator and cable losses and are
not pooled. Check zero, known-load response, sample rate/bandwidth, time base, voltage burden/shunt
drop and saturation before the trial. Align analyzer and runner by a shared electrical/GPIO marker
or measured offset/drift with uncertainty. With simultaneous samples, set `P_i = V_i x I_i`;
interpolate the boundary samples at marked `a` and `b`, then compute `E_[a,b] = sum (P_i + P_(i+1))/2
x (t_(i+1)-t_i)` over the **exact marked interval** `[a,b]`, or use a calibrated analyzer's integral
counter with the same boundaries. Voltage and current sampled on different clocks require validated
alignment before multiplication. Include active acquisition, transport, CPU/NPU work, standby/off
and wake transitions inside the chosen full-system boundary. Record absolute joules first; a
bracketed idle-baseline subtraction is secondary. Never infer joules from CPU utilization, TDP,
nominal sensor watts or suppressing a recorded stream. This follows the same-run power/performance
principle in the [MLPerf power-measurement
policy](https://github.com/mlcommons/inference_policies/blob/master/power_measurement.adoc).

Determine meter bandwidth and maximum acceptable sample gap **before** testing from the shortest
wake/load transient and decision window being claimed. Reject saturated, clipped, missing-gap or
clock-misaligned intervals as `NOT_MEASURABLE` for energy when their uncertainty breaches the
predeclared tolerance; retain the raw trace and report the failure. `sampled_peak_W` is only the
maximum recorded sample; claim a transient peak current/power bound only with suitable bandwidth and
an explicit uncertainty. Report absolute joules, mean watts, sampled or validated peak watts, warm
steady watts, wake latency/joules, standby/off watts and energy per scheduled task epoch with the
same task numerator/denominator. Use the same physical meter boundary for every arm of a
sensor-policy frontier and account for disabled sensors still physically installed. This makes the
comparison about the actual system, including regulator and interface overhead.

During sustained trials, sample ambient and board/CPU/accelerator/sensor temperature where
available, requested and measured frequency evidence, cooling state, supply voltage,
undervoltage/throttle flags and delivered quality/deadlines. A frequency request or Linux
`scaling_cur_freq` is not necessarily instantaneous silicon frequency ([Linux
CPUFreq](https://docs.kernel.org/admin-guide/pm/cpufreq.html)); Raspberry Pi `vcgencmd
get_throttled`, `measure_temp` and `measure_clock arm` provide additional platform evidence when
present ([Raspberry Pi documentation](https://www.raspberrypi.com/documentation/computers/os.html)).
Report time and fraction under throttling, minimum frequency evidence, temperature trajectory and
its relation to latency, drops and task quality. A throttle event is a measured failure mode, not a
reason to delete an unfavorable run.

For motion/vibration bench claims, use a calibrated actuator or replayed platform-motion profile
with a separate encoder/IMU reference and an accelerometer attached close to the camera/sensor
mount. State axes, anti-alias filtering, sample rate, mount and measured input
acceleration/attitude; compute band-limited RMS, peak and a windowed power spectral density (for
example Welch's method) with its frequency bands and window parameters. Report camera
angular/image-plane jitter, blur, calibration residual, frame loss and tracking quality against the
*same stimulus* with vibration on/off. A field-measured spectrum replayed by a shaker is a
controlled approximation and is labelled as such. Change in tracking quality is paired with actual
measured mount motion; actuator command or nominal motor RPM alone is not the delivered vibration.
When payload integration becomes a claim, measure the installed assembly including
cables/mount/regulator on a calibrated scale and record mass and center-of-gravity method; bench
computer watts or nominal battery capacity alone cannot predict flight endurance.

## 8. TrackEval adapter and upgrade policy

[TrackEval](https://github.com/JonathonLuiten/TrackEval) is the reference MOT evaluator once a
genuine multiple-object scenario exists. It is **not** the G0 operator-seeded SOT oracle or the
canonical frame/telemetry contract. The adapter converts validated annotations and predictions to a
pinned TrackEval input and records the upstream commit, Python/NumPy environment, configuration,
source/export hashes and output. The exact revision must pass an import-and-fixture smoke test in
its locked environment; an [upstream dataset
implementation](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/datasets/mot_challenge_2d_box.py)
contains `np.int` uses that conflict with the [NumPy 1.24 alias
removal](https://numpy.org/doc/stable/release/1.24.0-notes.html) unless fixed or pinned.

TrackEval scores the canonical MOT output irrespective of how many sensors produced it. Fusion
provenance, probability calibration, sensor cost and resource-policy decisions are evaluated by
separate versioned suites; HOTA does not validate a claimed covariance, existence probability or
energy benefit.

For the initial MOTChallenge-format adapter, each evaluated object class is exported in a declared
**per-class** run using the implementation's class-1 `pedestrian` slot only inside that export; the
real taxonomy and class ID remain in an audited row map. A multi-class aggregate is permitted only
when its aggregation rule and class composition are predeclared. The adapter explicitly disables or
replaces benchmark-specific distractor preprocessing. Canonical ignore regions are resolved by an
audited rule before export: match scored ground truth first, then ignore only remaining predictions
in reviewed ignore regions; log every affected row. If that rule cannot faithfully represent a
scenario, report `UNSUPPORTED` for this adapter. The [format
guide](https://github.com/JonathonLuiten/TrackEval/blob/master/docs/MOTChallenge-format.txt)
specifies one-based frame numbers, IDs and box positions; the export maps canonical zero-based
values to those rows. Golden fixtures compare exported text **byte for byte** with hand-written rows
as well as hand-audited metric values/invariants, because a consistent box shift on both sides can
leave IoU unchanged.

Fixtures include perfect tracks, misses, false positives, duplicate detections, ID switches,
absent/one-frame sequences, border boxes, classes, ignore cases and malformed inputs. An upstream
update is tested on those fixtures and a frozen representative corpus. New metrics or changed
defaults require explicit review and a new metric-suite version; historical results retain their
original evaluator. [SO-HOTA](https://arxiv.org/abs/2507.12832), designed for small-object tracking,
is a candidate **separate** suite in the relevant small-target scenario. It never silently replaces
ordinary HOTA or G0 SOT measures.

## 9. Offline advisory actions and later closed loop

`AdvisoryAction` is a timestamped, image-plane recommendation: `CENTER`, `HOLD`, `SEARCH`, `ABORT`
or `ABSTAIN`, with target instance ID, horizon, confidence and reason. G0/G1 have **no actuator
endpoint**. Historical video may test whether a recommendation agrees with a recorded operator
action when telemetry is aligned, whether a forecast matches the target's future image location **on
the operator's recorded path**, and whether the proposal violates a declarative scenario rule. These
are separate diagnostics. Agreement with the operator does not establish an optimal action, and a
forecast from the recorded path does not show what would happen under the module's action. Search
and abort after target loss are reported, including abstention; no policy is rewarded for unverified
closer approach or unsafe entry into a restricted zone.

G3 may begin with an action-dependent crop window inside a high-resolution wide recording. It is a
limited image-plane simulator: no unseen scene outside source FOV, parallax, object behavioral
response or other road-user reactions. It must reproduce the recorded path under logged operator
actions within a stated tolerance, model delay and actuator constraints, and mark trajectories that
leave supported source view as failures or `ABORT`, not exclusions. More complete simulators need
versioned vehicle/camera/environment and energy models. Simulation scores do not establish
real-world safety without independent field evidence.

## 10. Run artifacts and comparison dashboard

Command names define user-facing behavior; [current documentation](../impl/current.md#areas) states
which exist. They are subcommands of the installed `ss-track` entry point:

```text
ss-track import --source recording.yaml
ss-track corpus build --manifest corpus.yaml
ss-track corpus stage --corpus <id>
ss-track corpus verify --corpus <id>
ss-track corpus preview --corpus <id> --stream <id> --frame <index> --out sheet.png
ss-track annotate validate --corpus <id>
ss-track annotate derive --corpus <id>
ss-track hardware-probe --out host.json
ss-track hardware-measure --protocol hardware-trial.yaml --out trial/
ss-track hardware-select --requirements stand.yaml --trials <trial-ids> --out selection/
ss-track run --scenario scenario.yaml --module <local executable or adapter>
ss-track sensor-set evaluate --scenario <declared sensor-set scenario> # G2 front ends/subsets
ss-track fusion evaluate --scenario <fixed observation bundle>        # G2 fusion/analysis
ss-track tracker evaluate --scenario <fixed observation bundle>       # G2 tracker
ss-track system evaluate --scenario <installed-system scenario>       # G2 full pipeline
ss-track policy sweep --scenario <budgeted scenario>              # later resource suite
ss-track ingest --manifest external-run.yaml --events <event bundle>
ss-track compare --runs <run-a>,<run-b> --out report/
```

The scenario pins the domain pack/class taxonomy, corpus/split, frame-set hash, annotation and
eligibility-mask hashes, selection set, canonical decode/frame delivery, replay mode, module
configuration, metric suite, seed, camera/host profile where applicable, deadlines, sensor-absence
policy, energy boundary
and sampling protocol. A G1 or G2 hardware claim also pins the section 7.9 `HardwareTrial` protocol and
instrument/calibration revision. A G2 scenario additionally pins **one of the four evaluation
boundaries**, allowed inputs, upstream bundle/producer hashes, sensor opportunity profile, declared
feasible sensor subsets, calibration/clock versions and tolerances, fusion/tracker epochs,
association and missing-source policy, probability definitions and calibration revision. A resource
scenario pins the policy/action space, decision-time feature set, candidate-mode profiles,
false-alarm and quality constraints, peak and rolling budgets, workload and fixed-baseline sweep. A
compute-profile declaration additionally pins the workload's input shape/layout, precision, batch,
concurrency, requested backend and permitted partition/fallback, cold versus warmed interval and
comparison boundary. The runner assigns the run ID. Artifacts contain the manifest, input/output
hashes, raw event records, validation and fault reports, metrics with
numerator/denominator/exposure, environment, timing/resource/power evidence, per-encounter results
and frame-linked failure references. Hardware artifacts contain the protocol, physical boundary,
instrument/check records, raw sensor/power/reference traces and hashes, alignment/uncertainty
budget, sample gaps, validity decisions, per-trial metrics and paired-trial order; a plotted summary
cannot replace the raw evidence. Fusion artifacts include raw-source lineage, alignment/calibration
evidence, decisions made before acquisition, predicted versus actual costs, source availability,
posterior/calibration evidence and budget violations. Compute artifacts include the actual
kernel/ISA or tensor device/operator partition, runtime/driver/firmware and model/calibration
provenance, compilation/cache and transfer evidence, and profile deviations. A local HTML/JSON
report is G0's dashboard. Hosting and a shared service are outside the scheduled scope.

An **algorithm-only** accuracy comparison requires the same scenario pack and class map, corpus,
split, annotation, selection and mask, transforms, metric suite, evidence lane and input
representation. Within `FIXED_OBSERVATION_FUSION` and `FIXED_OBSERVATION_TRACKER`, input bundle
hashes, release schedule and upstream producer/configuration are identical. `SENSOR_SET_FRONT_END`
explicitly varies declared sensor/front-end sets under one pinned reference fusion rule and
separates an oracle observability ceiling from achieved fusion output. A separately labelled
**system-level modality-subset comparison** may change enabled sensors while holding the
synchronized encounter, independent task truth, observation path and scoring opportunities fixed;
modality sets, missingness and calibration are explicit factors. A **policy-level comparison** holds
raw available streams, decision opportunities, reference truth, hardware/workload and task
denominator fixed, while the ROI, rate, model, precision and consumed inputs chosen by each policy
remain explicit factors. Timing and energy comparisons additionally require a controlled
host/installed-sensor/workload cohort, comparable scheduler, shape/batch/concurrency and cold/warm
state, and **the same installed-system meter boundary** for sensor-policy arms; dispatch, backend or
sensor subsets are explicit comparison factors. A CPU-to-accelerator comparison can show a
quality-latency-energy trade-off on the same host/workload, but may not be labelled a like-for-like
kernel speedup when precision, model, pre/postprocessing or graph partition changed. Cross-device
results are stratified; an overall hardware-agnostic ranking is forbidden. The only cross-device
comparison is the unranked same-stimulus device evaluation in
[section 16.6](#166-device-bench-evaluation). The report
explains every refused comparison and always displays scorable exposure, class and object-size distribution,
uncertainty/calibration quality, source availability, module faults, backend fallback/profile
deviations, deadline and budget misses, and energy measurement quality. The hardware view shows
measured capture rate/drop cause, optical/temporal calibration, stage and end-to-end latency,
memory/I/O pressure, temperature/throttling, measured motion spectrum, total energy and uncertainty,
with instrument/trace links and `NOT_MEASURABLE`/`inconclusive` statuses. It distinguishes isolated
kernel/operator timing from full pipeline timing and never edits or recomputes source metrics.
Generated cases form their own slice, named by transform, and never merge with field encounters or
count toward an encounter minimum. A source whose completeness is unverified is listed. G2
shows **four separate panels** for sensor-set/front-end evidence, fixed-input fusion/analysis,
fixed-input tracking and full installed-system output; a component score is never displayed as a
whole-system score. Shareable exports require explicitly public input; missing visibility is
restricted, while local restricted analysis remains available. The local report may display
detection/track quality at fixed false-alarm burden and coverage,
reliability/risk-coverage views, and a quality-latency-energy Pareto view for a compatible cohort,
with no hidden composite score.

## 11. Scenario safety, privacy and data governance

Each scenario pack declares the object classes and local operational constraints that matter for
collecting and interpreting evidence. For protected habitats, preserve non-interference rules,
disturbance observations, restricted nest/den/roost locations and independently approved
distance/stop criteria. For roads and parks, preserve applicable privacy and public-space operating
rules, including handling of identifiable people and location traces. These are scenario rules, not
labels to replace with a generic `object_response` score. A visible absence of reaction from a
living subject is not proof of no impact; a benchmark score never grants permission for autonomous
vehicle operation or closer approach.

G0/G1 use already authorized recordings and controlled non-sensitive bench objects. A living-subject
scenario may record `none_observed`, `possible`, `observed` or `unknown` behavioral response, with
reviewer notes; `none_observed` means only that the available evidence showed no response. Such
labels are not a universal safety metric. Sensitive historical clips may be scored only under their
rights/policy and must not be promoted as desirable operating examples. Public derivatives redact or
coarsen GPS tracks, subtitles, EXIF, faces/license plates when required, and other identifying or
location-bearing metadata; raw video may be withheld. Every derivative retains rights, retention,
sharing and access rules.

Audio streams can capture identifiable speech or bystanders, and active radar has site- and
jurisdiction-specific spectrum and operating conditions. Their use requires scenario-specific
collection, access and operating rules before a bench or field profile is opened. A modality is not
activated merely because the benchmark supports its schema; absent equipment or permission is
recorded as `UNSUPPORTED` for that profile.

Any new field trial involving protected wildlife, people, traffic or public space requires the
relevant site, safety, privacy and vehicle-operation approvals, a trained operator and
scenario-specific stop criteria. The [bird-drone
meta-analysis](https://esajournals.onlinelibrary.wiley.com/doi/10.1002/fee.2809) illustrates why
observed responses and distances are context dependent in one wildlife scenario; it supplies no
universal safe distance for other objects or sites. The dashboard emphasizes performance at a
declared object pixel extent and does not reward closest approach.

### Measurement-only scope

ss-track measures detection, tracking and energy for monitoring, warning and situational awareness.
It does not evaluate or tune a system whose tracker output steers, cues or triggers a weapon,
interceptor or other effector, and it publishes no engagement metrics. A **sensitive device** is any
system sold for defense, security, counter-drone or law-enforcement use, or subject to export
control. Results on a sensitive device stay restricted unless the project owner releases them.

## 12. Unscheduled design candidates

These candidates are design input, not implementation commitments. Scheduling one requires a
[capability registry](#capability-registry) entry and plan tasks with declared acceptance gates.

| Capability | How it is evaluated |
| --- | --- |
| `scalar-vector-cpu-kernels` | Scalar C++20 reference and optional Neon/SVE/x86/RISC-V paths pass conformance and measured quality-latency-energy comparison |
| `tensor-compute-backends` | Pinned CPU reference and optional accelerated graph pass support, partition/fallback, precision, task-quality and end-to-end cost fixtures |
| `external-event-ingest` | Second-host contract tests, frame match and clock-validity cases |
| `advisory-diagnostics` | Recorded-path and operator-agreement diagnostics remain separate; no G0/G1 actuation path |
| `recognition-state` | Scenario-specific class/state labels, class probability and abstention coverage with negative-result tests |
| `resource-aware-sensing` | Causal policy decisions, fixed-configuration and VOI/event-trigger comparators, task quality at energy/deadline budgets and measured sensor-plus-compute cost |
| `stereo-range` | Independent distance reference, calibration/synchronization uncertainty, range error and unsupported-mode coverage |
| `closed-loop-simulation` | Action changes the next supported observation; out-of-support action fails or aborts; energy model declared |

## 13. Acceptance and negative-result matrix

| Gate | Required test or artifact | Expected result |
| --- | --- | --- |
| G0a input validity | Truncated/zero-length media, wrong hash, non-increasing PTS, selection past sequence end | Structured rejection or time-metric unavailability; never a fabricated score |
| G0a scoring oracle | Oracle emits correct target/proposals on all scorable frames | Lock coverage 1 and motion event recall 1 on eligible fixtures, with zero operator-burden proposals |
| G0a reference tracker | Deterministic operator-seeded fixture with perfect observation, one miss, moving distractor, occlusion and re-entry; rerun with the same seed and binary | Exactly one result per scheduled frame; hand-audited track/lost transitions and metric denominators repeat; a predicted stale box cannot masquerade as a measured detection |
| G0a null | Module acknowledges every frame but emits no target or proposals | `VALID` zero lock coverage and zero motion recall, not `NOT_SCOREABLE`; horizon loss when the fixture is long enough |
| G0a anti-gaming | Whole-frame boxes; oracle selectively drops scorable shake frames; crash mid-episode | Whole-frame boxes fail scale check; dropped frames lower coverage; crash is `MODULE_FAULT` with remaining scorable input missed |
| G0a identity and absence | Proposal/track on another labelled instance; selected target leaves view | Identity error; absence/re-entry diagnostics and exposed unscorable time |
| G0a comparability | Same-version rerun; different labels, seed, class map or mask versions | Repeatability/noise recorded; incompatible comparison refused |
| G0b development decision | At least 10 independent encounter groups, three same-version runs, paired A/B results | Separate metric statuses, encounter interval and noise floor; otherwise `insufficient_data` |
| G1 CPU dispatch, when a vector path is claimed | Scalar reference and each claimed vector build; absent-feature and forced-fallback fixtures; odd widths/strides, tail lanes, alignment, overflow and FP cases | Correct platform/OS feature dispatch and declared exact/tolerant numerical checks; unsupported ISA never executes; effective SVE vector length is recorded if SVE is used |
| G1 tensor backend, when introduced | Pinned CPU reference for framework-owned graphs; representative compile/run; unsupported operation/shape, absent device, partial graph assignment, pre-run and frame-attributed fallback, post-run unlocalized fallback, threshold/precision drift and asynchronous device-fence fixtures | Supported graph path and actual partition are proved; unsupported or mixed-device mode is explicit; undeclared fallback follows section 7.3; tensor and task-level tolerances and quality are reported |
| G1 real-time | Normal paced runs under concurrent load; PREEMPT_RT profile only when claimed and available, with the same workload and compute variant | Deadline misses and tail latency include queue/transfer/synchronization cost with scheduler, thermal and clock evidence; unavailable PREEMPT_RT is `UNSUPPORTED` only for that optional profile |
| G1 hardware protocol and instruments | Predeclared section 7.9 protocol; hand-calculated constant/pulsed-power, sample-gap and clock-drift fixtures where those quantities are claimed; instrument identity, calibration, markers, trace hashes and uncertainty budget for **each claimed quantity** | Raw evidence reproduces the claimed derived estimates; saturated or misaligned measurements become `NOT_MEASURABLE` for the affected quantity; no energy meter is required when energy is unclaimed; uncertain paired differences are `inconclusive` |
| G1 capture, optics and stereo characterization | Locked mode/ISP and measured chart/target at declared distances; source frame IDs or explicit `upstream_drop_unknown`, independently measured clock marker, two-camera skew/stereo range when claimed | Delivered FPS, supported drop/duplicate counts, object extent, SFR/contrast and clock uncertainty are separate from requested FPS/pixel count; stereo geometry/error and controlled-target range are hardware/bench evidence, while scene-level object range and fusion-quality claims belong to G2 |
| G1 compute, thermal and vibration | Sustained joint-stream load, cold/warm runs, instrumented mount-motion profile, memory/I/O/CPU traces, temperature/voltage/frequency/throttle evidence | Queue/deadline/memory and actual mount PSD/RMS/quality changes are reportable; nominal USB/CPU speed and actuator command do not substitute for delivered measurements; throttled runs remain visible |
| G1 bench and energy | Actual camera and controlled object with independent trace; stationary and motion runs; cold and warmed compute intervals; calibrated meter when an energy claim is made | Mode, light/exposure, object extent, drops and full-pipeline timing always reported; joules and meter boundary reported only when measured; isolated kernel/operator results are separately labelled; uninstrumented energy is `NOT_MEASURABLE` |
| G1 external events | Matched/mismatched frame inputs; synced/unsynced host clocks | Perception scoring only on matched inputs; cross-host latency only with adequate clock evidence |
| G1 two-camera alignment smoke test, when claimed | Joint-mode probe, independent alignment target, calibrated transform and clock; time/geometry and source-ID fixtures | Joint-mode limits and alignment uncertainty are recorded; stale/misaligned input cannot create a confident fused range or identity. Quantitative fusion-quality claims use G2 |
| G2 TrackEval | Byte-exact per-class MOT export and hand-audited perfect/miss/FP/ID-switch/ignore fixtures | Pinned metrics; changed upstream output requires new suite version |
| G2 recognition/state | Unknown subtype, too-small object, no valid state label and confident wrong-class fixture | Explicit abstention or `NOT_SCOREABLE` with coverage and class-probability calibration; no fabricated fine-grained score |
| G2 `SENSOR_SET_FRONT_END` | Modality-specific positive/negative/coverage fixtures; feasible single, paired, all-installed and leave-one-out sets on identical encounters with one pinned reference fusion rule | Per-sensor recall, false alarms, latency and uncertainty plus achieved set-level gain/loss are reported at fixed burden; uninstalled or infeasible sensor sets are `UNSUPPORTED`; label-derived oracle union is visibly an upper-bound diagnostic |
| G2 `FIXED_OBSERVATION_FUSION` | Two versions consume byte-identical hashed observation bundles with fixed calibration, order, availability and epochs; correlated duplicates, contradictory and no-detection states | Association, false merge, dedup, existence/class calibration, abstention, faults and stage cost are isolated; a changed front end forces a new cohort; future or forbidden raw data access fails conformance |
| G2 `FIXED_OBSERVATION_TRACKER` | Reference and candidate consume byte-identical frozen single/fused observations and seed; crossing, misses, occlusion, re-entry and prediction-only fixtures | SOT/MOT, identity, loss/re-entry, state/calibration, coverage and tracker-stage timing are isolated; every scheduled epoch is acknowledged; hidden detection from raw pixels fails this boundary |
| G2 `FULL_INSTALLED_SYSTEM` | Complete sensor-plus-compute path on a named installed configuration, stationary/motion/vibration and sensor-outage trials, matched encounters, balanced A/B order and calibrated same-boundary meter when claiming energy; include active/standby/off/wake transitions | Raw-to-output quality, false alarms, availability, deadlines, full-system joules, sampled/validated peak and rolling limits with uncertainty, and paired quality-latency-energy frontier are reported from the same trials; no component causal attribution from this result alone |
| G2 fusion provenance and timing | Two cameras plus optional registered audio/radar/thermal/event/contact/context fixtures; clock skew, out-of-order/stale/duplicate source, missing/negative/out-of-view source, calibration error and conflicting or correlated evidence | Source lineage is exact; no future event enters a decision; false merge/duplicate output is counted; missing/out-of-view is not treated as negative; unsupported geometry cannot yield a confident cross-modal identity |
| G2 source versus policy absence | Valid `no_detection`, capture/clock failure, candidate `disabled_by_policy`, and frozen reference `unknown` fixtures | The first is a negative sensor observation, the next two retain scorable task exposure with distinct reasons, and only the last may yield `NOT_SCOREABLE` for the affected task; pre-run impossible joint mode is `UNSUPPORTED` |
| G2 probability calibration | Known-outcome probability fixtures and a disjoint calibration split; confident false association, localization region and abstention cases | Proper-score, reliability, coverage/sharpness and risk-coverage computations match hand results; TrackEval output alone never certifies uncertainty |
| G2 adaptive policy and energy | Each single-sensor/fixed-rate/always-on/time-shared baseline, skip-heavy policy, thermal/deadline/peak-power/rolling-energy fixtures and a measured sensor-on/off profile for an energy claim | Fixed task denominator and false-alarm burden expose skipped detections; predicted/realized costs and violations are visible; offline quality/process-latency gains are qualified to recorded inputs; energy savings from stream suppression alone are `NOT_MEASURABLE`, and energy-efficiency claims require the predeclared measured paired frontier |
| G2 range | Uncalibrated stereo, radar mode without calibrated range or absent independent distance reference | `UNSUPPORTED` or `NOT_SCOREABLE` with coverage and uncertainty; no range inferred from modality name |
| G3 closed loop | Candidate actions alter future view; action leaves simulator support | Model-bounded score; unsupported path fails or aborts, not excluded |
| Paced frame release | Fixture module attempts to read a future frame | Read fails; the run reports a conformance failure |
| Optional thermal trial | Identical frames at two chip temperatures; frequency-capped cool arm; load-calibrated baseline; fresh state; randomized order | Mechanism supported only if all four conditions hold; no throttling is `not_tested`; a negative result is retained |
| Optional cohort rank | Fixture cohorts: median-run choice, every-run floor, anchored tiers, fault penalty, null row, fewer than three qualifying projects, cohort-key mismatch | Expected rank, tier, `inconclusive` or refusal; no rank published under the minimum; null row is never subtracted |
| Export boundary | Restricted or unmarked bundle passed to a shareable export | Export refuses without leaking values; local restricted analysis remains available |
| Hardware selection | Fixture configurations against a stated budget; datasheet-only option; shared rail | Only measured configurations are chosen; none qualifying is the stated result; a shared rail stays shared |
| Optional device bench | No output path; matched and mismatched stimulus/reference fixtures across hosts | `UNSUPPORTED` or refused comparison where appropriate; valid cases remain unranked |

A negative finding such as "the object cannot be localized at this pixel extent," "this camera pair
cannot sustain the declared mode," "PREEMPT_RT did not improve the tail deadline," or "energy is not
measurable with the available meter" is a valid, traceable project result. Passing a software
fixture is not evidence of field safety or a specific detection range.

## 14. Research and platform basis

| Primary source | Useful element | Limit for this product |
| --- | --- | --- |
| [TrackEval](https://github.com/JonathonLuiten/TrackEval) and [HOTA](https://arxiv.org/abs/2009.07736) | Reference MOT metrics and detection/association decomposition | Does not define operator seed, camera time, telemetry, energy or G0 SOT |
| [VOT long-term methodology](https://arxiv.org/abs/1906.08675) and [OxUvA](https://arxiv.org/abs/1803.09502) | Presence/absence and re-detection evaluation | Different capture conditions; use method, not transferred performance |
| [LaSOT](https://openaccess.thecvf.com/content_CVPR_2019/papers/Fan_LaSOT_A_High-Quality_Benchmark_for_Large-Scale_Single_Object_Tracking_CVPR_2019_paper.pdf) | SOT success/precision and long-sequence stress views | No onboard timing or energy contract |
| [UAVDT](https://openaccess.thecvf.com/content_ECCV_2018/papers/Dawei_Du_The_Unmanned_Aerial_ECCV_2018_paper.pdf) and [VisDrone](https://arxiv.org/abs/1804.07437) | Mobile-camera motion, small-object and attribute slices | Different class mix and dataset rights |
| [SMOT4SB](https://arxiv.org/abs/2507.12832) | Small-bird point/dot similarity and SO-HOTA candidate | Domain-specific MOT; not a universal SOT or safety suite |
| [DAgger](https://arxiv.org/abs/1011.0686) | Learner actions change future observations | Motivates lane separation; does not validate a simulator or policy |
| [Attention and Anticipation](https://arxiv.org/abs/1610.03344) | Task-conditioned resource selection | Navigation performance gains do not transfer to object perception |
| [SLAMBench](https://arxiv.org/abs/1410.2167) and [MLPerf Tiny rules](https://github.com/mlcommons/tiny/blob/master/benchmark/MLPerfTiny_Rules.adoc) | Paired accuracy/runtime/energy evaluation and declared measurement procedure | Different task, device and energy boundary; use methodology, not scores |
| [NIST uncertainty guidance](https://physics.nist.gov/cuu/pdf/tn1297.pdf) and [MLPerf power policy](https://github.com/mlcommons/inference_policies/blob/master/power_measurement.adoc) | Traceable uncertainty, paired power/performance trials and an explicit system boundary | Instrument calibration, sampling and uncertainty must be set for this system; neither source supplies a measured joule value |
| [ISO 12233](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso%3A12233%3Aed-5%3Av1%3Aen), [EMVA 1288 Linear/General](https://www.emva.org/standards-technology/emva-1288/emva-standard-1288-downloads-2/) and [V4L2 buffer timestamps](https://docs.kernel.org/userspace-api/media/v4l/buffer.html) | Optical SFR, appropriately scoped camera characterization and driver timestamp semantics | Pixel count and buffer time alone do not establish delivered detail or glass latency; ISP output is not automatically a raw-sensor property |
| [NIST event-camera latency](https://www.nist.gov/publications/pixel-latency-measurements-event-cameras), [NIST 3D-imager range characterization](https://www.nist.gov/publications/characterization-range-performance-3d-imaging-system-nist-tn-1695) and [avian radar validation](https://pmc.ncbi.nlm.nih.gov/articles/PMC3774623/) | Physical reference stimuli and independently validated latency, range and detection probability | Their instruments and target conditions are different; no reported range or error transfers to this hardware |
| [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), [`perf_event_open`](https://man7.org/linux/man-pages/man2/perf_event_open.2.html), [timerlat](https://docs.kernel.org/trace/timerlat-tracer.html), [CPUFreq](https://docs.kernel.org/admin-guide/pm/cpufreq.html) and [Raspberry Pi OS diagnostics](https://www.raspberrypi.com/documentation/computers/os.html) | Reproducible CPU/memory/I/O diagnostics, PMU caveats, scheduler noise and throttling evidence | Counters and clock settings diagnose bottlenecks; they do not replace measured application latency or electrical joules |
| [Sensor-failure benchmark](https://arxiv.org/abs/2503.18445) and [radar-camera fusion calibration study](https://openaccess.thecvf.com/content/CVPR2025/papers/Luu_RC-AutoCalib_An_End-to-End_Radar-Camera_Automatic_Calibration_Network_CVPR_2025_paper.pdf) | Missing/noisy-modality and extrinsic-alignment test design | Their sensors, scenes and accuracy figures do not establish performance here |
| [Context-aware asynchronous sensor modelling](https://arxiv.org/abs/2603.15137) and [out-of-sequence measurement processing](https://ieeexplore.ieee.org/document/1039398/) | Field-of-regard/context-dependent detection probability, clutter and bounded delayed-event handling | Their tracking gains do not transfer to the scenario without measured sensor models and timing |
| [JPDA](https://doi.org/10.1109/JOE.1983.1145560), [MHT](https://doi.org/10.1109/TAC.1979.1102177) and [covariance intersection](https://doi.org/10.1109/ACC.1997.609105) | Optional ambiguous-association and unknown-correlation state-fusion methods | These methods are candidate implementations, not universal fusion of raw detector scores or a mandatory software dependency |
| [Energy-aware sensor scheduling](https://arxiv.org/abs/1009.2997) and [event-triggered estimation](https://is.mpg.de/uploads/publication_attachment/attachment/322/trimpe-TAC14b.pdf) | POMDP/approximate and transparent event-triggered acquisition comparators | Their cost models and task outcomes must be re-estimated for the actual installed sensors and object task |
| [Rotational stereo field tracking](https://jeb.biologists.org/content/jexbio/218/16/2496.full.pdf), [event-based flying-object dataset](https://openaccess.thecvf.com/content/CVPR2025W/EventVision/papers/Magrini_EV-Flying_an_Event-based_Dataset_for_In-The-Wild_Recognition_of_Flying_Objects_CVPRW_2025_paper.pdf) and [thermal bird observations](https://pmc.ncbi.nlm.nih.gov/articles/PMC4705634/) | Candidate optical/event/thermal sensor roles and small-object failure slices | Different optics, mounts and environments do not establish 100 m performance for the proposed compact platform |
| [Flight-call microphone array](https://pmc.ncbi.nlm.nih.gov/articles/PMC5513243/), [K/W-band bird radar measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC6255807/) and [wild-bird PIR camera traps](https://pmc.ncbi.nlm.nih.gov/articles/PMC6065333/) | Acoustic, radar and PIR observation models, with distinct range/coverage and negative-evidence semantics | Calling, RF return and thermal zone crossing are not interchangeable sightings or proof of the same object; transmitter power is not system power |
| [ToF module specification](https://ai.benewake.com/en/resources/technical-documents/tfmini-s-datasheet/), [ultrasonic sensor specification](https://maxbotix.com/products/mb7566), [bird perch load-cell experiment](https://pmc.ncbi.nlm.nih.gov/articles/PMC12795351/), [geophone footfall experiment](https://besjournals.onlinelibrary.wiley.com/doi/full/10.1002/2688-8319.70072) and [Motus tagged-bird network](https://motus.org/resources/how-motus-works/) | Near-field, contact and cooperative-only sensor scope | Commodity short-range or contact/tag evidence cannot be generalized to untagged free flight at 100 m |
| [Object-detection confidence calibration](https://arxiv.org/abs/2004.13546), [selective-classification evaluation](https://arxiv.org/abs/2407.01032) and [uncertainty-aware MOT measure](https://arxiv.org/abs/2108.04619) | Distinct probability, risk-coverage and posterior-aware scoring concepts | Posterior-aware scores require defined outputs and suitable labels; they do not follow from arbitrary confidence fields |
| [DCASE audiovisual sound-event task](https://dcase.community/challenge2024/task-audio-and-audiovisual-sound-event-localization-and-detection-with-source-distance-estimation) and [IEEE radar band designation](https://technav.ieee.org/topic/microwave-bands/) | Separate acoustic event/location tasks and W-band terminology | Neither proves object identity or range from a generic microphone/radar module |
| [Linux PREEMPT_RT](https://docs.kernel.org/core-api/real-time/index.html) and [kernel configuration guidance](https://docs.kernel.org/core-api/real-time/kernel-configuration.html) | Scheduler profile and preemption checks | Does not bound arbitrary camera, driver or accelerator paths |
| [Arm64 HWCAP](https://docs.kernel.org/arch/arm64/elf_hwcaps.html), [Linux SVE user API](https://docs.kernel.org/arch/arm64/sve.html) and [Arm Neon intrinsics](https://developer.arm.com/documentation/ihi0073/latest/) | User-space ISA dispatch and per-thread SVE vector-length behavior | Extensions and benefit must be checked on the actual host |
| [Linux x86 feature flags](https://docs.kernel.org/arch/x86/cpuinfo.html) and [RISC-V hardware probing](https://docs.kernel.org/arch/riscv/hwprobe.html) | OS-enabled instruction discovery on other host families | Advertised hardware or compile flags alone are insufficient |
| [Linux Arm SME user API](https://docs.kernel.org/arch/arm64/sme.html) and [x86 XSTATE/AMX](https://docs.kernel.org/arch/x86/xstate.html) | Optional CPU matrix state and permission checks | Availability and usefulness are host/runtime specific |
| [ONNX Runtime architecture](https://onnxruntime.ai/docs/reference/high-level-design.html) and [OpenVINO device querying](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/query-device-properties.html) | Graph partition/fallback and candidate device discovery | A listed provider/device does not prove graph coverage or speed |
| [Raspberry Pi 5 specification](https://www.raspberrypi.com/products/raspberry-pi-5/) | Cortex-A76 reference host | Does not imply SVE, an NPU or a measured speed/energy gain |

External datasets are candidate material only after license, annotation semantics, privacy and
train/test overlap are checked. Benchmark claims rest on governed recordings and measured trials,
not on transferred performance numbers.

## 15. Owner inputs and change control

The G0a design is implementable with an authorized private development corpus. The following inputs
are required **before the named later claim or gate**, rather than blocking G0a:

| Input | Required before |
| --- | --- |
| Scenario packs, class taxonomy, recording rights/retention, locked-test custodian and access policy | Creating a locked test or shared dashboard for each domain |
| Annotation reviewers and disagreement authority | Freezing G0 labels; a small two-reviewer set is the G0 default |
| Operator-relevant motion response window, onboard deadlines and stress workload | Locked motion evaluation or real-time claim |
| Camera/lens modes and actual Raspberry Pi Zero/Rockchip revisions | Declaring those hardware profiles supported |
| Versioned section 7.9 protocol, independent target/trajectory reference, optical/time calibration fixtures, instrument identities/checks, declared workload and uncertainty/decision margin | Opening a G1 hardware accuracy, latency, optical or sustained-performance claim |
| Joint sensor modes, capture and arrival clocks, field-of-regard/detectability profiles, calibration/transform uncertainty, and independent cross-sensor identity labels | Opening a claimed multi-sensor fusion or range suite |
| Actual installed sensor inventory, capability/coverage and active/standby/off/wake profiles, independent modality labels and a feasible-subset design | Opening G2 sensor-set/front-end evaluation; an uninstalled family remains a schema-supported candidate only |
| Modality-specific collection/operating rights and installed active-emitter, audio, radar, contact or tag capabilities | Opening the corresponding physical sensor profile |
| Target CPU/OS feature probe, compiler and vector implementation | Declaring an optional vector compute profile supported on that host |
| Target tensor model, device, runtime/driver/firmware, precision and supported shapes/operators | Declaring an optional tensor compute profile supported on that host |
| Calibrated power meter, fixed electrical boundary, synchronized time marker, raw traces and uncertainty budget | Energy-efficiency claims or cross-variant energy comparison |
| Candidate action profiles, false-alarm/coverage target, deadline, peak and rolling energy/thermal budgets, calibrated sensor visibility/detection/cost models, and disjoint policy/calibration data | Claiming adaptive sensing improves quality or energy against a fixed-mode frontier |
| Acceptable range-error tolerance | Opening stereo-range evaluation |
| Local habitat/public-space/road constraints, response-label governance and approvals | Any new field operation or safety claim |
| Frozen measurement protocol, floors, decision margin and maximum interval half-width | Optional cohort ranking |
| A chip-temperature rig, measured throttle onset, declared schedule and deadline | Opening the optional thermal mechanism claim |
| Recorded measurement access and data-sharing permissions | Physical device trials and explicitly shareable exports |

Changes to taxonomy, labels, split, matching threshold, metric formula, TrackEval revision, decoder,
clock policy, sensor set/opportunity profile or calibration, fixed-input bundle, evaluation
boundary, hardware measurement protocol, energy boundary or real-time workload create a new relevant
version and comparison cohort. A new instrument or calibration record remains in the trial
provenance and triggers the section 7.9 equivalence/uncertainty check before joining an existing
measurement cohort. A model, quantization/calibration, precision, compute backend,
operator-partition, preprocessing, fusion rule, probability calibrator, action space, cost predictor
or budget policy change creates a distinct variant and, when output semantics or metric validity
changes, a new relevant comparison cohort. Previous run artifacts remain immutable and readable. A
newly discovered capability first changes this living specification with its boundary and
negative-result rule, then the capability registry and forward plan; implementation and
current-state documentation follow.

## 16. Benchmark extensions, hardware selection and reference sensor mesh

The project has two goals: correct benchmarks, and a reference sensor mesh object-tracking
implementation. One engine serves both through reproducible, inspectable evidence bundles.
This section defines the additional capabilities and is normative for them. The rationale is in the
[engine design](perception-bench-engine.md), and hardware needs are in the
[test-stand requirements](test-stands.md).

Terms used in this section:

- A **run** is one pass of one module version over the scored segments at one chip set-point, in a
  fresh container.
- A **block** is one cool run and one hot run of the same module version, in randomized order.
- A **row** is one module version in one cohort.

### 16.1 Cohort ranking

`benchmark-ranking` optionally computes local rankings inside one matched cohort. It compares
declared module versions on one selected host, metered at its power input, on one authorized workload,
in paced `OFFLINE_REPLAY`. It claims algorithm behavior on that host, not finished-system, held-out
or field performance. It is not required for M1-M3 acceptance. Local comparison and hardware
selection remain useful when no ranking is possible.
The cohort key is the scenario hash (pack, class map, corpus, split, annotation, selection, mask,
transforms and input representation), metric suite, evidence lane, execution schedule and frame
deadline, host profile, physical meter boundary, chip set-points and rules version. One contract
function derives it, and any difference refuses the comparison.

The measurement protocol is frozen before candidate comparison runs:

- **Workload rights:** the workload permits the intended analysis and recorded access.
  Shareable exports additionally require permission for every included artifact; private development
  data does not become public because it was scored.
- **Quality:** encounter-aggregated observable lock coverage `C_j` from
  [section 6.1](#61-operator-selected-tracking-sot-v2-dev), scored in the hot run by a suite named
  `sot-paced-v1`. A result after its frame deadline, or a dropped frame, is a miss. The G0 thresholds
  remain engineering defaults.
- **Ranked energy:** `E_[a,b]` from [section 7.9.4](#794-electrical-power-thermal-state-and-motion),
  between the marked first and last scheduled frames of the hot run, divided by scheduled frames.
  Scheduled and emitted counts stay beside it.
- **Runs:** the rules declare an odd number of blocks, at least three, and every run is kept. The row
  comes from the hot run with median `C_j`. With an even number of valid hot runs it uses the lower of
  the two middle runs, and a tie takes the run with higher ranked energy.
- **Floor:** the lower bound of the 95% encounter-cluster interval clears the floor in every valid hot
  run. Otherwise the row is `inconclusive`. The bootstrap seed and resample count are frozen, so the
  interval recomputes exactly. A predeclared cap on false continuation and a minimum scorable exposure
  also apply.
- **Energy interval:** the ranked value with its expanded uncertainty from
  [section 7.9.1](#791-common-trial-design-and-uncertainty), combining the meter budget and the
  spread between hot runs.
- **Order:** sort by ranked energy. The lowest row leads a tier. A row joins if its energy interval
  overlaps the leader's interval widened by the margin, and the next row starts a new tier. The
  margin is the larger of baseline rerun noise and combined meter uncertainty, frozen with the rules.
- **Faults:** a `MODULE_FAULT` run shows the fault rate and moves the row down one tier. A row in the
  last tier stays there with its fault shown. Throttling is measured behavior, not a fault.
- **Invalid runs:** an invalid run stays on record with one replacement. A repeat undervoltage after
  the supply passes its known-load check counts as a fault. Fewer than three valid hot runs means not
  ranked.
- **Sample:** 10 independent encounter groups is the minimum, not evidence of generalization. A pilot
  on baselines measures interval width, and groups are added until a frozen maximum half-width holds.
- **Baselines:** each cohort shows an unranked null-module row, never subtracted, and ss-track's own
  modules are unranked baselines. Candidates, baselines and the null module use one container path.
- **Diagnostic column:** `C_j` divided by ranked energy is a secondary diagnostic under
  [section 7.5](#75-controlled-bench-and-energy-measurement). It never sets a rank or a pick.
- **Picks:** lowest energy above the floor, highest `C_j`, and smallest cool-to-hot loss, from ranked
  rows only.
- **Snapshots:** each local report is an immutable versioned snapshot with fixed ranks. New
  inputs or corrected calculations create a new snapshot; old artifacts stay readable.
- **Minimum:** ranking needs at least three distinct algorithm lines passing every condition.
  The protocol selects a version/configuration per line before measurement. Multiple versions of one
  algorithm never inflate this count; their pairwise development comparisons remain available.

Reproducibility has three levels. **Recompute** rebuilds scores from retained traces and applies to
every row. **Re-run** repeats open software on the same host class within a declared tolerance, using
recorded module recipes and pinned image digests. **Re-measure** repeats the hardware measurement
with a calibrated meter, where the hardware can be obtained.

Boundary: the software ranks only a declared development cohort. Known workloads can be tuned to;
candidate choice limits generalization. Scoring reads saved bundles only. Public enrollment,
commercial terms, moderation, site hosting and publication are outside this capability.

Evaluation: fixture cohorts produce expected rank, tier, `inconclusive` or refusal; a second process
recomputes byte-identical scores. Below the minimum, every row is shown unranked. Recompute and
Re-run can be tested using the reference baseline even if no candidate qualifies for ranking.

### 16.2 Paced thermal trial

`paced-thermal-trial` tests whether tracking quality changes with the host's thermal state. The same
labelled segments run at a declared cool and a declared hot chip temperature. The hot set-point is
declared from the measured throttle onset of the reference host, so the hot run reaches the throttled
state. A closed-loop rig holds chip temperature through each scored segment. Its control runs off the
host, its power stays outside the energy boundary, and the host adds only a low-rate temperature and
frequency log whose cost lands in the null-module row.

Each run starts in a fresh container with no retained module state and a dropped file cache, and the
runner warms its own frame store before the timed interval. Order is randomized within blocks, and
setup energy is reported apart from ranked energy.

The hypothesis is that throttling causes missed deadlines, missed deadlines cause lost tracks,
and quality falls. It is tested on ss-track baselines before candidate comparison protocols freeze.
They include a
load-calibrated baseline whose cool-run compute sits near the frame deadline under a declared load
setting, because a light tracker with spare time shows no loss whatever the heat does. A result on
that baseline shows the mechanism, not any tracker's behavior. The hypothesis is supported on a workload
only if all four conditions hold:

1. Cool and hot runs score identical frames.
2. Hot `C_j` is lower than cool `C_j`, beyond the rerun noise floor of
   [section 6.3](#63-comparisons-and-decision-status).
3. A cool run with frequency capped at the hot run's measured frequency reproduces the loss within
   that noise floor. This control separates frequency from temperature.
4. Frequency evidence from [section 7.9.4](#794-electrical-power-thermal-state-and-motion), deadline
   misses and drops line up with the loss.

Candidate reports show measured cool-to-hot change without assuming the mechanism generalizes.

Boundary: it runs only in paced execution, because lockstep replay cannot show the effect. It does
not show a module's own heating effect, and a mobile scenario pack discloses that a still bench lacks
in-flight airflow and battery sag.

Evaluation: hand-audited cool, hot and capped fixtures on identical frames, then a live baseline run.
A hot run with no throttling evidence reports `not_tested`. Valid negative results are no change
above noise, or a capped arm that does not reproduce the loss. Both are documented results.
This optional experiment does not gate host selection, the reference mesh or basic energy evidence.

### 16.3 Module reproducibility

`module-contract-runner` owns pinned module recipes, image digests, declared configurations and
license notices for the reference, null and candidate modules. Adapters and third-party dependencies
stay under `modules/`, outside the core package lock. The same isolation and frame-release path
applies to every module. Host checks use synthetic frames to verify schema, input isolation and
whether the declared schedule can be sustained; passing them is not quality or energy evidence.

Boundary: recipes and conformance are software deliverables. No mandatory external entry count,
release-age filter, public participation policy, vendor recruitment or registry hosting is required
for the benchmark or mesh to work.

Evaluation: a recorded recipe/digest identifies the measured executable and can be used in a fresh
environment. A missing image, incompatible host or license restriction is an explicit unavailable
or unsupported result, never silently replaced by a different executable.

### 16.4 Hardware selection

`hardware-selection` turns software needs into documented hardware choices. Requirements come from
the benchmark and the reference tracker, and they are listed per test stand in the
[test-stand requirements](test-stands.md). A person shortlists candidates from published
specifications. Before acquisition, record versioned requirements, acceptance tolerances and
measurement precision from the software workload. Candidates are characterized against independent
references before final selection, then tested in simultaneous modes. Requirements include task
coverage/quality, clock/geometry uncertainty, latency/loss, driver/interface support, storage and
throughput as well as average watts, watt-hours per task, peak watts and thermal limits. The selection
record names the chosen configuration, rejected alternatives with reasons, evidence hashes and
what stayed unmeasured.

Each candidate also gets an energy ledger. Total energy is measured at the declared boundary,
subsystems are itemized only where a rail or on/off mode is separately measurable, and shared rails
stay shared. Datasheet-only options are listed as unmeasured and are never chosen as if measured.

The first meter and host are a declared bootstrap, with specifications distinguished from
known-load and harness checks. A single available candidate is provisional, not proof of comparative
selection. No qualifying candidate, insufficient precision or missing required evidence is a valid
result. Changes to requirements or installed configuration create a new decision revision.

Hardware work returns machine-readable profiles/calibration, raw evidence hashes and a documented
selection to software development. Financial approvals and supplier administration stay outside the
repository; test-stand requirements and measured suitability remain here.

Boundary: selection compares measured configurations for this project's stands. It makes no
prediction or simulation, no general buying recommendation, no component attribution and no public
ranking.

Evaluation: fixture configurations against a stated budget, with only measured configurations
chosen. Valid negative results are no configuration qualifying, `NOT_MEASURABLE` for an inaccessible
boundary, and a stand requirement that nothing can meet, which returns to this specification.

### 16.5 Reference sensor mesh

`multi-source-reference-tracker` is the project's reference implementation: sensor front ends, typed
observations, event-time late fusion and track maintenance on one installed sensor set. It uses the
contract in [section 5](#5-module-contract-execution-and-fault-semantics), the late-fusion baseline
in [section 7.6](#76-multi-sensor-fusion-and-uncertainty), the staged tracker in
[section 7.8](#78-tdd-reference-tracker-and-stagewise-development), and the four evaluation
boundaries in [section 6.6](#66-four-independent-g2-evaluation-boundaries).

The minimum mesh is two visible cameras plus one non-camera source chosen through hardware selection,
on a selected compute host. A networked source such as `ss-sens` may enter through an adapter when
its clocks and provenance meet the contract. Encounters come from authorized bench recordings with an
independent reference, and a disjoint calibration split supports any calibrated claim.

Software delivery includes live synchronized capture through replaceable drivers; immutable raw and
typed-observation bundles; four boundary-specific scenarios; calibrated evidence models where
supported; and four separate local report panels. Capture records measured clock domains, queue
loss, disconnect/recovery and original raw formats. Component runs enforce their allowed inputs
through the runner rather than trusting a candidate not to read pixels or future events. The same
corpus grouping rules cover every modality and freeze reviewed scene truth and opportunity masks.
The calibration suite fits only on the disjoint split and validates each claimed probability against
independent outcomes. Insufficient labels or calibration produces an explicit unavailable quantity
and coverage, while deterministic association and tracking can still be evaluated.

Boundary: the mesh is a reference baseline and not an accuracy ceiling. Resource-aware policy,
recognition, stereo range and learned fusion stay in [section 12](#12-unscheduled-design-candidates).
It makes
no field-range claim and has no actuation path.

Evaluation: the G2 rows of the [acceptance matrix](#13-acceptance-and-negative-result-matrix) for
the four boundaries. A valid negative result is a sensor that adds no measured evidence. That finding
is documented and updates the hardware selection record. A reduced mesh starts a new configuration
and cohort; it never retroactively changes the evidence for the original set.

### 16.6 Device bench evaluation

`device-bench-evaluation` is an optional extension for measuring finished systems in one device
class using the same physical stimulus, independent reference and installed-system boundary.
`SENSOR_BENCH` adapters emit contract events; a suite without an operator seed measures detection
delay, lock coverage by the device's own track ID and false alarms per hour. The protocol freezes
the stimulus, timing, calibration, windows and validity limits before acquisition.

Boundary: individual and side-by-side cases are unranked. This is the only cross-device comparison;
there is no hardware-agnostic ranking, public Device Board, enrollment or publication service.
Two units support unit-variation evidence; a single unit is explicitly labelled. An unavailable
device does not block benchmark or reference-mesh development. No field-range or safety claim follows.

Evaluation: simulated device fixtures verify event adaptation, unsupported output paths and refusal
of unmatched stimulus/reference/boundary. Live cases retain raw events, reference and energy traces.
No accessible device, no usable output path or an unmeasurable quantity is a valid negative result.

## Repository foundation

The repository carries the product through one traceable chain:

```text
domain problem -> bounded capability -> evaluation -> forward task
               -> code and tests -> current-state documentation
```

This specification answers what and why. The [implementation plan](../impl/plan.md) answers what
remains, [current-state documentation](../impl/current.md) answers what exists, and `AGENTS.md` is
the contributor policy. CI checks the joins so completion is a state transition, not a status note.

Production behavior belongs below `src/ss_track/`. CLI parsing stays at the boundary and domain
logic moves to focused modules. Runtime artifacts resolve from `DATA_DIR` and never enter source
packages. This foundation does not select a persistence layer, deployment platform, or release
policy; those enter through a specified capability when needed.

### Reproducible environment

The environment is created from `pyproject.toml` and committed `uv.lock`. Local development and
GitHub Actions both call Make targets and use the same locked development extra. Tool caches follow
`DATA_DIR`; the shared environment helper chooses `UV_LINK_MODE=copy` only when uv's cache and the
checkout live on different filesystems.

Boundary: the repository controls Python dependencies and checks. It does not install system
packages, provision external services, or guarantee reproducibility for undeclared tools.

Evaluation: a fresh clone reaches `make bootstrap` and `make ci` without manual repair. A negative
result names the missing command, stale lock, unsupported interpreter, or failing gate rather than
silently changing the environment contract.

### Project identity

The project distributes as `ss-track`, imports as `ss_track`, and installs the `ss-track` command.
The package exposes typed distribution, import-package, and version metadata. The `ss-track info`
command provides a minimal installed-path smoke test and a stable seam for the first product
interface.

Boundary: the command reports identity only. It does not define configuration, service health,
deployment readiness, or benchmark behavior.

Evaluation: package import and CLI tests verify the same identity, while the build target produces
both source and wheel distributions. A negative result retains the minimal identity seam and records
why the proposed product interface is not yet ready.

### Documentation and planning integrity

`AGENTS.md` is the canonical contributor policy; tool-specific files are adapters. The product
specification, forward plan, and current-state tree have distinct ownership. Repository checks
validate relative links and anchors, capability registration, task metadata, lane-appropriate
statuses, group ordering, and forward-only plan language.

Boundary: these checks establish structural agreement. They do not decide which capability is
valuable, whether an evaluation threshold is ambitious enough, or whether a human judgment is
correct.

Evaluation: synthetic tests reproduce broken links, unknown capabilities, missing task fields,
wrong task lanes, and invalid ordering; the shipped tree passes the same checks. A negative result
blocks the change and points to the documents that disagree.

## Capability Registry

Each scheduled software or hardware-support capability appears once. `planned` requires open tasks;
`shipped` links to current-state implementation. A shipped capability may have optional extensions.
Unscheduled design candidates remain in section 12 until their evaluation and work are scheduled.

Row order prioritizes required core software and hardware evidence before optional extensions.
Both plan lanes follow this order. Tasks within a capability can span milestones; explicit
dependencies handle cross-lane handoffs, such as characterization before final hardware selection.
Group order alone never establishes readiness.

| # | Capability | Status | How it is evaluated | Implementation |
| --- | --- | --- | --- | --- |
| 1 | `reproducible-environment` | shipped | A fresh locked environment reaches the complete CI gate without manual repair | [Developer tooling](../impl/current/developer-tooling.md) |
| 2 | `project-identity` | shipped | Import, CLI, and distribution-build tests agree on the project identity | [Product core](../impl/current/product-core.md) |
| 3 | `corpus-provenance` | planned | Import/hash/canonical-decode, staged frame bundles, synchronized multi-stream grouping, generated cases, version lineage, duplicate-frame and source-term refusals and scenario-rights/split fixtures; malformed source yields structured failure | - |
| 4 | `annotation-selection` | planned | Two-reviewer G0 labels, stable class/instance IDs, frozen mask and identical seed replay | - |
| 5 | `module-contract-runner` | planned | Oracle, null, dropper, crash, schema and class-identity fixtures pass with exact frame accounting | - |
| 6 | `motion-sot-evaluation` | planned | Hand-computed fixture metrics, denominators and time weights match evaluator output | - |
| 7 | `reference-tracker` | planned | Deterministic seeded SOT and proposal front end pass continuity, lost/re-entry, identity and deadline fixtures; optional load setting preserves lockstep outputs | - |
| 8 | `comparison-report` | planned | Compatible-cohort report exposes errors; incompatible runs are refused with reason | - |
| 9 | `hardware-probe-adaptive-launch` | planned | Recorded and live host probes report CPU, memory, storage, scheduler, frequency and throttle evidence, and select a supported profile, `UNSUPPORTED` or `MEASURE_REQUIRED` | - |
| 10 | `controlled-bench-timing-energy` | planned | section 7.9 versioned trials retain instrument/calibration and raw-trace hashes and compute timing, resource, thermal and energy estimates with uncertainty and explicit validity | - |
| 11 | `hardware-selection` | planned | Fixture configurations against a stated budget; only measured configurations are chosen; a selection record states rejected and unmeasured options; none qualifying is stated | - |
| 12 | `sensor-joint-mode-probe` | planned | Every installed sensor's modes and simultaneous joint modes are probed under sustained load and yield a supported profile or explicit fallback | - |
| 13 | `camera-bench-characterization` | planned | Independent stimulus, capture, optics and vibration trials retain raw evidence and report estimates with uncertainty and explicit validity | - |
| 14 | `sensor-adapter-frontends` | planned | Typed observations, mixed-modality bundles and four scenario boundaries pass conformance; fake-driver capture covers skew, overflow, outage and recovery before live acceptance | - |
| 15 | `fusion-analysis` | planned | Fixed hashed observation bundles isolate event-time association, deduplication, calibrated existence/class evidence, abstention and degraded-source behavior | - |
| 16 | `fixed-input-tracker-evaluation` | planned | Fixed hashed observations and schedule isolate SOT/MOT identity, re-entry, prediction, confidence and tracker-stage cost | - |
| 17 | `multi-source-reference-tracker` | planned | The staged reference tracker consumes frozen observation bundles and passes hand-audited provenance, identity and deadline fixtures | - |
| 18 | `g2-sensor-set-evaluation` | planned | Feasible single, paired, all-installed and leave-one-out sets run through one frozen reference fusion rule; achieved quality and oracle observability ceiling remain distinct | - |
| 19 | `installed-system-evaluation` | planned | Same-trial raw-to-output quality, timing and installed-boundary energy retain validity; four local report panels distinguish component from whole-system results | - |
| 20 | `mot-trackeval` | planned | Byte-exact per-class export fixtures, pinned environment and hand-audited MOT results | - |
| 21 | `paced-thermal-trial` | planned | Hand-audited cool, hot and capped fixtures on identical frames, then a live baseline run; a hot run with no throttling is `not_tested`, and a failed bet is published | - |
| 22 | `benchmark-ranking` | planned | Optional matched-cohort fixtures yield rank, tier, inconclusive or refusal; scores recompute exactly; below the minimum every row stays unranked | - |
| 23 | `device-bench-evaluation` | planned | Optional same-stimulus fixtures validate unranked cross-host cases; incompatible references are refused and missing device output is UNSUPPORTED | - |
| 24 | `documentation-integrity` | shipped | Link, registry-plan, task-lane, metadata, ordering, and forward-language checks pass over fixtures and the repository tree | [Governance](../impl/current/governance.md) |

Every task declares its outcome, scope, evidence, execution and acceptance. Only tested and
documented implementation changes a capability to `shipped`. Optional branches cannot gate
required M1-M3 acceptance.

## Extending This Specification

The specification is living. A product need discovered during implementation expands this document
through the lifecycle below. It is not a fixed scope fence, but behavior that has no specification,
boundary, or evaluation is outside the product until those are declared.

A capability gap is a product discovery, not an automatic refusal and not permission for silent
scope growth. Use this lifecycle in order:

1. State the problem in operator or domain terms.
2. Amend the owning section of this specification, including what the capability does not do.
3. Declare the measurement, acceptance signal, and valid negative result before implementation.
4. Add a `planned` registry row with that evaluation.
5. Put tasks under the capability in the implementation line; every task declares `Serves`.
6. Build and evaluate, document available behavior under current state, remove finished plan scope,
   and change the registry row to `shipped` with its implementation link.

When implementation reveals that an existing capability has the wrong boundary, update its section
instead of creating an implementation workaround that the specification cannot explain.

## Specification and plan integrity

The registry and [implementation plan](../impl/plan.md) are two views of one product. The executable
contract requires:

- every task serves a registered capability and sits in its capability group;
- every capability declares an evaluation;
- every planned capability has at least one open task;
- every shipped capability links to current-state documentation;
- groups follow registry order in each task lane;
- every task declares the required outcome, boundary, execution, and acceptance fields;
- lane statuses match whether an agent can finish independently or a human action gates acceptance;
- required tasks precede optional refinements within a capability.

The check is structural by design. Product priority changes are made by editing the registry order,
not by adding heuristics to the checker.

## Success criteria

Product claims are judged gate by gate in [Section 3](#3-scope-and-delivery-gates) and the
[acceptance matrix](#13-acceptance-and-negative-result-matrix).

The repository foundation succeeds when a contributor can clone it, create a locked environment, run
a tested package, and use any supported agent without duplicating project policy. A maintainer can
determine what the product promises, what work remains, which task is next in each lane, what
behavior exists, and how every capability is evaluated from repository files alone.
