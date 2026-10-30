# Planning Workflow Guide

The documentation lifecycle keeps product intent, future work, and available behavior separate.

## The product-quality discovery circle

1. **Observe a need.** State what a user or operator cannot do or trust.
2. **Classify it once.** Choose chore, audit of the current work, extension of a registered
   capability, or a new capability.
3. **Specify a capability gap.** For a new capability, define behavior, boundary, evaluation, and a
   valid negative result before code.
4. **Register and schedule.** Add a `planned` registry row, then tasks in the correct plan lane.
5. **Build and evaluate.** Implement the smallest bounded slice and run its declared checks.
6. **Close the loop.** Move available behavior to current-state docs, remove finished plan scope,
   update the registry, and classify anything newly surfaced.

A chore is handled during the change when necessary or dropped. An audit of the work just produced
is part of completion and does not become a permanent task. More work for an existing capability may
become a task; mark a refinement `(optional)`. A new capability always returns to specification.

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

## Completion transition

Before reporting completion:

1. Count plan tasks with `make plan-status`.
2. Record behavior, locations, commands, tests, and results in the narrowest current-state page.
3. Remove the finished task and retain only genuinely open residual scope.
4. Mark a newly complete capability `shipped` and add its current-documentation link.
5. Run `make lint-spec-plan`, `make lint-doc-links`, and `make ci`.
6. Count tasks again and report which capabilities moved.

Current-state pages retain decisions and results. The plan never becomes a changelog.
