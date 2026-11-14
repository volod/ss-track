# corpus-evaluation-by-source

## Task and scope

- Id / capability: `corpus-evaluation-by-source` / `self-supervised-corpus`
- State: accepted
- Source: plan task, start commit `02a616e`; working tree clean.
- Plan counts at start: 125 tasks, 102 agent and 23 human. Next agent
  `corpus-evaluation-by-source`, next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-evaluation-by-source

A combined result can conceal that selection misses a source or that a source has no reviewed sample.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: The evaluator reports each collection's reviewed exposure, exclusions and
  weighted selection metrics alongside the explicitly defined combined population.
- Scope boundary: Verified source provenance and reviewed audit observations; no inference about
  species, field prevalence or absence from unreviewed windows.
- Data and artifact paths: `src/ss_track/corpus/evaluation/`, `tests/corpus/evaluation/`,
  `contracts/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Bind source membership to the sealed pool and stratum; report per-source sample
  counts, weights, unknown and withheld exposure, costs, recall and uncertainty, plus the weighted
  combined result. Use the paired review budget: equal selection counts are not equal review cost,
  and an unmatched or unmeasured budget stays inconclusive. A stratum spanning sources must preserve
  the sampling design rather than be silently treated as independent; explicitly report unavailable
  estimates and uncertainty.
- Acceptance gates: Hand-calculated mixed-source fixtures cover unequal sampling weights,
  shared-stratum covariance, a source with no reviewed sample, incomplete provenance and negative
  gains. Unavailable evidence is inconclusive, never zero; `make ci` passes.
- Documentation target: [Discovery runs](current/corpus/discovery-runs.md#evaluating-selection).
```

- Amendments: none.

## Implementation

`discover evaluate` keeps the combined `audit` estimate and adds `by_source`. The name is not
`sources`: that command field is the hash-comparison list. `result/command` 1.24.0 adds optional
`by_source` and widens `limits` from four entries to five. Other commands omit `by_source`.

Membership is the pinned source origin. Providers are `huggingface` and `zenodo`, the same pair the
source manifest allows. A missing origin, an unreadable pin, an unnamed inventory, or a
disagreement between the paired runs is a reason. The evaluator does not guess a collection and
does not use the combined-pool name `unknown`. A window on two origins is counted in each
collection, so per-collection counts can exceed the unique windows, and `partitions_population` is
false. The combined estimate stays the unique population.

Each sampled window keeps its stratum weight, `population / sample_size`, including windows of
other collections. A collection is not reweighted as its own sample. In the hand-calculated shared
stratum, N=8 and n=4, both target totals are 2. An independent weight would have scored them 5 and
1. Variance uses the whole stratum sample, with zero for non-members, so one draw in a stratum of
at least two still has an interval. The covariance of the target totals is -2/3, and the two
variances plus twice that covariance equal the combined target-total variance, 8/3.

A collection with no reviewed sample, or one that sits in an unsampled stratum, has null weighted
totals, recall and target total. A reviewed sample with no target-present window reports a target
total of zero and withholds the interval, as the combined estimate withholds recall. Unknown
observations are not target absence. A census covariance of zero is a real zero. A constant sample
can still produce a zero variance; the interval is not a guarantee, the same limit the combined
estimate already states.

`by_source` status follows the paired review budget. An unmatched or unmeasured budget leaves a
computed gain in place and makes the collection inconclusive. Equal selected counts are not equal
review cost. Withheld windows and sibling offers are cost. A sibling has no inclusion probability.
Recorded minutes do not change the window budget.

The frame and the predicates are in `corpus/evaluation/domains.py`. Collection recall is in
`collection_metrics.py`, shared-stratum covariance in `covariance.py`, membership in
`membership.py`, and per-collection cost in `exposure.py`. `exposure.py` is 262 lines: the frame
check and the costs are one report, and splitting them would separate that check from the numbers
it withholds.

Current behavior is in
[Evaluating selection](../current/corpus/discovery-runs.md#evaluating-selection). The contract
catalog lists 1.24.0 in [Contracts](../current/contracts.md). The specification's evaluation
paragraph now requires the per-collection report.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Unequal weights, shared-stratum covariance, no reviewed sample, incomplete provenance, negative gain, and the frozen command schema | `.venv/bin/pytest tests/corpus/evaluation/test_domains.py tests/corpus/evaluation/test_membership.py tests/corpus/evaluation/test_source_report.py` | pass before `make ci`. Shared stratum N=8 n=4 gives design weight 2, totals 2 and 2, covariance -2/3, and variances plus twice covariance equal 8/3. The gain interval is clamped to [-1, 1] |
| A real pair with no origin stays incomplete, collections stay empty, and the log validates | `.venv/bin/pytest tests/corpus/evaluation/test_evaluate_command.py` | pass before `make ci`. Six fixture windows, reason `source record has no origin` |
| Existing paired-review checks still log a comparison the schema accepts | `.venv/bin/pytest tests/corpus/discovery/test_selection_run.py` | pass before `make ci` |
| `make ci` | `make ci` | pass: 2272 passed, 112 deselected. Format, lint, typing, complexity, shell lint, doc links, spec-plan and contracts reported no findings |

Missing, mocked or stale evidence does not prove acceptance. Runtime artifacts stay under
`$DATA_DIR` and are cited by path, not copied here.

## Audit handoff

- `AUD-corpus-evaluation-by-source-1`, nonblocking. Discovery still does not record compute cost,
  so each run's `compute_cost` stays null. Owner: `corpus-selection-evaluation`, whose execution
  path already states that discovery does not record it and that the evaluation run captures
  measured cost.
- Dropped: a constant sample can report variance zero. The combined estimate uses the same
  variance, and [Evaluating selection](../current/corpus/discovery-runs.md#evaluating-selection)
  already says the interval is not a guarantee. A collection with no observed target withholds the
  interval instead of reporting a zero-width one. No further task.
- Dropped: recorded minutes do not gate the window budget. The budget counts offered windows.
  Gating on clock time would reject two reviews of the same windows. No further task.
- Dropped: no ss-video or ss-fusion change. Collection identity is the recording `origin` this
  repository already seals. The evaluator reads the pinned source record. It calls no sibling
  interface and changes no sibling contract. A recording imported without origin stays unbound.

## Close or resume

All acceptance gates passed. The task is removed from the plan. The plan has 124 tasks:
101 agent and 23 human. The next agent task is `corpus-two-source-pilot` and the next
human task is `define-locked-test-policy (optional)`. `corpus-two-source-pilot` still depends on
`authorize-video-corpus-sources`. `self-supervised-corpus` remains planned.
