# corpus-evaluation-review-budget

## Task and scope

- Id / capability: `corpus-evaluation-review-budget` / `self-supervised-corpus`
- State: accepted
- Source: plan task, start commit `e5cc701`; working tree clean.
- Plan counts at start: 126 tasks, 103 agent and 23 human. Next agent
  `corpus-evaluation-review-budget`, next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-evaluation-review-budget

Equal selection counts can offer different total numbers of windows when audit overlaps differ, but
`discover evaluate` currently marks such a comparison estimated without checking total review cost.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A comparison states the actual review workload and cannot present unequal
  review budgets as a matched-budget result.
- Scope boundary: Queue-based and recorded review costs for paired runs; no estimation of unrecorded
  human time or changing the independent audit design.
- Data and artifact paths: `src/ss_track/corpus/evaluation/`, `tests/corpus/evaluation/`,
  `contracts/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Define comparable per-method and shared audit review workload before computing
  gains; count unique offered windows, audit overlaps, sibling offers and withheld windows. Compare
  the workload under the declared review protocol, and mark unmatched or unmeasured budgets
  inconclusive while retaining descriptive counts. Keep resource and independence claims explicit.
- Acceptance gates: A fixture with equal selection counts but different audit overlap reproduces the
  false matched result and now becomes inconclusive; matched, missing, sibling and withheld cases
  have hand-calculated counts and valid negative gains stay valid; `make ci` passes.
- Documentation target: [Discovery runs](current/corpus/discovery-runs.md#evaluating-selection).
```

- Amendments: none.

## Implementation

`corpus/evaluation/workload.py` counts the review budget before a comparison can stay `estimated`.
Each offered window counts once. `per_run`, when neither review names an `audit_id`, compares the
two queues. `shared_audit`, when both name the same `audit_id`, compares the windows each run
offers beyond the audit windows both offer, and states that shared count once. Any other pairing is
`unrecorded`, so the budget is unmeasured and the counts stay. A withheld window is reported and is
not offered. A sibling offer is review work. Siblings stay out of the pool index, so the population
estimate does not weight them; the workload reads the inventories directly.

Equal selected counts with different audit overlap are `unmatched`. Unequal selected counts stay
unmatched even when the offered counts match. A withheld key missing from the run is unmeasured.
`review_budget.status` must be `matched` before the comparison status can be `estimated`. A gain
that remains on an inconclusive comparison is descriptive. A negative gain stays `estimated` when
the budget matches.

Recorded minutes are `equal`, `unequal` or `unmeasured`. A missing minute is not stored as zero.
Minutes do not decide the window budget: they record how long a reviewer said the work took, and
two reviews of the same windows need not take the same time. Independence and blinding stay
declarations. The audit sample itself is unchanged. Discovery still does not record compute cost.

`result/command` 1.23.0 adds optional `review_budget` and `sibling_offers`. The queue's stated cost
is the distinct offered count, not the selection budget plus the audit sample.
`corpus-evaluation-by-source` now says to use this budget.

Current behavior is in
[Evaluating selection](../current/corpus/discovery-runs.md#evaluating-selection). The contract
catalog lists 1.23.0 in [Contracts](../current/contracts.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Equal selection, different overlap becomes inconclusive; matched negative gain; missing protocol and missing withheld window; sibling and withheld counts | `.venv/bin/pytest tests/corpus/evaluation/test_workload.py` | pass before `make ci`. Hand-counted fixtures only |
| A real pair's offered and withheld counts match its queues, and the logged comparison validates | `.venv/bin/pytest tests/corpus/evaluation/test_evaluate_command.py` | pass before `make ci`. Budget 6 selects the whole six-window fixture pool, so the queues match. Minutes 12 and 15 stay `unequal` and the window budget stays `matched` |
| Existing paired-review and unequal-selection checks | `.venv/bin/pytest tests/corpus/discovery/test_selection_run.py::test_evaluation_reads_paired_reviews_and_withheld_audit_is_inconclusive tests/corpus/discovery/test_selection_run.py::test_evaluation_refuses_different_budgets_and_audit_designs` | pass before `make ci` |
| `make ci` | `make ci` | pass: 2253 passed, 112 deselected. Format, lint, typing, complexity, shell lint, doc links, spec-plan and contracts reported no findings |

Missing, mocked or stale evidence does not prove acceptance. Runtime artifacts stay under
`$DATA_DIR` and are cited by path, not copied here.

## Audit handoff

- `AUD-corpus-evaluation-review-budget-1`, nonblocking. Per-source metrics must not treat equal
  selection counts as equal review cost. Owner: `corpus-evaluation-by-source`, whose execution
  path now states that it uses this budget and that an unmatched or unmeasured budget stays
  inconclusive.
- Dropped: discovery still does not record compute cost. `corpus-selection-evaluation` already
  states that the comparison must capture measured cost and that discovery does not record it.
- Dropped: recorded minutes do not gate the window budget. The comparison reports them as
  `equal`, `unequal` or `unmeasured`, and a missing minute is not zero. Gating on clock time
  would reject two reviews of the same windows. No further task.
- Dropped: no ss-video or ss-fusion change. The budget is counted from ss-track discovery
  inventories and the reviews or freezes already stored for those runs. It calls no sibling
  interface and changes no sibling contract.

## Close or resume

All acceptance gates passed. The task is removed from the plan. The plan has 125 tasks:
102 agent and 23 human. The next agent task is `corpus-evaluation-by-source` and the next
human task is `define-locked-test-policy (optional)`. `self-supervised-corpus` remains planned.
