# Task Record

development-staged-hashes-provenance

## Task and scope

- Id / capability: `development-staged-hashes-provenance` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `8362654`. Only uncommitted file at start: the closing of
  record 0109 (see that record).
- Plan counts at start: 128 agent, 30 human; next agent `development-staged-hashes-provenance`,
  next human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-staged-hashes-provenance

`corpus compare` reads a `staged-hashes.json` that another host's data root wrote and an operator
carried over, a sealed record crossing data roots, but the record binds no contract set. In the
development stage a host on another commit, whose `record/staged-hashes`, `record/frame-set` or
`shared/types` was edited in place, still writes `schema_version: 1`, so `compare` seals
`identical`, or names differing frames, without proving that both hosts read the records alike.
Spec section 17.7 requires a development handoff of sealed records between data roots to bind the
exporting contract set; only the review handoff does. Reproduction: copy a staged-hashes record
from a root stamped under the shipped set and run `corpus compare` on it under an install whose
`record/staged-hashes` meaning pin differs, on a fresh root: the comparison is sealed `identical`
and the command exits 0. Impact: a cross-host identity or difference claim can rest on records the
two hosts interpret differently.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus compare` refuses a staged-hashes record whose development contract
  pins are absent or differ from the installed set, naming the changed contracts, before it writes a
  comparison. Records with matching pins compare as today, and released records compare by major.
- Scope boundary: The staged-hashes record and the comparison's read of it. Reuse the pins and the
  comparison of `corpus/links/portable_provenance.py` rather than a second statement of either. No
  change to the review handoff or to frame bytes; stale records are regenerated, not migrated.
- Data and artifact paths: `contracts/record/staged-hashes/`, `src/ss_track/corpus/hosts/`,
  `src/ss_track/corpus/links/portable_provenance.py`, `tests/corpus/hosts/`,
  `$DATA_DIR/run/<run-id>/staged-hashes.json`.
- Execution path: Edit `record/staged-hashes` 1.0.0 in place to carry the `contract_set` rows the
  review handoff carries, re-pin it, write them in `corpus hashes` and check both records in
  `compare_staged_hashes` before `_require_comparable` and before any write. Move the row parsing to
  one place both readers use. The edit changes the stamp, and `$DATA_DIR` holds staged-hashes
  records, so the root then refuses every root-taking command: regenerate it under the owner's
  transfer authorization, or add the Human-Assisted regeneration task, in the same change.
- Acceptance gates: A pair with equal frame bytes but another pin for `record/staged-hashes`,
  `record/frame-set` or `shared/types` on one side refuses `RECORD_SCHEMA_UNSUPPORTED` with
  `changed_contracts` and writes no `hash-comparison.json`; a record with no pins refuses; matching
  pins compare as before; a released-stage pair compares by major. The regression fails before the
  fix. `make ci` passes.
- Documentation target: [Contracts](current/contracts.md) and the [Corpus](current/corpus.md)
  section "Across hosts".
```

- Amendments: none.

## Implementation

**Contracts**, each edited in place and re-pinned with `ss-track contracts freeze ... --summary
"Initial contract."`:

- `shared/types` gains `$defs/contract-set`: `null`, or one `{contract, structure, meaning}` row per
  record and shared contract in contract order. This is the row shape `record/link-review-handoff`
  stated inline, moved so that both carriers have one statement.
- `record/link-review-handoff` `contract_set` now references that definition. Its records' bytes
  do not change, and `contracts diff` reports no change because references are compared at their
  use sites; its file and fingerprints moved.
- `record/staged-hashes` requires `contract_set`, with the `provenance` rule under `x-rules`.

**Code.** `core/evidence/carried_pins.py` (new) holds what `corpus/links/portable_provenance.py`
held: `carried_contract_set` writes the installed pins, and `require_carried_contract_set` refuses
absent, null or differing pins with `RECORD_SCHEMA_UNSUPPORTED`, the record, `changed_contracts`
and the carrier's remedy, and unsorted, repeated or incomplete rows with `RECORD_TAMPERED`. It
compares through `contract_stamp.changed_contracts`, the stamp's own rule. `portable_provenance.py`
keeps only the handoff's remedy and its call. `corpus/hosts/host_hashes.py` writes the pins into
every staged-hashes record. `corpus/hosts/hash_comparison.py` checks the left and then the right
record after reading them and before `_require_comparable` and the write, with
`STAGED_HASHES_REMEDY`. A review acceptance compares the local record with the archive's through the
same function, so the carried staged hashes are held to the pins as well as the manifest.

