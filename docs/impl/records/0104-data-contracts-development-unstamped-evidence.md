# Task Record

development-unstamped-evidence

## Task and scope

- Id / capability: `development-unstamped-evidence` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `0364976`, no unrelated dirty files.
- Plan counts at start: 127 agent, 30 human; next agent `development-unstamped-evidence`, next
  human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-unstamped-evidence

A development root without `contract-set.json` is treated as fresh even when it contains sealed
records. If a stamp is lost, or a first write made by older code was interrupted before stamping,
a command can read those records or stamp the root under a later contract set, silently accepting
unproven evidence. The shared sealed-read path and first-write ordering do not establish whether an
unstamped root already contains records.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A root with unstamped sealed evidence refuses with a regenerate remedy;
  genuinely new roots and roots holding only operator inputs remain usable without a read-side write.
- Scope boundary: Development data-root provenance checks; do not delete evidence or operator inputs,
  alter released reads, seals or frozen contract bytes.
- Data and artifact paths: `src/ss_track/core/evidence/`, data-root layout owners under
  `src/ss_track/`, `tests/corpus/records/`, private fixture data roots.
- Execution path: Identify all sealed-record locations and direct write entry points; implement a
  fail-closed check before an unstamped root can read evidence or receive its first stamp, with a
  bounded-cost path for large roots. Preserve declarations and clean-only access.
- Acceptance gates: Fixtures with an unstamped sealed record refuse both a read and a first write,
  even when a command writes before reading it; an empty root and one containing only declarations
  remain usable and read-only commands create no stamp. Released behavior stays unchanged; test a
  large representative root and report cost. `make ci` passes.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: none.

## Implementation

`core/evidence/unstamped.py` scans an unstamped root for top-level JSON record identity and seal
keys without relying on a filename or loading records into memory. It streams JSON through fixed
buffers, sorts traversal, follows links with directory-cycle detection, and fails closed on
unreadable or non-regular files. Record-shaped objects are refused conservatively; the shipped
closed declaration contracts do not permit both keys. The check changes no input or evidence.

`contract_stamp.py` scans before a root is used and again under the first-write lock. The shared
sealed-read path rechecks if a stamp was initially absent or later disappears, closing the window
between a root check and a record read. Root-taking corpus APIs, evidence readers and other direct
record publishers check the root as well as CLI handlers. Source acquisition had a separate
`write_once` path for its sealed record: it now checks the root and stamps before that write,
without changing record bytes. The private pool fixture now creates stamped source records, as the
production flow does.

Read-only checks write no stamp; clean-only access and released-stage reads remain unchanged. No
contract file, sealed record, seal, dependency or operator input changed. The
[Contracts page](../current/contracts.md#development-stage) describes the scope and scan cost.

The completion audit found two defects, both fixed here. First, the scan raised
`FileNotFoundError` when an entry vanished between listing and inspection, so a concurrent
command's scratch churn, such as a first acquisition downloading before it stamps, could fail
another command with `STORAGE_FAILED`. A one-off script that churned temporary files during five
scans of 20,000 files failed one of them. Vanished entries and dangling links are now skipped,
because no read can load them; permission errors and non-regular files still fail closed. Second,
the checked-root context held one root and every check replaced it, so a nested check of another
root would silently stop stamping and read rechecks of the first. The context now keeps every root
the command checked, and a write or read uses the most specific root that holds its path.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Unstamped read, first write, late record and removed stamp | `.venv/bin/pytest -q tests/corpus/records/test_unstamped_evidence.py` | pass; private roots, arbitrary names, escaped keys, symlinks and public root-taking APIs |
| Fresh inputs, clean-only and released behavior | Same test file and `tests/corpus/records/test_contract_stamp.py` | pass; declarations, nested keys, empty roots, `data clean`, released records and no read-side stamp |
| Existing acquisition, pool and contract flows | `.venv/bin/pytest -q tests/corpus/sources/test_acquisition.py tests/corpus/sources/test_pool.py tests/corpus/records/test_contract_stamp.py` | pass; direct and CLI acquisition write a stamp, pool replay remains unchanged |
| Large representative root | One-off Python script, not kept; temporary root with 25,000 PNG files, 102.4 MB, 50 directories and one declaration; three `require_current_data_root` calls with `tracemalloc` | pass: 0.983, 0.688 and 0.685 s; 4.99, 0.06 and 0.06 MiB peak traced memory. First includes installed-contract initialization; no stamp was created |
| Vanished entries and nested root checks | `.venv/bin/pytest -q tests/corpus/records/test_unstamped_evidence.py -k "vanished or removed_during or another_root"` | pass; ghost file and directory, dangling link, record after a dangling link still refused, nested check keeps the first root stamped and rechecked |
| Required CI | `make ci` | pass: 2673 passed, 155 deselected |
| Plan, links and Markdown | `make lint-md lint-spec-plan` | pass |

## Audit handoff

Reviewed source, sequence, corpus, bundle, frame-set, hash, discovery, pool, link, annotation,
review, blinding and portable-handoff publishers. Their record writes use `write_sealed`; the one
source acquisition `write_once` path is now stamped. Root-taking public operations, evidence
readers and the other root-taking record publishers establish the checked context before reading or
publishing.

A path-only standalone record reader has no data-root argument from which to infer a root. Its
caller must establish the root context when treating that path as data-root evidence. This is the
existing standalone interface boundary, not an unowned data-root operation; it needs no follow-up.
`AUD-development-unstamped-evidence-1` (nonblocking): The portable review archive binds source,
frame and record hashes but does not carry the source root's contract fingerprints. A private
round trip with a changed `record/corpus-links` meaning pin returned `identical`; a one-off script
used fixture media and was not kept. Same-version remote records can therefore be interpreted under
a different development meaning. Owner: `development-portable-handoff-provenance`. The temporary
archive validator now checks its standalone link file without pretending it is a stamped data root;
the existing portable integration tests still pass.

The check is deliberately conservative: a top-level object with both record keys is treated as
unverified even if its seal is invalid. This avoids trusting damaged evidence; closed operator
declaration contracts cannot have that shape. The completion audit also found:

- Vanished-entry `STORAGE_FAILED` and the single checked-root context: fixed in this change; see
  Implementation.
- `AUD-development-unstamped-evidence-2` (bug): `annotate freeze` with an explicit
  `--revision-out` inside `DATA_DIR` publishes a sealed revision without a root check or stamp, so
  the next command on a fresh root refuses it. Owner: `development-explicit-path-revision-root`.
- `AUD-development-unstamped-evidence-3` (improvement): one command can scan an unstamped root once
  per check, several times in all; the measured cost is per scan. Owner:
  `development-unstamped-scan-reuse` (optional).

## Close or resume

Every gate passed, including `make ci`. The completed task has left the plan and the Contracts
page and records index are updated. The group audit remains open to review this change. Plan counts
after: 129 agent and 30 human tasks; `data-contracts` remains planned.
