# Planning Workflow Guide

The documentation lifecycle keeps product intent, future work, and available behavior separate.

## The product-quality discovery circle

1. **Observe a need.** State what a user or operator cannot do or trust.
2. **Classify it once.** Choose chore, audit of the current work, extension of a registered
   capability, or a new capability.
3. **Specify a capability gap.** For a new capability, define behavior, boundary, evaluation, and a
   valid negative result before code.
4. **Register and schedule.** Add a `planned` registry row, then tasks in the correct plan lane.
5. **Build and evaluate.** Open a task record, implement the smallest bounded slice and run its
   declared checks.
6. **Close the loop.** Move available behavior to current-state docs, close the task record, remove
   finished plan scope, update the registry, and classify anything newly surfaced.

A chore is handled during the change when necessary or dropped. An audit of the work just produced
is part of completion and does not become a permanent task. More work for an existing capability
amends the open task that owns it or becomes a new task; mark a refinement `(optional)`. A new
capability always returns to specification.

Discovery is part of implementation. A gap, wrong boundary, risk or directly usable feature found in
a deep dive changes the specification and the plan in the same change, unasked. A task record explains
what happened; it does not schedule anything. An item is routed only when an open task's text states
it, or when the record says why it was dropped.

## Task lanes

Use **Agent Implementation Tasks** when an agent can reach acceptance using repository fixtures,
deterministic tools, or an authorized non-interactive run:

- `CLEAR`: code, tests, and docs can finish locally.
- `RUN NEEDED`: implementation is deterministic, but acceptance includes a declared heavier run.

Use **Human-Assisted Tasks** when acceptance itself needs a person or authority unavailable to an
agent:

- `BLOCKED BY HUMAN`: an agent can prepare support, but a human-provided artifact gates completion.
- `HUMAN-GATED`: the outcome is human judgment, authorization, private access, or spend approval.

Add `Research: yes` when the path is uncertain and a well-supported negative result is acceptable.
Research is not a reason to omit scope or acceptance criteria.

Add `Milestone: <id>` when a task belongs to a staged delivery. Cross-lane dependencies are
allowed, including characterization that feeds a later selection step in an earlier capability
group. Dependencies express gating; group order expresses priority. Required work cannot depend on
an optional extension. Milestone relationships follow the engine's dependency graph rather than
the numeric order of IDs.

`make plan-status` currently reports counts and the first task by priority in each lane. It does not
parse dependency readiness; check the full Dependencies fields before starting work. The optional
dependency-integrity task covers automated graph validation and truthful readiness reporting.

Hardware support stays in the Human-Assisted lane: define requirements from software needs, shortlist,
characterize with independent references, select from measured evidence, and hand profiles and
selection records back to software development. Datasheet and bootstrap choices remain provisional.
Commercial planning, staffing, public entry/dispute policy, publication approval and launch operations
belong outside repository Git control. Keep technical rights and export controls in the data contract;
do not make organizational publication a dependency of software acceptance.

## Task shape

Task ids are stable lowercase slugs. A task heading may end with `(optional)`. Use this structure:

```markdown
### Capability name -- `capability-id`

#### stable-task-id

Describe the unresolved operator problem in present or future tense.

- Serves: `capability-id` -- [Specification section](../design/spec.md#section)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: State what becomes possible or trustworthy.
- Scope boundary: State what is in scope and explicitly out of scope.
- Data and artifact paths: Name repository-relative or `$DATA_DIR` locations.
- Execution path: Name modules, fixtures, commands, and any declared run.
- Acceptance gates: State deterministic checks and the negative-result rule.
- Documentation target: [Current-state area](../impl/current.md#areas).
```

The plan integrity gate requires every field. Human-lane tasks use a human-lane status. Optional work
follows required work within its capability.

## Ordering

Capability groups follow the registry. Within a group:

1. hard prerequisites;
2. changes to inputs that later evaluation consumes;
3. required work before optional refinements;
4. cheap deterministic work before expensive runs.

If priorities change, edit the registry order and move the same groups in both lanes. Do not encode
priority in task wording.

## Task records

Each task started from the plan gets a record under [`docs/impl/records/`](../impl/records/README.md),
copied from the [template](../impl/records/template.md) when work starts. The record keeps the
accepted task text verbatim, the implementation notes, and the acceptance evidence after the task
leaves the plan. Current-state pages link the record; the plan never does.

An amended task keeps its original block, followed by each revised block with its reason and who
authorized it. Name exact commands and tests as evidence; missing, mocked or stale evidence does not
prove acceptance, and a one-off investigation says that its scripts were not kept. The audit handoff
gives each observation exactly one owner: an open task whose text states it, created in the same
change if necessary. A closed record is history and is not rewritten later. Later routing of an old
item goes in a new `adhoc` record.

### Record file naming

Name a record `NNNN-<group>-<task-id>.md`: `NNNN` is the next unused four-digit sequence from the
[records index](../impl/records/README.md), `<group>` is the capability id the task serves, and
`<task-id>` is the plan task id. Ad hoc work that did not come from the plan uses `adhoc` as the
group. Add the record to the index table in the same change.

## Completion transition

Before reporting completion:

1. Count plan tasks by lane with `make plan-status`.
2. Update available behavior, interfaces, locations and verification methods in the narrowest
   current-state page, and link the task record from it.
3. Remove the finished task and retain only genuinely open residual scope.
4. Mark a newly complete capability `shipped` and add its current-documentation link.
5. Run `make lint-spec-plan`, `make lint-doc-links`, and `make ci`.
6. Close the task record with its evidence and add it to the records index.
7. Count tasks again and report which capabilities moved.

Current-state pages retain design rationale, actionable limitations and measured evidence that
informs implementation, updated in place. They omit task-count snapshots, migration narratives,
completed audit logs and routine check results, which belong in the task record. The plan contains
only remaining work.