Decisions: the shared definition, because a second inline copy of the rows would be a second
statement of one format; the module under `core/evidence`, because the links and hosts areas both
use it and it rests on the stamp's comparison. Both sides are held to the install, not to each
other: two records from one other commit agree with each other, yet this install's reader would
interpret them. Rejected: checking only the record that came from elsewhere, which `compare` cannot
tell apart.

Compatibility: a staged-hashes record written before this change has no pins and is refused. The
handoff refusal details gain `record: manifest.json`, an addition. No CLI flag, environment variable
or dependency changed. In the released stage the writer sets `null` and the comparison reads by
major. The three re-pinned contracts stale every data root stamped before; see the audit handoff.
The arm64 reproducibility workflow records both sides at one commit, so its pins agree.

Current pages: [Contracts](../current/contracts.md#development-stage), the [Corpus](../current/corpus.md)
section on hosts and its refusal table, and [Leakage review](../current/corpus/leakage-review.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Regression fails before the fix | `.venv/bin/pytest -q tests/corpus/hosts/test_staged_hashes_provenance.py` with only `carried_pins.py` added, writer and comparison unchanged | fail as expected: 11 of 11 (`KeyError: 'contract_set'`; the cross-host cases `DID NOT RAISE`) |
| Equal frame bytes, another pin on one side, refuse and write no comparison | `test_a_host_under_another_contract_set_refuses_before_any_write`: the other root is staged entirely under an install whose `record/staged-hashes` or `record/frame-set` meaning, or `shared/types` structure, differs, on either side | pass: `RECORD_SCHEMA_UNSUPPORTED`, `changed_contracts` names that one contract, no `hash-comparison.json` |
| A record with no pins refuses | `test_a_record_that_states_no_contract_set_refuses` (absent and null, resealed) | pass; damaged rows are `RECORD_TAMPERED` (`test_damaged_pins_are_tampered`) |
| Matching pins compare as before | `tests/corpus/hosts/`, `tests/corpus/records/test_contract_outputs.py`, the portable round trips in `tests/corpus/links/` | pass |
| A released pair compares by major | `test_released_records_carry_no_pins_and_compare_by_major` | pass: `contract_set` is `null`, result `identical` |
| Contracts edited in place and re-pinned | `ss-track contracts freeze` of `shared/types`, `record/link-review-handoff`, `record/staged-hashes`; example `tests/schema/examples/record-staged-hashes.json` resealed with pins; `make lint-contracts` | pass: 0 findings |
| The plan's reproduction | `ss-track corpus compare` on two copies of `$DATA_DIR/run/pilot-hashes-origin-grouped/staged-hashes.json` with a scratch `DATA_DIR` | refused `RECORD_SCHEMA_UNSUPPORTED` naming the record, exit 1, no comparison written; scratch removed, `$DATA_DIR` only read |
| Required CI | `make ci` | pass: 2801 passed, 147 deselected; format, lint, typing, complexity, shell, links, plan, contracts and events clean |
| Contract-artifact tests `make ci` omits | `pytest -m external tests/schema tests/corpus/records tests/contract tests/corpus/links tests/corpus/hosts tests/commands` | pass: 139 passed, including the real freezes on private copies of the edited set |

## Audit handoff

Reviewed: every reader and writer of a staged-hashes record (`corpus hashes`, `corpus compare`,
handoff export and acceptance, the fixed-corpus targets and the arm64 workflow), the handoff path
after the move, released behavior, the generated example and the data root.

- `AUD-development-staged-hashes-provenance-1` (chore needing authorization): `$DATA_DIR` now refuses
  every root-checking command, naming `record/link-review-handoff`, `record/staged-hashes` and
  `shared/types`. It holds one staged-hashes record and no handoff; rebuilding downloads what the
  cache lacks under the owner's transfer cap. Owner: `development-data-root-regenerate-provenance`
  (Human-Assisted lane, added in this change).

No bug or improvement is left open by this change. `run-bundle-store` now names the shared type for
its manifest's contract set, and the group audit's text names the carried pins instead of this task.

## Close or resume

Every gate passed. The task has left the plan; the Contracts, Corpus and Leakage review pages and the
records index are updated, `run-bundle-store` and the group audit are amended, and
`development-data-root-regenerate-provenance` is added to the Human-Assisted lane. `$DATA_DIR`
refuses until that task runs. Plan counts after: 127 agent and 31 human tasks; next agent
`development-stamp-added-contracts` (optional), next human `define-locked-test-policy` (optional).
`data-contracts` remains planned.
