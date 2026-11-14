# Remote link review plan

## Task and scope

- Id / capability: `remote-link-review-plan` / `self-supervised-corpus`
- State: accepted
- Source: user request; start commit `21dae935e84a00431257617804114e65a4cb546d`; the working tree
  contains the prior pilot and interactive review work.
- Plan counts at start: 104 agent and 23 human; next agent `corpus-two-source-pilot`, next human
  `define-locked-test-policy (optional)`.
- Accepted request: "please update plan.md with task to run and link to description how to run
  discover review-links command on different host"
- Amendment: user requested an end-to-end command chain to prepare the dataset and run the review
  on another computer.
- Amendment: user requested an agent implementation task for the cross-host review workflow.

## Implementation

Added the human-gated `review-pilot-recording-links` task and made the pilot depend on it. Added the
required agent task `corpus-portable-link-review` and specified its portable handoff and evaluation.
The [other-host instructions](../current/corpus/leakage-review.md#review-on-another-host) provide
commands to transfer the working checkout, minimal source and sealed records, start or resume the
review, return the checkpoint, and run the link checker. The transfer excludes staged frames and
pretrained models. The existing link command validates the returned file; related pairs require
regrouping, and uncertainty remains explicit.

## Acceptance evidence

- Local `rsync -aR` with hard links assembled only the documented `import/`, corpus manifest and
  link record into an isolated data root. A pseudo-terminal run of `discover review-links` opened
  all 136 pilot pairs and saved an empty checkpoint; no judgments were invented. SSH transfer and
  installation on a second computer remain for the human review task.
- `make ci` passed: 2309 tests passed, 112 deselected, including format, lint, typing, complexity,
  documentation links, specification and plan integrity, and frozen contract checks.
- `make lint-md`, `make lint-doc-links`, and `make lint-spec-plan` passed.

## Audit handoff

The manual transfer requires operator-selected hosts and does not coordinate checkpoints across
computers; `corpus-portable-link-review` owns the verified handoff and conflict detection. The actual
pilot review is owned by `review-pilot-recording-links`. The independent window audit remains owned
by `review-video-corpus-sample`.

## Close or resume

Accepted. After planning, 105 agent and 24 human tasks remain. The next agent task is
`corpus-portable-link-review`; the next human task is `define-locked-test-policy (optional)`.
The current capability remains planned.
