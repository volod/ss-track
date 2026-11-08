# corpus-blinded-audit-review

## Task and scope

- Id / capability: `corpus-blinded-audit-review` / `self-supervised-corpus`
- State: accepted
- Source: plan task, start commit `6579321`; working tree clean.
- Plan counts at start: 127 tasks, 104 agent and 23 human. Next agent
  `corpus-blinded-audit-review`, next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-blinded-audit-review

The current review queue exposes scores and selection reasons to an auditor and cannot record blinding.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A reviewer can inspect the common audit sample without selection, source-label
  or annotation cues, then submit traceable observations with independence and blinding provenance.
- Scope boundary: Review of offered non-locked windows and recorded procedure; no automatic judgment,
  review of locked footage, new ground-truth labels or claim that recorded blinding is verified.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `contracts/`,
  `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Add a blinded presentation and stable private mapping back to existing review and
  freeze candidates; hide score, method, offer reason, upstream labels and source-derived target cues.
  Preserve audit eligibility and offer constraints, state whether independence and blinding were
  declared, and report review effort. Contract any new interchangeable records and keep unblinding
  and provenance reproducible. Hide filenames and source identifiers while recognizing that visual
  content itself may reveal the source.
- Acceptance gates: Deterministic fixtures show matched audit samples, unselected windows, withheld
  locked material, no identifying metadata or scores in the blinded presentation, reversible mapping,
  unknown observations and refusal of forged or mismatched inputs; `make ci` passes.
- Documentation target: [Review and freeze](current/corpus/review-and-freeze.md).
```

- Amendments: none.

## Implementation

`discover blind` writes the common audit sample for runs that share a pool, frame set and audit
design. Selected and unselected sampled windows are shown together. Windows the sample did not draw,
and sibling windows, stay out. Locked sampled windows are counted as `locked_without_policy` and
their stream ids stay in the private mapping. Item ids follow the SHA-256 of the frame set, the
audit seed, the stream and the candidate. Picture files are named by offset and hold PNG bytes of
the staged frames.

The reviewer file is `declaration/audit-review` 1.0.0. It is not valid until the reviewer and
`reviewer_minutes` are set. `discover unblind` maps each item back to one corpus review 1.1.0 per
run. `record/corpus-freeze` 1.1.0 copies independence, blinding, minutes and `audit_id`
only when the review stated them, so a review without those fields keeps the previous record shape.
The private mapping is `record/audit-blinding` 1.0.0 at
`$DATA_DIR/self-supervised-corpus/<audit-id>/blinding.json`. `result/command` 1.21.0 adds
`presented`, `unblinded` and `blind`.

`discover evaluate` reports a shared declaration, `unrecorded` when both reviews omit it, or
`mixed` when they differ, plus the recorded minutes. A stated value is not a verification.

Current behavior is in [Review and freeze](../current/corpus/review-and-freeze.md). The
specification sentence for the blinded audit is in
[video corpus formation](../../design/spec.md#41a-self-supervised-video-corpus-formation).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Matched samples, unselected windows, withheld locked material, no source cues, reversible mapping, unknown observations, forged and mismatched inputs | `.venv/bin/pytest tests/corpus/review/test_blind.py` | pass before `make ci`; fixture clips only |
| A review without provenance still freezes without those fields | `.venv/bin/pytest tests/corpus/review/test_freeze.py` | pass before `make ci` |
| `make ci` | `make ci` | pass: 2242 passed, 112 deselected. Format, lint, typing, complexity, shell lint, doc links, spec-plan and contracts reported no findings |

## Audit handoff

- `AUD-corpus-blinded-audit-review-1`, nonblocking for this task. `discover evaluate` returns
  statuses `estimated` and `inconclusive` and fields the newest `result/command` does not accept,
  including `audit`, `observations`, `review_blinding`, `review_independence`,
  `review_effort_minutes` and `limits`. Evidence: `corpus/evaluation/report.py` against that
  contract. The production CLI does not check the result, so the command succeeds, and a pytest
  run of the CLI would fail the command-result hook. Impact: a reader cannot validate the
  comparison. Owner: `corpus-evaluation-result-contract`, whose text states this.
- Dropped: pictures may show the source. The task scope accepts that, and the specification states
  it. No scrubbing was in scope.
- Dropped: the ordinary queue template still shows selection and scores. That file is the
  corpus-building review. The blinded packet is the audit presentation.
- Dropped: a recorded `declared` is not a check that the reviewer was kept from the queue or the
  mapping. The task forbids that claim, and the current page states it.
- Dropped: discovery still does not record compute cost. `corpus-selection-evaluation` already
  states that the comparison must capture measured cost and that discovery does not record it.
- Dropped: no ss-video or ss-fusion change. Blinding uses staged ss-track frames and the existing
  review and freeze records, and it calls no sibling interface.

## Close or resume

All acceptance gates passed. The task is removed from the plan. `corpus-evaluation-review-budget`
now depends on nothing, and `corpus-two-source-pilot` depends only on
`authorize-video-corpus-sources`. The plan has 127 tasks: 104 agent and 23 human. The next agent
task is `corpus-evaluation-result-contract` and the next human task is
`define-locked-test-policy (optional)`. `self-supervised-corpus` remains planned.
