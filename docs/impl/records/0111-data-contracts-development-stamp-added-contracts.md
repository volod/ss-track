# Task Record

development-stamp-added-contracts

## Task and scope

- Id / capability: `development-stamp-added-contracts` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `f722275`, no unrelated dirty files.
- Plan counts at start: 127 agent, 31 human; next agent `development-stamp-added-contracts`
  (optional), next human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-stamp-added-contracts (optional)

A data root stamped before a record or shared contract was added refuses every root-taking command,
because a contract named on only one side counts as changed. No record of an added contract can be
in the root yet, so the refusal is a false positive, and each task that adds a record contract, such
as `run-bundle-store`, forces the whole development root to be deleted and regenerated, including
an authorized re-acquisition of its sources.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A command on a root whose stamp lacks only contracts added since it was
  written runs, and the root's next sealed write adds their pins to the stamp. A changed or removed
  contract still refuses with `changed_contracts`.
- Scope boundary: The data-root stamp's comparison and its extension under the first-write lock. The
  handoff pins stay an exact match. Fail-closed handling stays: an extended stamp never lets a
  command read a record written under another pin of the added contract.
- Data and artifact paths: `src/ss_track/core/evidence/`, `tests/corpus/records/`.
- Execution path: In `contract_stamp._verify_stamp`, count a name only the install pins as added
  rather than changed, and extend the stamp atomically under `directory_lock` before a sealed write
  in such a root. A stamp can then change while a command runs, which the read fast path assumes it
  cannot: `check_before_read` trusts a stamped root whose stamp file exists. Recheck a root whose
  stamp was incomplete when checked, or whose stamp file changed identity, before each read, and
  refuse a loaded record whose kind's contract the verified stamp did not pin.
- Acceptance gates: A root stamped without a contract the install adds passes a read-only command
  without a write, and its first sealed write adds exactly the added pins; an install with another
  pin for that contract then refuses; a command that checked the root before another install
  extended it refuses that install's record of the added contract; two commands extending one root
  concurrently leave one consistent stamp; a removed or changed contract still refuses. `make ci`
  passes.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: none.

## Implementation

`core/evidence/contract_stamp.py` `verify_stamp` (public now, since the read side calls it) compares
a stamp with meanings by the contracts the stamp names: one pinned otherwise, or one the install
lacks, is a conflict and refuses as before. A contract only the install pins is returned as missing
instead: it was added after the stamp was written, and no record of it can be in the root, because
every writer extends the stamp before it writes. `_require` remembers that set on the checked root
(`checked_roots.CheckedRoot.missing`). `stamp_before_write` rechecks under the lock and, when the
stamp is absent or lacks contracts, writes the installed set, which is then the union. A legacy
structure-only stamp still refuses, and the handoff pins stay an exact match through
`changed_contracts`.

The read side moved to `core/evidence/stamp_reads.py`. Extension only adds names, and a writer
verifies every existing pin under the lock, so a stamp's existing pins never change while a command
runs. A read of a contract the stamp pinned when checked therefore needs no recheck, and a root whose
stamp matched the install completely needs none at all: a later extension adds only contracts this
install has no reader for. `check_before_read(path, kind)` now takes the record format's kind and
returns a `ReadGuard` only for an unstamped root or for a kind whose contract the stamp lacked.
`require_proven` then runs on the loaded record. An unstamped root refuses a record-shaped object,
as before. A missing contract verifies the stamp again: another pin refuses with
`changed_contracts`, a stamp that now pins it as this install does serves it, and a contract still
unpinned refuses with the record and `contract`, which catches a hand-copied record of a new kind.

Deviation from the execution path, with its reason: the plan asked to recheck an incomplete root,
or one whose stamp file changed identity, before each read. The analysis above shows that only a
read of a missing contract can be affected, so the recheck runs there, after loading, which also
closes the gap between a check and the bytes read. Reads of pinned contracts do not reread the stamp
(tested). Rejected: tracking the stamp file's identity, which adds a stat to every read and guards no
case the narrower recheck misses.

Compatibility: no CLI flag, contract, record byte, seal or dependency changed. The new refusal for an
unpinned contract uses the existing `RECORD_SCHEMA_UNSUPPORTED` code. `$DATA_DIR` still refuses,
because its three contracts were edited, not added. Spec section 17.7, the
[Contracts](../current/contracts.md#development-stage) page, the Corpus refusal table, the authoring
guide and `AGENTS.md` state the rule.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Regression fails before the change | `.venv/bin/pytest -q tests/corpus/records/test_stamp_added_contracts.py` at the starting code | fail as expected: 9 of 11; the two changed-or-removed cases already passed, as guards. The concurrency cases then used `fork` without a barrier |
| A read-only command on a root stamped without an added contract writes nothing | `test_a_read_only_command_serves_the_root_and_writes_nothing` (`corpus inspect-source`) | pass: `SOURCE_NOT_IMPORTED`, stamp bytes unchanged |
| The first sealed write adds exactly the added pins | `test_the_first_sealed_write_adds_exactly_the_added_pins` (`import`, two contracts added) | pass: the stamp equals the installed pins |
| Another pin for that contract then refuses | `test_another_pin_for_an_adopted_contract_then_refuses` | pass: `changed_contracts` names it |
| A command that checked first refuses another install's record of the added contract | `test_a_record_another_install_pinned_otherwise_is_refused_after_the_check`; the same pin is served (`..._pinned_alike_is_served`); a never-pinned record refuses (`..._never_pinned_is_refused`) | pass |
| Concurrent extensions leave one consistent stamp | `test_concurrent_extensions_leave_one_consistent_stamp`, two `spawn` processes past a barrier, alike and other pins | pass; with the locked recheck replaced by the unlocked result, the `other` case fails, then the code was restored |
| A changed or removed contract still refuses | `test_a_changed_or_removed_contract_still_refuses` | pass |
| Reads of pinned contracts cost no stamp read | `test_a_read_of_a_pinned_contract_does_not_reread_the_stamp` | pass: no `read_stamp` call over three reads |
| Existing stamp, unstamped, handoff and freeze behavior | `tests/corpus/records`, `tests/corpus/links`, `tests/corpus/hosts`, `tests/commands`, `tests/core`; `pytest -m external` over the same with `tests/schema/registry` | pass: 669, and 80 external |
| Required CI | `make ci` | pass: 2813 passed, 147 deselected |

## Audit handoff

Reviewed: the stamp comparison for added, changed, removed and legacy pins, the locked extension,
the read guard on every sealed-read entry, nested roots, released behavior, the handoff's exact
pins and the data root.

Dropped observations, each with its reason:

- An install that lacks a contract a newer install added to the stamp refuses the root, for example
  an older checkout after a newer one wrote. That was already so before this change, the task states
  it, and development moves forward; no work.
- A stamp replaced by a regenerated root while a command runs is not detected unless it disappears,
  as before this change; regenerating a root under a running command is outside any writer's
  contract.

No bug or improvement is left open. `run-bundle-store` now states that its new stamp names are
added contracts, with the name rules to widen, and the group audit names this mechanism.

## Close or resume

Every gate passed. The task has left the plan; spec section 17.7, the Contracts and Corpus pages,
the authoring guide, `AGENTS.md` and the records index are updated. Plan counts after: 126 agent and
31 human tasks; next agent `data-contracts-audit` (optional), next human `define-locked-test-policy`
(optional). `data-contracts` remains planned.
