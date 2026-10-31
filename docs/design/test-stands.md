# Test stands and hardware selection

Hardware work supports correct benchmarks and a reference sensor mesh object-tracking implementation.
It is a separate [Human-Assisted task flow](../impl/plan.md#human-assisted-tasks), governed by
[spec section 16.4](spec.md#164-hardware-selection). Agents build measurement and analysis software;
people supply requirements, access, equipment, physical setup and reviewed decisions. Procurement
administration and organizational approvals stay outside the repository.

## Selection flow

1. **Define requirements before acquisition.** Name the software capability and workload each
   requirement supports. Version its target, units, acceptance tolerance and measurement precision.
   Include task quality/coverage, geometry and clock uncertainty, latency/loss, interfaces, sustained
   throughput/storage, average and peak power, energy per task and thermal limits. Unknown limits
   remain unresolved; do not derive favorable thresholds from candidate results.
2. **Shortlist provisionally.** Inventory available, borrowed or approved candidates, exact revisions,
   drivers and raw formats. Datasheets guide the shortlist; they do not establish measured support.
3. **Bootstrap metrology.** Check the first meter, host and supply with known loads, clock markers
   and the reference/null workload. Record bootstrap exceptions and provisional choices explicitly.
4. **Build the characterization stand.** Use candidate interfaces to build independent stimulus,
   reference and clock checks before final sensor selection. Retain raw traces for every trial.
5. **Measure and compare.** Characterize candidate quality, observability and timing; probe joint
   modes under sustained load; measure installed-boundary energy. The planned
   `ss-track hardware-select` consumes evidence against frozen requirements and uncertainty.
6. **Review and hand off.** Record chosen, rejected and unmeasured configurations with reasons.
   Deliver machine-readable profiles, calibration, raw-format examples and evidence hashes to
   software development. A single available candidate is provisional; no qualifying set is valid.
7. **Validate the installed mesh.** Evaluate all four boundaries and update selection from measured
   sensor contribution. Dropping a source creates a new configuration and cohort, preserving the
   original evidence. Changed requirements start a new selection revision.

The plan names these handoffs: `acquire-bootstrap-bench`, `calibrate-bench-instruments`,
`select-reference-host`, `shortlist-mesh-sensors`, `build-sensor-test-stand`,
`run-camera-characterization`, `select-mesh-sensors`, `record-mesh-encounters` and `run-mesh-trials`.
The thermal rig is an optional branch after host selection; it does not gate sensor selection.

## Selection record

The first result creates `docs/impl/current/hardware-selection.md`. Raw evidence stays under
`$DATA_DIR/selection/<selection-id>/`, `$DATA_DIR/trial/<trial-id>/` and
`$DATA_DIR/instruments/<instrument-id>/`; sanitized requirement profiles belong in `scenarios/stands/`.
These paths describe planned artifacts, not existing choices or commands.

| Field | Required content |
| --- | --- |
| Software consumer | Capability, task and workload the hardware enables |
| Stand and requirement revision | Targets, units, tolerances, precision, resource limits and basis frozen before trials |
| Candidate identity | Exact host, sensor, optics, firmware, driver, transport, supply and cooling configuration |
| Trial comparability | Workload, schedule, physical reference, conditions, repetitions and measured boundary |
| Evidence | Trial and raw-trace hashes, calibration, alignment and uncertainty for every required quantity |
| Decision | Qualified choice, provisional bootstrap, insufficient evidence or no qualifying configuration |
| Rejected and unmeasured | Each alternative and its measured rejection or missing evidence; no invented measurements |
| Software handoff | Profile/calibration revisions, raw-format samples, supported modes and known failure limits |
| Review and invalidation | Responsible reviewer and conditions that require a new requirement/configuration revision |

Shared rails stay shared in energy ledgers. A value whose uncertainty crosses a requirement is
inconclusive; a missing required quantity cannot pass. This is a measured suitability decision for
the declared stand, not a general buying recommendation.

## Stand A: module measurement stand

Serves paced replay, host selection, energy/timing evidence and the reference tracker's cost profile.

| ID | Requirement | Software need | Verification |
| --- | --- | --- | --- |
| A1 | Declared Linux architecture and a supported isolated container runtime | Runner and module recipes | Host probe and hostile-input fixture on the actual host |
| A2 | Storage and memory sustain the frozen frame schedule and retained corpus | Paced replay without hidden I/O loss | Measured throughput, pacing jitter and null-module run |
| A3 | Calibrated external logging meter covering measured voltage/current peaks | `power-trace-ingest` | Known-load, range and saturation checks; onboard counters alone do not qualify |
| A4 | Sample rate and maximum gap justified from workload transients before acquisition | Exact interval energy and uncertainty | Versioned protocol and trace-gap test |
| A5 | Validated marker alignment between meter and runner clocks | Interval boundaries | Offset/drift trial and uncertainty budget |
| A6 | Identified instruments and calibration records | Recomputable measurement uncertainty | Calibration and check evidence |
| A7 | Full power delivery through the actual meter/supply/cable path | Valid host comparison | Supply/load checks and undervoltage evidence |

The optional thermal experiment adds these requirements; a host can support M2/M3 without them.

| ID | Requirement | Software need | Verification |
| --- | --- | --- | --- |
| A8 | Off-host control holds chip temperature within a declared band | Thermal controller | Full-segment load-step trial |
| A9 | Hot set-point reaches measured throttling onset | Causal thermal experiment | Temperature, frequency and throttle evidence |
| A10 | Rig sensors, heater and cooling have a declared external power boundary | Uncontaminated module energy | Boundary inventory |
| A11 | Low-rate temperature/frequency/throttle logs with measured overhead | Thermal mechanism test | Raw trial and null-module evidence |
| A12 | A verified frequency cap | Capped cool control | Probe and sustained frequency trace |

## Stand B: sensor characterization stand

Serves candidate characterization before selection and later front-end calibration.

| ID | Requirement | Software need | Verification |
| --- | --- | --- | --- |
| B1 | Controlled non-sensitive target with measured dimensions and conditions | Pixel extent and modality observability | Independent target/stimulus record |
| B2 | Trajectory/event reference independent of every tested source | Quality and timing truth | Reference trace, calibration and uncertainty |
| B3 | Fixed mounts with optics, exposure, lighting and sensor modes recorded | Repeatable inputs | Exact assembly/profile inventory |
| B4 | Optical/electrical marker or validated modality-specific clock alignment | Capture timing | Offset/drift and capture-clock trials |
| B5 | Instrumented motion/vibration stimulus when claimed | Motion-conditioned metrics | Measured reference motion, not actuator commands |
| B6 | Independent positive/negative cases for the non-camera evidence role | Selection beyond transport compatibility | Task coverage, false events and timing with uncertainty |

## Stand C: reference sensor mesh stand

Serves the installed tracker and its four independent evaluation boundaries.

| ID | Requirement | Software need | Verification |
| --- | --- | --- | --- |
| C1 | Initial test configuration of two visible cameras and one measured non-camera source | Reference mesh | Selection record; later removal requires measured contribution evidence |
| C2 | Sustained simultaneous modes with shared bus/compute limits | Capture and fusion inputs | Joint-mode trial, including loss and recovery |
| C3 | Measured clock offset/drift and uncertainty | Event-time association and deadlines | Clock markers and raw traces |
| C4 | Geometry, coverage and calibration for each claimed quantity | Gated association | Independent reference and versioned calibration |
| C5 | Reviewed scene truth and cross-sensor identity with disjoint calibration/evaluation encounters | Four boundary suites | Frozen labels, opportunity masks and split checks |
| C6 | Meter boundary includes sensors, transport and compute | Full-system energy | Boundary inventory and instrument checks |
| C7 | Declared evidence role and available dimensions for every source | Typed front ends | Conformance; context is never an independent object detection |
| C8 | Authorized recording conditions for every modality | Valid data and hardware access | Scenario rights and operating constraints |
| C9 | Raw formats, driver support and bounded capture with explicit failures | `synchronized-sensor-capture` | Capture, outage and recovery evidence |

## Stand D: optional device evaluation stand

Serves unranked device-suite validation after the reference-mesh software exists.

| ID | Requirement | Software need | Verification |
| --- | --- | --- | --- |
| D1 | Same physical stimulus for each compared device in one class | Comparable cases | Stimulus and environment record |
| D2 | Independent scene/trajectory reference | Device-suite scoring | Reference trace and calibration |
| D3 | Meter covering each installed system's supply range | Same-boundary energy | Known-load and uncertainty checks |
| D4 | Contract events with exact raw-output provenance | Device adapter | Conformance fixtures and retained events |
| D5 | Unit identity, with two units or a single-unit limitation | Variation interpretation | Trial inventory |

## Limits

No hardware model is selected by this document. Datasheet figures and capacity calculations remain
design inputs until measured. No stand result establishes field range, operational safety or the
value of an uninstalled sensor. Negative findings return to the software requirement and selection
record rather than becoming unsupported hardware claims.
