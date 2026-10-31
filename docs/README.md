# Documentation

This directory separates product intent, forward work, current behavior, and contributor guidance.

## Start here

- [Product specification](design/spec.md) defines purpose, scope, boundaries, capabilities, and
  evaluation.
- [Design input](design/README.md#perception-bench-design-input) defines the engine architecture,
  test plan and test-stand requirements.
- [Forward implementation plan](impl/plan.md) contains only work that remains.
- [Current implementation](impl/current.md) indexes behavior available in the repository.
- [Planning workflow](guide/planning-workflow.md) explains task lanes and the capability lifecycle.
- [Development guide](guide/development.md) lists setup and quality workflows.
- [Project rules](../AGENTS.md) govern agent and contributor behavior.

## Document ownership

| Question | Source of truth |
| --- | --- |
| What should the product do? | [Design specification](design/spec.md) |
| What work remains? | [Implementation plan](impl/plan.md) |
| What exists and where? | [Current implementation](impl/current.md) |
| How should work be performed? | [Contributor guide](guide/README.md) and [AGENTS.md](../AGENTS.md) |

## Repository boundary

Keep software development, evaluation methods and hardware support design here. The Human-Assisted
lane supplies authorized data, reviewed labels, calibrated stand evidence and measured hardware
selection. Commercial strategy, staffing, publication policy and launch operations are maintained
outside repository Git control and do not gate software acceptance.
