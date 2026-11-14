# corpus-evaluation-result-contract

## Task and scope

- Id / capability: `corpus-evaluation-result-contract` / `self-supervised-corpus`
- State: accepted
- Source: plan task, start commit `16da110`; working tree clean.
- Plan counts at start: 127 tasks, 104 agent and 23 human. Next agent
  `corpus-evaluation-result-contract`, next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-evaluation-result-contract

`discover evaluate` logs a comparison the newest `result/command` contract refuses.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: The comparison `discover evaluate` prints is a command result a reader can
  validate.
- Scope boundary: The comparison the command already returns. No change to the statistics, and no
  claim that a recorded blinding declaration was verified.
- Data and artifact paths: `src/ss_track/corpus/evaluation/`, `tests/corpus/`, `contracts/`,
  `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: `corpus/evaluation/report.py` returns statuses `estimated` and `inconclusive` and
  fields such as `audit`, `observations`, `review_blinding`, `review_independence`,
  `review_effort_minutes` and `limits`. The newest `result/command` accepts none of those statuses
  or fields. The production CLI does not check the result, so the command succeeds, and a pytest
  run of the CLI fails the command-result hook. Add a minor of `result/command` for this comparison
  and a CLI test. The presentation command already uses `blind` for its counts, so this comparison
  keeps its metrics off that name.
- Acceptance gates: `discover evaluate` results for an estimated and an inconclusive fixture
  validate against the newest `result/command`, and `make ci` passes.
- Documentation target: [Discovery runs](current/corpus/discovery-runs.md#evaluating-selection).
```

- Amendments: none.

## Implementation

`result/command` 1.22.0 adds statuses `estimated` and `inconclusive` and the comparison
`discover evaluate` already returns. The comparison writer is unchanged: it does not recompute the
stratified estimates, and a recorded blinding or independence value stays a declaration.
`review_blinding` and `review_independence` are `declared`, `not_declared`, `unrecorded` or `mixed`.
They are separate from the `blind` counts of the presentation command. `compute_cost` remains null.
Exclusion counts use the reasons a candidate inventory can record, and miss counts use the four
observation names. A reason or observation is absent when its count is zero.

The command test runs both selections through `discover evaluate`. The suite's command-result hook
checks each log against the newest `result/command`. No new dependency, environment variable or
refusal code was added.

Current behavior is in
[Evaluating selection](../current/corpus/discovery-runs.md#evaluating-selection). The contract
catalog lists 1.22.0 in [Contracts](../current/contracts.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Estimated and inconclusive `discover evaluate` results validate | `.venv/bin/pytest tests/corpus/evaluation/test_evaluate_command.py` | pass before `make ci`; fixture clips only. The hook checks the logged records, including a mixed blinding declaration |
| `make ci` | `make ci` | pass: 2243 passed, 112 deselected. Format, lint, typing, complexity, shell lint, doc links, spec-plan and contracts reported no findings |

Missing, mocked or stale evidence does not prove acceptance. Runtime artifacts stay under
`$DATA_DIR` and are cited by path, not copied here.

## Audit handoff

`none identified`. Reviewed the comparison writer, the new command schema, the CLI test and the
evaluating-selection page.

- Dropped: discovery still does not record compute cost. `corpus-selection-evaluation` already
  states that the comparison must capture measured cost and that discovery does not record it.
- Dropped: equal selection counts can still hide unequal review workload.
  `corpus-evaluation-review-budget` already states that comparison.
- Dropped: the production CLI does not validate command results at runtime. The suite hook does,
  which is the check this task required, and every other command uses that same hook.
- Dropped: no ss-video or ss-fusion change. The comparison is an ss-track command result over
  ss-track runs and reviews. It calls no sibling interface.

## Close or resume

All acceptance gates passed. The task is removed from the plan. Nothing else depended on it.
The plan has 126 tasks: 103 agent and 23 human. The next agent task is
`corpus-evaluation-review-budget` and the next human task is
`define-locked-test-policy (optional)`. `self-supervised-corpus` remains planned.
