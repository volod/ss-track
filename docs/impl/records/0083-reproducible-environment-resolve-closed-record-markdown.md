# Resolve closed record Markdown

## Task and scope

- Id / capability: `resolve-closed-record-markdown` / `reproducible-environment`
- State: accepted
- Source: plan task; user authorized a formatting-only exception. Existing uncommitted work includes
  the shared-evidence and ARM CI changes.
- Plan counts at start: 135 agent, 29 human; next agent `recording-capture-vocabulary`, next human
  `resolve-closed-record-markdown`.
- Accepted task:

```markdown
#### resolve-closed-record-markdown

The closed shared-evidence-primitives record contains a line longer than the Markdown lint limit.
`make lint-md` reports MD013 for line 8 of that record, so `make quality` cannot pass. Closed
records cannot be rewritten under the repository rules, including to reflow the line, without a
human decision about that rule.

- Serves: `reproducible-environment` -- [Capability registry](../design/spec.md#capability-registry)
- Agent status: HUMAN-GATED
- Dependencies: none.
- User-visible outcome: Markdown lint and the full quality workflow can pass while record history
  remains accurate and the repository's record policy is respected.
- Scope boundary: Resolve the formatting violation in the closed record; do not weaken lint checks
  or alter its historical facts.
- Data and artifact paths: `docs/impl/records/0081-corpus-provenance-shared-evidence-primitives.md`,
  `AGENTS.md`.
- Execution path: The owner decides whether a formatting-only correction to this closed record is
  permitted, then apply the authorized correction or an alternative consistent with the policy.
- Acceptance gates: `make lint-md` passes with the record's task facts unchanged; `make quality`
  passes, and the policy decision is recorded.
- Documentation target: [Developer Tooling](current/developer-tooling.md).
```

- Amendments: none.

## Implementation

With the user's explicit formatting-only exception, wrapped the plan-counts line in record 0081.
Its words and historical facts are unchanged. See [Developer Tooling](../current/developer-tooling.md).

## Acceptance evidence

| Gate | Exact command or artifact | Result and limit |
| --- | --- | --- |
| Record facts unchanged | Whitespace-only line wrap in record 0081 | Passed. |
| Markdown | `make lint-md` | Passed. |
| Required CI | `make ci` | Passed: 2385 tests passed, 112 deselected. |
| Full quality | `UV_NO_BUILD_ISOLATION=1 UV_CACHE_DIR=/tmp/ss-track-quality-uv-cache make quality` | Passed: 2489 tests passed, 8 skipped, 92.85% coverage; Markdown and builds passed. |

## Audit handoff

None identified. Reviewed the record text, plan dependency and the resulting quality gates.

## Close or resume

Accepted. Removed the human-gated task and linked this record from developer tooling. Plan counts
are 135 agent and 28 human; the capability remains shipped.
