# corpus-balanced-review-budget

## Task and scope

- Id / capability: `corpus-balanced-review-budget` / `self-supervised-corpus`
- State: accepted
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

Decision: the selection-pass protocol is chosen and padding is rejected. Padding pays for windows
neither method chose, and its findings belong to no method. The amount it needs follows the audit
draw, not the methods: in the pilot it is two windows, and another audit seed would change it.
Counting its findings would credit a method with random review, and ignoring them would hide
discoveries. Under a selection pass, each run's work is its selected count by construction. The
audit stays the only input to the estimate, and every pass finding is reported. That includes
targets outside the audit and windows that disagree with the run's review. The protocol has no
seed and nothing to tune, so it is fixed before review.

Implementation:

- `declaration/corpus-review` 1.2.0 and `record/corpus-freeze` 1.2.0 add an optional
  `selection_pass`: the reviewer, optional minutes, and one observation per window.
  `corpus/review/selection_pass.py` reads it and bounds it to the selected windows the run offers.
  Export, freeze and evaluation refuse a repeated, unselected or withheld window
  (`MANIFEST_INVALID`), so a pass cannot be replayed onto another run. Freeze copies the pass
  with its windows ascending, and `read_freeze` refuses a resealed record whose pass windows are
  out of order or repeated.
- `result/command` 1.25.0 adds the `selection_pass` protocol and `review_budget.selection_pass`.
  `corpus/evaluation/passes.py` counts expected, reviewed and missing windows, audit repeats,
  observations, targets outside the audit, disagreements and total exposures. `workload.py`
  compares pass counts, and treats an incomplete pass, a pass in one review only, or passes
  without one shared audit as unmeasured.
- `discover queue` appends a commented selection-pass block that lists every selected window
  with a blank observation, so the protocol can be followed without writing window ids by hand.
- The spec, review-and-freeze, discovery-runs and contracts pages state the protocol. The plan
  removes this task, drops it from `corpus-selection-evaluation`'s dependencies, and names the
  protocol in the pilot, evaluation and human review tasks.

No real-data run was possible in this change. The pilot's link review is unresolved, so no blinded
audit or pass has been reviewed, and the pilot data root is not on this host. The protocol
was run end to end through `discover run`, `discover evaluate` and `corpus freeze` on staged
fixtures.

## Acceptance evidence

- `tests/corpus/evaluation/test_selection_pass_budget.py` hand-counts the pilot's 85-versus-87
  shape: 500 windows, a 232-window audit, and 100 selections overlapping it by 15 and 13.
  `shared_audit` is unmatched at 85 versus 87. Complete passes are matched at 100 versus 100, with
  15 and 13 repeats and 432 exposures, and recall, gain and strata stay unchanged. It also covers
  findings outside the audit, disagreements and unknowns, an incomplete pass, a pass in one review
  only or without a shared audit, unequal selections (98 versus 100), a withheld selection, and a
  pass replayed onto the other run.
- `tests/corpus/review/test_selection_pass.py` covers the template block, a blank pass, freeze
  carry-through without adding an observation, unselected and locked windows, a repeat, an edited
  (`RECORD_TAMPERED`) and a resealed (`RECORD_INVALID`) freeze record, and old-review compatibility
  against corpus-review and corpus-freeze 1.1.0.
- `tests/corpus/evaluation/test_evaluate_command.py` logs a matched `selection_pass` comparison
  checked against `result/command` 1.25.0. It also checks that a comparison without a pass is still
  a 1.24.0 record.
- `make ci`: 2337 passed, 112 deselected. `make lint-md`, `make lint-spec-plan` and
  `make lint-doc-links` pass.

## Audit handoff

- `AUD-corpus-balanced-review-budget-1`: An apparently balanced queue can hide discoveries in
  padding if only the 100 selected windows count toward yield. The open
  `corpus-balanced-review-budget` task owns a defensible protocol, visibility of padding findings
  and the associated contracts and tests.
- `AUD-corpus-balanced-review-budget-1` is resolved by this change. Pass findings, including
  targets outside the audit, are reported and never hidden, and selected-only recall is not
  presented as review yield.
- `AUD-corpus-two-source-pilot-2` (the 317 versus 319 queues) is resolved by the `selection_pass`
  protocol. `corpus-two-source-pilot` now freezes that protocol before `discover blind`.
- `AUD-corpus-balanced-review-budget-2`: pass disagreements compare each pass with its own run's
  review. A window both runs selected outside the audit, which no review observed, is not
  compared across the two passes. Owner: `corpus-selection-evaluation`, whose execution path and
  acceptance gates now state it.
- `AUD-corpus-balanced-review-budget-3`: `tests/corpus/links/test_interactive.py` read the pty
  once and could see only the echoed `q` before the banner. It failed once in `make ci`. Fixed in
  this change by draining the terminal; dropped.
- Dropped: `corpus/evaluation/workload.py` is 260 lines. Pass accounting already moved to
  `passes.py`, and the rest is one cohesive protocol rule.

## Close or resume

Accepted. All gates passed. The task left the plan; 103 agent and 24 human tasks remain. The next
agent task is `corpus-two-source-pilot`; the next human task is
`define-locked-test-policy (optional)`. The capability remains planned.
