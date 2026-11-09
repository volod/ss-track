# corpus-balanced-review-budget

## Task and scope

- Id / capability: `corpus-balanced-review-budget` / `self-supervised-corpus`
- State: active
- Source: real two-source pilot comparison; start commit
  `21dae935e84a00431257617804114e65a4cb546d`. Existing working-tree changes belong to active
  pilot, authorization, evaluation, progress and adaptive-motion work.
- Plan counts at start: 104 agent and 23 human; next agent `corpus-two-source-pilot`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-balanced-review-budget

Equal selection counts can have unequal review cost when the selections overlap a shared audit
sample differently. For example, 100 selections with audit overlaps of 15 and 13 add 85 and 87
windows respectively. The current queues cannot add work to the smaller arm, so an otherwise
usable paired comparison is inconclusive even when two extra windows could balance review effort.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A reviewer can follow a predeclared, reproducible matched-workload protocol
  without changing the random baseline or treating extra review windows as audit evidence.
- Scope boundary: Paired review queues and workload accounting; padding never changes selection,
  independent audit weights or inferred observations, and unavailable work stays inconclusive.
- Data and artifact paths: `src/ss_track/corpus/review/`, `src/ss_track/corpus/evaluation/`,
  `tests/corpus/`, `contracts/`, and `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Define and contract a sealed, pre-review padding declaration with deterministic
  seed and eligible unselected pool windows. Make review and freeze validate padded offers, report
  their cost in the matched-budget comparison, and keep their observations out of audit estimates.
  Preserve existing review and freeze compatibility; refuse conflicting or unverifiable padding.
- Acceptance gates: Hand-counted fixtures cover the 85-versus-87 example, equal and unmatchable
  workloads, withheld windows, replay, tampering, independence from audit estimates and old review
  compatibility. The report distinguishes padding from selection and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: padding may expose useful targets, so selected-only recall cannot stand for total
  review yield. The fairness and estimand need research before implementation. Revised task:

```markdown
#### corpus-balanced-review-budget

Equal selection counts can have unequal review cost when the selections overlap a shared audit
sample differently. For example, 100 selections with audit overlaps of 15 and 13 add 85 and 87
windows respectively. The current queues cannot add work to the smaller arm, so an otherwise
usable paired comparison is inconclusive even when two extra windows could balance review effort.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Research: yes
- Dependencies: none.
- User-visible outcome: A reviewer can follow a predeclared, reproducible matched-workload protocol
  without changing the random baseline or treating extra review windows as audit evidence.
- Scope boundary: Paired review queues and workload accounting; padding never changes selection,
  independent audit weights or inferred observations, and unavailable work stays inconclusive. Do
  not hide findings from padded windows or represent selected-only recall as total review yield.
- Data and artifact paths: `src/ss_track/corpus/review/`, `src/ss_track/corpus/evaluation/`,
  `tests/corpus/`, `contracts/`, and `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Define and contract a sealed, pre-review padding declaration with deterministic
  seed and eligible unselected pool windows. Make review and freeze validate padded offers, report
  their cost in the matched-budget comparison, and keep their observations out of audit estimates.
  Preserve existing review and freeze compatibility; refuse conflicting or unverifiable padding.
- Acceptance gates: Hand-counted fixtures cover the 85-versus-87 example, equal and unmatchable
  workloads, withheld windows, replay, tampering, independence from audit estimates and old review
  compatibility. The report distinguishes padding from selection and shows its observed findings;
  an evidence-backed decision that padding cannot support a fair comparison is a valid negative.
  `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: separately recorded selection passes can balance actual work without changing either
  draw or discarding padding discoveries. Evaluate that alternative before choosing a protocol.
  Revised task:

```markdown
#### corpus-balanced-review-budget

Equal selection counts can have unequal review cost when the selections overlap a shared audit
sample differently. For example, 100 selections with audit overlaps of 15 and 13 add 85 and 87
windows respectively. The current queues cannot add work to the smaller arm, so an otherwise
usable paired comparison is inconclusive even when two extra windows could balance review effort.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Research: yes
- Dependencies: none.
- User-visible outcome: A reviewer can follow a predeclared, reproducible matched-workload protocol
  without changing the random baseline or treating extra review work as audit evidence.
- Scope boundary: Paired review queues and workload accounting; repeated reviews or padding never
  change selection or independent audit weights, and unavailable work stays inconclusive. Do not
  hide findings from extra windows or represent selected-only recall as total review yield.
- Data and artifact paths: `src/ss_track/corpus/review/`, `src/ss_track/corpus/evaluation/`,
  `tests/corpus/`, `contracts/`, and `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Evaluate separately recorded repeated selection passes and deterministic padding;
  choose and contract a pre-review protocol that proves completed work and preserves independent
  audit observations. Define how disagreements and findings in extra windows are handled. Make
  review and freeze validate the work and report its cost, preserving existing compatibility.
- Acceptance gates: Hand-counted fixtures cover the 85-versus-87 example, equal and unmatchable
  workloads, withheld windows, replay, tampering, independence from audit estimates and old review
  compatibility. The report distinguishes added work from selection and shows its findings;
  an evidence-backed decision that padding cannot support a fair comparison is a valid negative.
  `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

## Implementation

The verified pilot queues offer 317 versus 319 windows despite equal selections of 100, because
the 232-window common audit overlaps 15 versus 13 selections. An evaluator correctly refuses
to call that review budget matched. A simple two-window padding proposal preserves audit weights
but creates a different problem: a reviewer can find targets in those added windows, and ignoring
those discoveries would misrepresent total review yield. Selecting a scientifically defensible
workload protocol and its estimand remains research, before a contract or implementation.

A second candidate protocol reviews the shared 232-window audit once, then separately reviews all
100 selected windows per method, including repeats of audit windows. It makes 100 selection-pass
exposures per arm without changing either selection or suppressing extra discoveries. The current
review declaration stores one decision per candidate and does not prove repeated work or separate
audit and selection opinions. A contract and evaluation changes must record the completed passes,
keep independent audit observations authoritative for the estimate, and handle disagreements;
merely relabeling existing unique queue counts would invent review work.

The grouping review is also unresolved, so no blinded audit has been presented and the eventual
paired runs and their overlap may change.

## Acceptance evidence

Pending.

## Audit handoff

- `AUD-corpus-balanced-review-budget-1`: An apparently balanced queue can hide discoveries in
  padding if only the 100 selected windows count toward yield. The open
  `corpus-balanced-review-budget` task owns a defensible protocol, visibility of padding findings
  and the associated contracts and tests.
- Further audit is pending.

## Close or resume

In progress.
