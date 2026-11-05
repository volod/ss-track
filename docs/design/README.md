# Design

The [product specification](spec.md) is the living source of truth for product behavior. It includes
the capability registry, the evaluation contract for each capability, explicit boundaries, and the
process for adding capabilities discovered during implementation.

The registry order is the implementation line followed by the
[forward plan](../impl/plan.md). `make lint-spec-plan` makes disagreement between those documents a
build failure.

Current behavior is indexed by [current implementation](../impl/current.md).

## Perception Bench design input

These documents describe the implementation approach for
[specification section 16](spec.md#16-benchmark-extensions-hardware-selection-and-reference-sensor-mesh).
The specification stays authoritative when they differ.

- [Engine design](perception-bench-engine.md): approach, milestones and rationale.
- [Test plan](perception-bench-test-plan.md): required tests for approved behavior.
- [Test-stand requirements](test-stands.md): hardware needs and the selection flow.
- [Mesh hardware shortlist](mesh-hardware-shortlist.md): datasheet-sourced compute-host and sensor
  candidates feeding the shortlist step; selects no hardware.

## Data contracts and telemetry design input

- [Data contract design](data-contracts.md): why open schemas, what was taken from fl-op, and the
  evidence behind
  [specification section 17](spec.md#17-data-contracts-and-schema-evolution).
- [Telemetry sources](telemetry-sources.md): boards, sensors, formats, libraries and the adapter
  design behind [specification section 18](spec.md#18-board-and-sensor-telemetry).

Repository design covers software and the hardware support needed to evaluate it. Commercial,
organizational and publication operations live in an owner-managed to-do outside Git control.
The human hardware flow produces documented measured choices, not a purchasing roadmap.
