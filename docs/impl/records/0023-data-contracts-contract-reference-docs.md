# Contract reference docs

## Task and scope

- Id / capability: `contract-reference-docs` / `data-contracts`
- State: accepted
- Source: plan at `e9cecc3`; no unrelated dirty files.
- Plan counts at start: 108 agent, 22 human; next agent `decode-policy-reimport`, next human `select-development-workload`.
- Accepted task:

```markdown
#### contract-reference-docs (optional)

A reader of a contract should not need to read JSON Schema to learn what a field means, or how
records link.

- Serves: `data-contracts` -- [Identity and versions](../design/spec.md#172-identity-and-versions)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts docs --out <dir>` writes a data dictionary per contract,
  the first version of each field, and a lineage graph from `x-references`.
- Scope boundary: Generated Markdown only. No site or hosting. The change log stays the authored
  text.
- Data and artifact paths: `src/ss_track/schema/`, `tests/schema/`.
- Execution path: Render from frozen contracts and add dangling-reference detection to the check.
- Acceptance gates: Output is deterministic and lists every property and enum value. A dangling
  `x-references` target fails `make lint-contracts`.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.
```

## Implementation

`schema/docs.py` renders versioned property dictionaries and lineage edges from frozen schemas.
`cli.py` exposes `contracts docs --out`; `schema/check.py` resolves annotations against the latest
frozen target. No contract files or authored change logs changed. Current state:
[contracts](../current/contracts.md#generated-reference).

## Acceptance evidence

| Gate | Command or artifact | Result |
| --- | --- | --- |
| Deterministic dictionaries and fields | `tests/schema/test_docs.py` | pass |
| Dangling annotation rejected | `tests/schema/test_check.py::test_dangling_annotation_fails_contract_gate` | pass |
| Command output | `.venv/bin/ss-track contracts docs --out /tmp/ss-track-contract-reference` | pass: ten dictionaries and lineage |
| Required gate | `make ci` | pass: 1520 tests |

## Audit handoff

Reviewed renderer traversal, version ordering, annotation resolution, CLI output and tests. No
outstanding findings identified. Temporary generated output was removed after inspection.

## Close or resume

All gates passed. Removed the task from the plan; no task depended on it. The current page and
records index link this record. Plan counts after: 107 agent, 22 human; next agent
`decode-policy-reimport (optional)`, next human `select-development-workload`. Capability remains
planned with open work.
