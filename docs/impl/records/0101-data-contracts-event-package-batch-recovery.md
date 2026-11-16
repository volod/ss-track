# Task Record

event-package-batch-recovery

## Task and scope

- Id / capability: `event-package-batch-recovery` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `fa8bcac`, no unrelated dirty files.
- Plan counts at start: 127 agent, 30 human; next agent `event-package-batch-recovery`, next human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### event-package-batch-recovery

The development generator validates the whole set after staging one package. If two event images
are missing, the first staged update is refused because the other image is still missing, although
both can be regenerated from their protos. This prevents recovery of an incomplete development set.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: One generation command restores all missing development event images and
  updates their pins together while preserving released images.
- Scope boundary: Event artifact staging and publication; no event message changes.
- Data and artifact paths: `src/ss_track/contract/build.py`, `contracts/event/`, `tests/contract/`.
- Execution path: Stage and validate the complete set of event candidates before publication.
  Preserve concurrent-update protections and avoid exposing a partially pinned set on failure.
- Acceptance gates: A private development set with two missing images regenerates and passes the
  contract and proto checks; a failed batch leaves prior images and pins intact; released images stay
  frozen. `make ci` passes.
- Documentation target: [Runner](current/runner.md).
```

- Amendments: none.

## Implementation

`contract/build.py` builds every descriptor and binding before publication;
`contract/development.py` stages and validates the complete candidate set with its updated pins.
`schema/compatibility/batch_publish.py` uses the existing contract-root lock and atomic file writer,
checks registry, image and binding snapshots, and restores written files if publication fails.
Released candidates are checked before any image is created and existing released images remain
untouched. No event message, public CLI, dependency or contract changed. See
[Runner](../current/runner.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Two missing images, full set checks, invalid candidates, released images | `.venv/bin/pytest -q tests/contract/test_development_build.py` | pass; private copies with edited proto, contract and proto checks |
| Failed publication and concurrent changes | `.venv/bin/pytest -q tests/contract/test_batch_publish.py tests/contract/test_development_build.py` | pass; injected image, binding and registry write failures, stale registry and image snapshots |
| Shipped generation and check | `make proto-gen proto-check` | pass; no event contract changed |
| Full required gate | `make ci` | pass; 2635 tests passed, 134 deselected |
| Plan and links | `make lint-spec-plan lint-doc-links` | pass |

## Audit handoff

Reviewed candidate generation, full-set validation, stage changes, stale snapshots, rollback,
released image behavior and binding generation. No finding requires routing. Image and registry
replacement use separate atomic writes: a concurrent reader may temporarily refuse an inconsistent
set during publication. This is a fail-closed transient condition and needs no follow-up; retrying
after generation is documented. An interrupted process can be recovered by rerunning generation.

## Close or resume

All acceptance gates passed. The Runner page and records index are updated and the completed task is removed.
Plan counts after: 126 agent, 30 human; next agent is `data-contracts-audit` (optional). No
capability changed status; `data-contracts` remains planned.
