# Task Record

resolve-data-contract-record-markdown

## Task and scope

- Id / capability: `resolve-data-contract-record-markdown` / `data-contracts`
- State: accepted
- Source: plan task; user explicitly authorized whitespace-only corrections. The preceding
  data-contracts audit is uncommitted and remains active.
- Plan counts at start: 127 agent, 31 human; next agent `development-unstamped-evidence`, next
  human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### resolve-data-contract-record-markdown

`make lint-md` reports overlong lines in the closed event-package development-edit and batch-recovery
records. Consequently `make quality` fails; repository rules say closed records are not rewritten,
including formatting-only corrections without an explicit exception.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Full quality passes while closed record facts and the record policy remain
  respected.
- Scope boundary: Resolve the four Markdown line-length findings in the two closed records without
  changing their historical facts or weakening checks.
- Data and artifact paths: `docs/impl/records/0100-data-contracts-event-package-development-edit.md`,
  `docs/impl/records/0101-data-contracts-event-package-batch-recovery.md`.
- Execution path: The owner decides whether whitespace-only reflow of the affected closed records is
  permitted; apply that decision or another policy-consistent remedy.
- Acceptance gates: `make lint-md` and `make quality` pass; record facts and accepted task text remain
  unchanged and the policy decision is recorded.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: none.

## Implementation

The owner explicitly authorized the correction. Reflowed the four overlong lines in closed records
0100 and 0101 without changing their words or their accepted task blocks. No code, sealed data,
contract or dependency changed. [Contracts](../current/contracts.md) links this decision.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Historical facts unchanged | Compared each file with `git show HEAD:<path>`, normalizing whitespace and comparing fenced accepted tasks byte-for-byte | pass; one-off Python script was not kept |
| Markdown and links | `make lint-md lint-spec-plan` | pass |
| Full quality | `UV_NO_BUILD_ISOLATION=1 UV_CACHE_DIR=/tmp/ss-track-record-format-uv-cache make quality` | pass; full test suite, coverage, Markdown and package builds. Build used installed dependencies because network access is restricted |
| Required CI | `make ci` on the same code in the preceding audit | pass; 2631 tests passed and 154 deselected |

## Audit handoff

No new finding. Reviewed the word and accepted-task comparisons, the record index, plan removal,
Markdown checks and the full quality result. The existing `development-unstamped-evidence` task
remains owned by the open group audit and is unaffected by this correction.

## Close or resume

All gates passed. The human-gated task left the plan; the Contracts page and records index link this
record. Plan counts after: 127 agent and 30 human tasks. `data-contracts` remains planned; its group
audit stays open for `development-unstamped-evidence`.
