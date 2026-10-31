# ss-track Implementation Plan

Forward-only: this file describes work that remains. Available behavior and durable results belong
in [current-state documentation](current.md). Product behavior and evaluation belong in the
[specification](../design/spec.md).

Every task serves a capability from the
[capability registry](../design/spec.md#capability-registry). Capability groups follow registry
order in both lanes. Take the first required task in the earliest group that has one.

Task fields, statuses, ordering, and the capability-gap lifecycle are defined in the
[planning workflow](../guide/planning-workflow.md). Run `make plan-status` to view lane counts and
the next eligible work.

## Agent Implementation Tasks

No open agent tasks. Add work here when a capability enters the registry.

## Human-Assisted Tasks

No open human-gated tasks. Add work here when acceptance requires human judgment, authorization,
private access, or spending authority.
