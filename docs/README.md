# Documentation

This directory separates product intent, forward work, current behavior, and contributor guidance.

## Start here

- [Product specification](design/spec.md) defines purpose, scope, boundaries, capabilities, and
  evaluation.
- [Design input](design/README.md#perception-bench-design-input) defines the engine architecture,
  test plan and test-stand requirements.
- [Data contract design](design/data-contracts.md) and
  [telemetry sources](design/telemetry-sources.md) explain open schemas and telemetry adapters.
- [Forward implementation plan](impl/plan.md) contains only work that remains.
- [Current implementation](impl/current.md) indexes behavior available in the repository.
- [Task records](impl/records/README.md) keep each finished task's text and acceptance evidence.
- [Planning workflow](guide/planning-workflow.md) explains task lanes and the capability lifecycle.
- [Development guide](guide/development.md) lists setup and quality workflows.
- [Project rules](../AGENTS.md) govern agent and contributor behavior.

## Document ownership

| Question | Source of truth |
| --- | --- |
| What should the product do? | [Design specification](design/spec.md) |
| What work remains? | [Implementation plan](impl/plan.md) |
| What exists and where? | [Current implementation](impl/current.md) |
| What happened to a finished task? | [Task records](impl/records/README.md) |
| How should work be performed? | [Contributor guide](guide/README.md) and [AGENTS.md](../AGENTS.md) |

## Repository boundary

Keep software development, evaluation methods and hardware support design here. The Human-Assisted
lane supplies authorized data, reviewed labels, calibrated stand evidence and measured hardware
selection. Commercial strategy, staffing, publication policy and launch operations are maintained
outside repository Git control and do not gate software acceptance. A local `.env` may name that
folder as `ORG_ARTIFACTS_DIR` for awareness. Nothing in the repository reads it.
