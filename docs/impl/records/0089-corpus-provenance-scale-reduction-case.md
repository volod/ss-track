# Scale reduction case

## Task and scope

- Id / capability: `scale-reduction-case` / `corpus-provenance`
- State: accepted
- Source: plan task; start commit `d1d3d00`; worktree clean.
- Plan counts at start: 134 agent, 28 human; next: `scale-reduction-case`, `define-locked-test-policy`.
- Accepted task:

```markdown
#### scale-reduction-case

No generated case makes a target smaller, so the benchmark cannot show where a module stops seeing
a target as it covers fewer pixels, which is the offline form of long-range detection.

- Serves: `corpus-provenance` -- [Deterministic cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A recipe declares a scale-reduction case, and staging writes frames
  resampled by its factor with a stored `scale` label transform.
- Scope boundary: Whole-frame reduction by a declared factor, with an area-average filter that is
  part of the transform revision, and a label transform that states the factor. No blur, noise,
  atmosphere or optics model, no enlargement and no range claim. A graded list of factors belongs
  to `robustness-severity-sweep`, and deriving the labels belongs to `generated-case-labels`.
- Data and artifact paths: `src/ss_track/corpus/cases/`, `tests/corpus/cases/`, `contracts/`,
  `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Add the transform in integer arithmetic, so one recipe gives identical bytes on
  x86-64 and arm64, record the output dimensions in the bundle, and extend `corpus preview` to
  show the reduced frame beside its parent.
- Acceptance gates: Hand-computed frames match for even and odd dimensions and for a factor that
  does not divide them. A rerun is byte-identical, a factor that changes no pixel is refused, and
  a stored case of another revision is refused. The case inherits its parent's split, encounter
  and group and adds to no count. `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

## Implementation

The integer area-average transform, bundle dimensions, black-padded preview and frozen minor
contracts are implemented. The selection must be whole to keep bundle dimensions uniform. The
factor is an integer divisor; label derivation remains in `generated-case-labels`. See
[Corpus](../current/corpus.md#generated-cases).

## Acceptance evidence

| Gate | Evidence | Result and limit |
| --- | --- | --- |
| Area averages, dimensions and label factor | `tests/corpus/cases/test_scale_reduction.py` | Passed: hand-computed even, odd and partial blocks; bundle and preview pixels |
| Repeat, refusal and membership | `tests/corpus/cases/test_scale_reduction.py`, `test_case_membership.py`, `test_case_refusals.py` | Passed: repeat bytes, no-change and revision refusals, inherited membership and counts |
| Revision determinism | `tests/corpus/cases/test_transform_golden.py`, `tests/corpus/hosts/test_fixed_corpus.py` | Passed locally; fixed fixture now includes this transform. No new cross-host measurement was made. |
| Required gate | `make ci` | Passed: 2418 tests, 115 deselected; all CI checks passed. |

## Audit handoff

No findings identified in review of pixel arithmetic, staging, preview, compatibility and contracts.
Label derivation is owned by `generated-case-labels`; the severity sweep is owned by
`robustness-severity-sweep`, as in the accepted scope.

## Close or resume

All gates passed. Updated [Corpus](../current/corpus.md#generated-cases),
[Contracts](../current/contracts.md), the specification and the records index. The completed task
was removed from the plan and its downstream dependency was removed. Plan after: 133 agent tasks,
28 human tasks; next agent is `frame-sequence-source-import` and next human is
`define-locked-test-policy`. Capability remains shipped.
