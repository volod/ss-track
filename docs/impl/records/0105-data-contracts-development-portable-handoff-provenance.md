# Task Record

development-portable-handoff-provenance

## Task and scope

- Id / capability: `development-portable-handoff-provenance` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `2db0c29`, no unrelated dirty files.
- Plan counts at start: 129 agent, 30 human; next agent `development-portable-handoff-provenance`,
  next human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-portable-handoff-provenance

A development review archive does not bind the source root's contract stamp. Two roots can use the
same `1.0.0` record bytes while a record or shared contract has a different meaning; the receiving
root accepts the archive after comparing only data hashes. This can silently reinterpret a remote
review under another contract set.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Development handoffs prove the source and receiving contract sets agree
  before any review state or local evidence is changed; missing or different pins refuse safely.
- Scope boundary: Portable review contract provenance and its checks. Preserve released-stage
  compatibility, existing sealed record semantics and operator-written inputs.
- Data and artifact paths: `contracts/record/link-review-handoff/1.0.0.json`,
  `contracts/registry.yaml`, `src/ss_track/corpus/links/`, `tests/corpus/links/`, `$DATA_DIR/`.
- Execution path: Bind the exporting root's record and shared structure and meaning fingerprints
  in the handoff contract and verify them before acceptance. Edit and re-pin `1.0.0` in place,
  update the writer and reader, and regenerate affected development datasets and handoffs from
  retained declarations and decisions, following the contract authoring rules.
- Acceptance gates: Two private roots with identical source and frame bytes and different record
  meaning pins refuse a handoff before writing local records or checkpoints; missing provenance
  refuses, matching pins round-trip, and released handoffs retain their versioned behavior. All
  operator-written inputs remain; `make ci` passes.
- Documentation target: [Contracts](current/contracts.md) and
  [Leakage review](current/corpus/leakage-review.md).
```

- Amendments: none.

## Implementation

`record/link-review-handoff` 1.0.0 was edited in place and re-pinned with `ss-track contracts
freeze`: a required `contract_set`, a nullable array of `{contract, structure, meaning}` rows in
contract order, and the `x-rules` entry `provenance`. The dialect forbids open maps, so the pins are
rows rather than the stamp's two objects.

- `core/evidence/contract_stamp.py`: the stamp comparison moved into `_changed`, and the new
  `changed_contracts(structures, meanings)` applies it to pins that travel with evidence. The stamp
  check keeps its structure-only legacy path unchanged.
- `corpus/links/portable_provenance.py` (new): `exported_contract_set` returns the installed
  record and shared pins, or `None` in the released stage; `require_matching_contract_set`
  refuses absent or null pins and any changed contract with `RECORD_SCHEMA_UNSUPPORTED`,
  `changed_contracts` and a handoff remedy, and unsorted, repeated or incomplete rows with
  `RECORD_TAMPERED`. A seal proves only self-consistency, so rows are parsed defensively.
- `portable_archive.build_archive` writes the pins; `read_archive`, shared by `review-unpack` and
  `review-accept`, checks them after the file table and before expiry. `accept_handoff` reads the
  archive before `record_staged_hashes`, so a refusal writes no staged hashes, comparison, link
  record, checkpoint or accepted handoff; `unpack_handoff` creates no recipe directory.
- `export_handoff` now checks its root first, so the pins are those the root was written under even
  when called without the CLI wrapper.
- Tests: `tests/corpus/links/test_portable_provenance.py` (new); shared preparation moved from
  `test_portable.py` to `tests/corpus/links/_portable.py`; the schema example carries pins.

Decisions: every record and shared contract is pinned, not only the three a handoff carries,
matching the data-root stamp and spec section 17.7; compared with the install, not the receiving
root's stamp, because `review-accept` has already required the root to match the install and
`review-unpack` takes no root. Unpack refuses too, so a host does not acquire and stage a corpus for
an archive that acceptance would refuse; the spec now says so. Rejected: a digest of the whole set,
which could not name the changed contracts.

Compatibility: an archive exported before this change has no `contract_set` and is refused with the
handoff remedy. No CLI flag, environment variable or dependency changed. Released behavior: the
writer sets `null` and the reader skips the check, reading by major.

Data root: `$DATA_DIR` holds no handoff archive and no `accepted-handoff.json`, so no handoff needs
regeneration. Its `contract-set.json` is a structure-only stamp from before meaning fingerprints were
required, so the root already refused every root-checking command; see the audit handoff.

Current state: [Contracts](../current/contracts.md) and
[Leakage review](../current/corpus/leakage-review.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Equal source and frame bytes, other record meaning pins, refuse before local writes | `test_roots_with_equal_bytes_but_other_pins_refuse_before_any_local_write` (`record/corpus-links` meaning, `shared/types` structure) | pass: `RECORD_SCHEMA_UNSUPPORTED` naming the one contract; no link run, staged-hashes or comparison directory, and no recipe directory on unpack. The receiver's differing pins are simulated by patching the installed fingerprints |
| Missing provenance refuses | `test_missing_pins_refuse_with_the_handoff_remedy` (absent and null, resealed) | pass |
| Damaged or changed pins refuse | `test_changed_or_damaged_pins_refuse`, seven cases | pass: changed and omitted rows `RECORD_SCHEMA_UNSUPPORTED`; unsorted, repeated, incomplete and non-row `RECORD_TAMPERED` |
| Matching pins round-trip | `test_matching_pins_round_trip_into_the_accepted_handoff`, `test_a_handoff_pins_every_installed_record_and_shared_contract`, both `test_portable.py` round trips | pass |
| Released handoffs keep versioned behavior | `test_a_released_handoff_carries_no_pins_and_reads_by_major` | pass: null pins, acceptance succeeds without a stamp; the same archive refuses under development |
| Contract edited in place and re-pinned | `ss-track contracts freeze record/link-review-handoff --summary "Initial contract."`; schema example `tests/schema/examples/record-link-review-handoff.json` | pass |
| Operator-written inputs remain | `git status`; no file under `$DATA_DIR` changed | pass |
| Regenerate affected datasets and handoffs | `$DATA_DIR` searched for `ss-track.link-review-handoff` records and `.tar` archives | pass: none exist, so nothing to regenerate; the root's older structure-only stamp is routed below |
| Required gate | `make ci` | pass: 2687 passed, 155 deselected; `make lint-md` also passes |

## Audit handoff

Reviewed: the contract edit, writer, both readers, the shared comparison, the refusal order in
`accept_handoff` and `unpack_handoff`, released-stage behavior and the data root.

- `AUD-development-portable-handoff-provenance-1` (chore needing authorization): `$DATA_DIR` has a
  structure-only stamp, so `ss-track corpus verify --corpus hawk-drone-pilot-v1` refuses
  `RECORD_SCHEMA_UNSUPPORTED` with `unverified_contracts`, and now also names
  `record/link-review-handoff` in `changed_contracts`. Nonblocking for this task. Rebuilding
  re-acquires the pilot sources under the owner's transfer cap. Owner: `development-data-root-regenerate`
  (Human-Assisted lane, added in this change).
- Observation, dropped: a stamped root refuses when any record or shared contract changed, even one
  with no records in the root, as here. Spec section 17.7 chose a root-level stamp so a stamped root
  never scans; no work is needed.

## Close or resume

Every gate passed. The task has left the plan; the Contracts and Leakage review pages and spec
section 17.7 (unpack refuses too) are updated and link this record. Plan counts after: 128 agent,
31 human; next agent `development-explicit-path-revision-root`, next human
`define-locked-test-policy` (optional). `data-contracts` stays `planned`.
