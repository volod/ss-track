# Design: ss-track Perception Bench and reference sensor mesh

This design implements two goals: correct benchmarks and an inspectable reference sensor mesh
object-tracking implementation. [The specification](spec.md) is normative; the
[forward plan](../impl/plan.md) owns remaining work. The [test plan](perception-bench-test-plan.md)
defines validation; [test stands](test-stands.md) define hardware support requirements.

## Problem

Tracking quality cannot be compared reliably when inputs, labels, timing, energy boundaries or
hardware configurations differ silently. A reference mesh also needs evidence about what each
sensor contributes, independently of the fusion and tracker stages.

## Goals and boundaries

1. Recompute detection, tracking and fusion metrics from immutable evidence, with uncertainty,
   timing, energy and missing measurements visible.
2. Run a replaceable reference mesh on hardware selected from measured evidence, and evaluate its
   sensor/front-end, fusion, tracker and complete-system boundaries separately.

Software methods, local reports and hardware support design belong here. Commercial positioning,
public participation and dispute policy, staffing, publishing a paper, account management and launch
operations belong in an organizational to-do outside Git control. No public launch is a prerequisite
for software acceptance. Source rights and export restrictions remain part of the data contract.

## Architecture

```text
authorized sources + reviewed labels -> frozen scenario -> runner -> immutable run bundle
                                                              |              |
calibrated instruments + profiles -----------------------------+              v
                                                                  pure metric suites
                                                                            |
                                                                   local HTML/JSON report
                                                                            |
                                                         explicit permission -> shareable export

selected sensors -> capture -> typed observations -> late fusion -> reference tracker
                       |               |                 |                |
                       +---- raw ------+--- frozen component inputs -------+
```

One contract function owns cohort identity. One bundle format records runs, blocks, schedules and
lineage. Metric suites read retained bundles; the report reads their results. The evaluator follows
the dataset/metric/evaluator separation, with `aggregate(level, children)` for episode, encounter,
run and block aggregation. TrackEval is an isolated MOT suite, never the energy evaluator. Verify
its current compatibility when implementing the adapter; do not assume a historical upstream state.

Use one package per concern under `src/ss_track/`; CLI parsing remains in `cli.py`. External module
adapters and image recipes live under `modules/`, keeping their dependencies outside the core lock.
The reference and null modules use the same input isolation and container path as candidates.
Fixtures run without hardware; physical claims require the human evidence flow.

## Measurement choices

- Freeze frames, annotations, masks, seeds and schedules before comparing modules. Late, missing or
  faulted outputs stay in the denominator.
- Retain raw traces and exact boundaries. Missing instruments make the affected quantity
  `NOT_MEASURABLE`, while valid quality evidence remains usable.
- Characterize sensor candidates before final selection. Probe simultaneous modes and compare
  measured quality, timing and resource limits against versioned stand requirements.
- Start fusion with transparent association and lineage. Fit probability models on disjoint data;
  absent calibration means an unavailable probability claim, not a fabricated posterior.
- Use frozen observation bundles for component comparisons and live synchronized capture for the
  installed-system path. A precomputed replay cannot establish capture latency or sensor energy.
- Keep optional thermal experiments causal: measured throttle onset, controlled chip temperature,
  frequency-capped cool control, randomized order and the load-calibrated reference baseline.
- Optional ranking uses quality floors before energy order, one median-quality run for row values,
  uncertainty-aware tiers and an unranked null row. No ranking is also a valid result.

## Milestone map

Milestones close on evidence, not elapsed-time estimates or task counts. Task dependencies are the
execution graph; independent fixture work can start before a human gate has supplied hardware.

| Milestone | Inputs | Exit condition |
| --- | --- | --- |
| M1: offline pipeline | Authorized positive/negative pilot encounters and reviewed labels | `g0a-pipeline-run` passes the G0a matrix and produces an inspectable comparison; ten encounters and G0b are not prerequisites |
| M2: metrology and host selection | M1 tooling, bootstrap instruments and versioned Stand A requirements | Instrument and harness checks, raw traces and `select-reference-host` produce a measured choice or explicit insufficiency; unsupported claims stay closed |
| M3: reference sensor mesh | M1 contracts, M2 measurement path and a qualified host; independent sensor reference | Candidates characterized before selection; pinned MOT adapter fixtures pass; synchronized capture, frozen inputs and `run-mesh-trials` produce four report panels and measured sensor contribution or a documented unsupported profile |
| M4: optional thermal experiment and ranking | M1 comparison, M2 host and instruments, reviewed development corpus | Thermal mechanism assessed including negative outcomes; frozen comparison protocol, local snapshot and independent recompute/re-run evidence; no rank if requirements fail |
| M5: optional device cases | M2 measurement and M3 installed-system software; accessible devices | Same-stimulus unranked cases or explicit unavailable/unsupported results |

M3 does not depend on M4 or M5. A documented negative result closes an experiment's evaluation,
but unavailable hardware does not mean the mesh implementation shipped. Keep the corresponding
implementation task open until its software acceptance gates pass. A reduced sensor set needs a new
selection/configuration revision. Sections 3 and 13 of the spec define broader G1/G2 claims; these
milestones do not silently claim optional recognition, resource policy, stereo or field behavior.

## Hardware handoff

The [human support flow](test-stands.md#selection-flow) delivers versioned requirements, candidate
evidence, instrument checks, clock/geometry calibration, raw-format samples and selection records.
Software consumes those artifacts through the probe, capture, trial and selection interfaces.
Physical work does not become an agent implementation task because an agent can analyze its output.

## Local reports and reproducibility

Reports show cohort identity and visibility, quality with denominators, timing and faults, measured
energy with uncertainty, limits and reproducible commands. Mesh reports show four separate panels.
Optional ranking adds tiers and unranked reasons from the same stored results; shareable export is
explicit and refuses restricted input. A second process recomputes identical metrics. A second
person can re-run the reference baseline even when no external module qualifies for ranking.

## Open engineering choices

- Decoder with the required host support, container runtime and pinned MOT evaluator.
- Authorized development sources and independent references for the selected sensor candidates.
- Per-stand budgets, measurement precision and acceptance tolerances before acquisition.
- Non-camera evidence role and whether its measured contribution justifies keeping it.

Each choice belongs to a named task in the plan. No hardware model, public release date, novelty
claim or positive thermal effect is assumed.
