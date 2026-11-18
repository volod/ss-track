# Task Record

data-contracts-audit

## Task and scope

- Id / capability: `data-contracts-audit` / `data-contracts`
- State: active
- Source: plan task; starting commit `dca3cab`, no unrelated dirty files.
- Plan counts at start: 126 agent, 30 human; next agent `data-contracts-audit` (optional), next
  human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### data-contracts-audit (optional)

A development-stage gate that lets a contract change without a version must still refuse every
change it did not pin, or formats drift silently before release.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: The stage rules, the contract-set check on the read path and the regenerate
  flow are reviewed against section 17.7, and every finding is fixed or routed.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `contracts/`, `src/ss_track/schema/`, `tests/schema/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  section 17.7 and `AGENTS.md` against the history gate, the registry meta-schema, the shared read
  path and the data-root stamp. Decide whether a meaning-only contract edit, such as a changed enum
  meaning, must also ask a data root for regeneration, since the stamp holds structure fingerprints
  only.
- Acceptance gates: Every section 17.7 rule has a failing fixture or is named as human judgment.
  Every finding is fixed, routed to a task or dropped with its reason, and `make quality` passes.
  Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: none.

## Implementation

Reviewed section 17.7, the current contract documentation, records 0016 through 0030 and 0099
through 0101, the registry meta-schema and stage rules, Git history, installed readers, root stamp,
JSON and event freeze paths, and their tests.

- **Integrity and gaps:** The history gate now detects a release in an intermediate ancestor and a
  later committed return to development, including a subsequent second release and a merge that
  hides the release stage. Runtime readers, contract commands, reference and ODCS exports, and
  dataset descriptors check file hashes, fingerprints and stage before using the set. Previously a
  stale registry fingerprint could be trusted. The root stamp now includes structure and meaning
  fingerprints of record and shared contracts. A legacy structure-only stamp is refused without
  deleting data. Meaning fingerprints include descriptions, so editorial changes are
  conservatively treated as meaning changes. The first sealed write now rechecks and stamps under
  a root lock before publishing, closing the interruption and concurrent-first-write window. Non-
  ASCII, duplicate-key and malformed stamp values are `RECORD_TAMPERED`.
- **Repetition and patterns:** Runtime consumers share `require_runtime_pins` and the existing
  fingerprint and event image checks. The development event batch and JSON freeze retain their
  existing lock and atomic file patterns. The stamp uses the shared strict JSON hooks and atomic
  writer. No sealed record, seal, contract fingerprint or dependency changed.
- **Naming:** `record_written` became `stamp_before_write` to state its new ordering. Names and
  refusal codes were checked against the specification; malformed stamps now use the documented
  `RECORD_TAMPERED` code, rather than a traceback or a stale-set code.
- **Algorithms:** Five warm local runs of installed-set initialization measured 0.029-0.034 s
  before and 0.047-0.062 s after; a full build-gate check measured 1.543-1.565 s, so runtime uses
  focused pin checks instead of repeating the dialect audit. Three 1,000-iteration runs of the
  previous stamp existence path took 0.016-0.017 s; locked rechecks took 0.079-0.081 s. These
  one-off scripts were not kept. This is a fixed per-write cost, not a walk over record contents.
- **Ideas:** No new capability was identified. The unverified unstamped-root case below remains
  required work for the existing capability.

[Contracts](../current/contracts.md) and the authoring guide state the new checks and conservative
regeneration rule. Section 17.7 now requires meaning and shared fingerprints. Existing stamped
roots lacking meanings refuse until regenerated; the check does not delete data or operator inputs.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| In-place pin, version count, release history and return | `.venv/bin/pytest -q tests/schema/registry/test_stage.py` | pass, including regressions for intermediate release and rerelease |
| Runtime pins, stage, regenerated events, failure rollback and release | `.venv/bin/pytest -q tests/schema/validation/test_installed_integrity.py tests/contract/test_development_build.py tests/contract/test_batch_publish.py` | pass on private sets; one-off regeneration does not mutate the shipped contract |
| Structural, shared and meaning changes; damaged and legacy stamps; first write | `.venv/bin/pytest -q tests/corpus/records/test_contract_stamp.py` | pass; real meaning-only private freeze refuses its prior root, old stamp preserves evidence |
| Regenerated root and every 17.7 rule | The stage and stamp tests above; `development-unstamped-evidence` | partial: unstamped sealed evidence remains unverified; see handoff |
| Operator input shape changes and distinguishing editorial intent | Section 17.7 and authoring guide | human judgment: preserve and update each input; semantic intent in prose is not inferable, so all meaning changes conservatively regenerate |
| Full required gate | `UV_NO_BUILD_ISOLATION=1 UV_CACHE_DIR=/tmp/ss-track-record-format-uv-cache make quality` | pass after authorized Markdown correction; coverage, Markdown and package builds passed |
| Required CI | `make ci` | pass; 2631 tests passed, 154 deselected |
| Package build | `UV_NO_BUILD_ISOLATION=1 UV_CACHE_DIR=/tmp/ss-track-audit-uv-cache make build` | pass using installed build dependencies; isolated build could not fetch from the restricted network |
| Plan and documentation links | `make lint-spec-plan lint-doc-links` | pass |

## Audit handoff

- `AUD-data-contracts-audit-1` (blocking): An unstamped root could contain sealed records and be
  treated as fresh. Fixed in the [unstamped-evidence record](0104-data-contracts-development-unstamped-evidence.md);
  the group audit remains open to review the complete change.

- `AUD-data-contracts-audit-2` (blocking): `make lint-md` reports four overlong lines in closed
  records 0100 and 0101. Fixed with the owner-authorized whitespace-only reflow in the
  [formatting record](0103-data-contracts-resolve-data-contract-record-markdown.md).

The earlier meaning-only handoff `AUD-contract-development-baseline-2` is fixed by the new meaning
stamp; shared reference structure is covered too. The event recovery handoff from record 0100 was
fixed by record 0101 and was re-tested. The remaining temporary refusal during multi-file event
publication is fail-closed and documented; no follow-up is needed for that observation.

## Close or resume

The per-change audit, targeted checks, full quality and CI passed. The group audit remains active
in the plan until `development-unstamped-evidence` is completed and re-audited. The current
Contracts page and records index are updated. Plan counts after: 126 agent and 30 human tasks. No
capability changed status; `data-contracts` remains planned.
