# Task Record

event-package-development-edit

## Task and scope

- Id / capability: `event-package-development-edit` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `bd4e481`, no unrelated dirty files.
- Plan counts at start: 127 agent, 30 human; next agent `event-package-development-edit`, next
  human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### event-package-development-edit

An event package cannot follow the development-stage rule: `make proto-gen` writes an image only
when it is missing or identical, and `make proto-check` holds the image and `buf breaking` to the
committed `1.0.0`, so an architecture fix to an event message can only be made as a new version.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: In the development stage, an edit of an event proto under
  `src/ss_track/contract/proto/` regenerates its `1.0.0` image and bindings in place and re-pins its
  registry entry with one command, and `make proto-check` passes. In the released stage the image
  stays frozen and `buf breaking` classifies a new version, as today.
- Scope boundary: The proto build and its gate only. JSON Schema contracts already edit in place.
  No event message changes in this task, and a released image is never rewritten.
- Data and artifact paths: `src/ss_track/contract/build.py`, `src/ss_track/contract/image.py`,
  `contracts/event/`, `contracts/registry.yaml`, `tests/contract/`.
- Execution path: Read the registry stage in the proto build. In development, rewrite the `1.0.0`
  image and the generated bindings, update the registry pins and skip `buf breaking` against the
  previous image. In released, keep the current behavior.
- Acceptance gates: A fixture proto edit in a development private set regenerates `1.0.0` and passes
  `make proto-check`; the same edit in a released set is refused as a frozen image change; a second
  event version in development fails the stage check. `make ci` passes.
- Documentation target: [Runner](current/runner.md).
```

- Amendments: none.

## Implementation

`contract/build.py` reads the stage, validates the stage rules, re-pins development event images
through staged contract-set validation and the existing locked publisher, and refreshes bindings.
The check validates registry pins and skips breaking comparison only in development. Released
images remain immutable. No event schema, public interface or dependency changed. See
[Runner](../current/runner.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Development edit and re-pin, released refusal, second version | `.venv/bin/pytest -q tests/contract/test_development_build.py` | pass; private copied set and proto fixture, including a breaking rename |
| Generated shipped artifacts | `make proto-gen proto-check` | pass, no event changes |
| Full required gate | `make ci` | pass; 2631 tests passed, 129 deselected |
| Plan and links | `make lint-spec-plan lint-doc-links` | pass |

## Audit handoff

`AUD-event-package-development-edit-1`: The staged set is checked one package at a time, so a
private development copy with both `event/analytics/1.0.0.binpb` and
`event/clock/1.0.0.binpb` removed refuses generation on the missing clock image. This prevents
recovery in one command. Owner: `event-package-batch-recovery`. Reproduced by copying the shipped
set to a temporary directory, deleting those files, and calling `write_artifacts(root)`; the
one-off script was not kept. Reviewed development and released paths, pins, stage checks, generated
bindings and imported descriptor effects.

## Close or resume

All acceptance gates passed. The current Runner page and records index are updated. The original
task is removed; the recovery finding is scheduled. Plan counts after: 127 agent, 30 human. No capability
changed status; `data-contracts` remains planned.
