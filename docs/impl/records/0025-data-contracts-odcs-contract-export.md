# ODCS contract export

## Task and scope

- Id / capability: `odcs-contract-export` / `data-contracts`
- State: accepted.
- Source: plan at `29543e4`; working tree clean.
- Plan counts at start: 108 agent and 22 human tasks; next agent `decode-policy-reimport`,
  next human `select-development-workload`.
- Accepted task:

```markdown
#### odcs-contract-export (optional)

A data catalog may expect ODCS, and a generated view costs little once contracts exist.

- Serves: `data-contracts` -- [Dataset
  descriptors](../design/spec.md#175-dataset-descriptors-and-self-service)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts export --format odcs` writes one ODCS document per
  contract.
- Scope boundary: A generated view, never authored or read back. A tagged union is listed as the
  union of its branches, and what ODCS cannot state is named in `customProperties`.
- Data and artifact paths: `src/ss_track/schema/`, `tests/schema/`.
- Execution path: Project each contract and validate against the official ODCS JSON Schema, pinned by
  hash.
- Acceptance gates: Every document validates, with id and version matching its contract. Every
  property appears, and each construct lost in projection is listed.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.
```

- Amendments: none.

## Implementation

`schema/odcs_projection.py` projects each latest frozen contract into a flat property catalog,
resolves local and registered references with cycle protection, merges tagged-branch paths without
collisions, and inventories source keywords conservatively. Each view includes its original JSON
Schema and source pointers, so catalog consumers can see what the projection does not enforce.
`schema/odcs.py` checks
the bundled upstream ODCS 3.2 schema hash, validates all documents and writes one JSON file per
contract. The schema and Apache 2.0 license ship under `contracts/meta/standards/`; the dataset
descriptor now copies nested standard files as part of its contract set.

The existing `contracts docs` command returned status `written` and `files`, neither allowed by the
then-current `result/command` schema. Version 1.4.0 adds those fields and the new `exported` status;
the CLI regression test covers both commands. No runtime dependency was added. Current state:
[contracts](../current/contracts.md#odcs-catalog-export).

## Acceptance evidence

| Gate | Command or artifact | Result and limit |
| --- | --- | --- |
| Official validation and coverage | `.venv/bin/python -m pytest tests/schema/test_odcs.py` | every registered contract validates; independent traversal checks every property and schema keyword |
| Tagged union and refusal | `tests/schema/test_odcs.py` | merged branch fields, conflicting types, recursive references and missing or changed schema checked |
| Installed distribution | `tests/schema/test_packaging.py` | wheel includes schema and license and exports without a checkout |
| Command run | `.venv/bin/ss-track contracts export --format odcs --out .data/odcs/odcs-contract-export-v3` | 11 documents generated and validated |
| Repository gate | `make ci` | pass: 1549 tests and all CI checks |

## Audit handoff

Reviewed source pointer coverage, branch merges, recursive references, copied source schemas, official
schema pin, shared definitions and installed-wheel operation. The existing reference-docs
result-contract mismatch was fixed in `result/command` 1.4.0 with a CLI regression case. The ODCS
view cannot itself express all source rules; every source keyword and its original schema are retained
in `customProperties`, and
the source JSON Schema is documented as authoritative. The standalone reference test now checks the
third-party schema separately and verifies its references stay local. No additional finding remains open.

## Close or resume

All acceptance gates passed. The task left the forward-only plan and the current contracts page and
records index link this record. The plan holds 107 agent and 22 human tasks; the next agent task is
`decode-policy-reimport (optional)` and the next human task is `select-development-workload`.
The `data-contracts` capability remains planned with open work.
