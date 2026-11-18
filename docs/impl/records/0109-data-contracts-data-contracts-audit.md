# Task Record

data-contracts-audit

## Task and scope

- Id / capability: `data-contracts-audit` / `data-contracts`
- State: active
- Source: plan task; starting commit `4590c9a`, no unrelated dirty files.
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
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits) over the
  remaining work, including unstamped evidence and its seams to the root stamp, read path, history
  gate and section 17.7. Verify that structural, shared and meaning changes refuse stale evidence.
- Acceptance gates: Every section 17.7 rule has a failing fixture or is named as human judgment.
  Every finding is fixed, routed to a task or dropped with its reason, and `make quality` passes.
  Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: this run left the task in the plan, under the group-audit rule that a new task in
  the group keeps the audit open for that work alone. Its execution path now names that work, by this
  audit:

```markdown
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits) over the
  remaining work: `development-staged-hashes-provenance`, `development-stamp-added-contracts` and
  their seams to the root stamp, the read path, the handoff pins and section 17.7. Verify that
  structural, shared and meaning changes still refuse stale evidence.
```

## Implementation

Reviewed spec sections 17.1 to 17.7, the [Contracts](../current/contracts.md) page, the Corpus
refusal table, the authoring guide, `AGENTS.md`, records 0099 to 0108, `src/ss_track/schema/`,
`src/ss_track/core/evidence/`, `commands/report.py`, the event-package development path, the
portable handoff, every CLI command and path argument, the retained operator inputs and their tests.
Every handoff those records raised reached an owner that closed it (`AUD-contract-development-
baseline-1` to `-3`, `AUD-event-package-development-edit-1`, `AUD-development-unstamped-evidence-1`
to `-3`, `AUD-development-portable-handoff-provenance-1`). The real `$DATA_DIR` passes the root
check under the installed set.

- **Integrity.** The Corpus refusal table did not say that `RECORD_SCHEMA_UNSUPPORTED` also covers
  unstamped evidence and handoff pins, that a damaged stamp is `RECORD_TAMPERED`, or that an
  uninspectable file in an unstamped root is `STORAGE_FAILED`; the rows now do. `AGENTS.md` said to
  delete only "the affected" datasets after an edit, but the stamp refuses the whole root, and an
  operator who kept the other datasets would meet either `changed_contracts` or unstamped evidence;
  it now states the whole-root rule the authoring guide states. Three retained workload inputs named
  `declaration/discovery-plan 1.1.0` and `declaration/corpus-pool 1.1.0`, versions the development
  baseline removed; the comments now say `1.0.0`. No sealed record pins those bytes: the pool hashes
  its canonical parsed declaration and a discovery run pins no plan file.
- **Repetition.** The stage of a registry had two readings: `stage_of` mapped any unknown value to
  development and the history walk ignored one, so a committed revision whose stage was neither
  could not be told from development. `stage.stated_stage` is now the one reading and refuses
  another value, so the history gate fails closed (regression first failed). `runtime_findings` and
  `check_contract_set` repeated their set-level checks, now `check._set_findings`;
  `installed_fingerprints` and `installed_meanings` repeated their walk, now `_installed_pins`;
  two tests kept their own unstamped-record helper, now `tests/corpus/records/_unstamped.py`.
- **Explicit patterns.** The directory lock (`os.open` and `flock` on a directory) was written out in
  the stamp, the freeze and the event batch publisher; it is now `core/scratch.py`
  `directory_lock`. The contract set had a second atomic writer, `publishing._write_atomically`,
  without the `fsync` before rename that `core/scratch.py` `write_atomically` does, and the batch
  publisher imported it as a private name. `publishing.write_contract_file` now keeps the file's
  mode and writes through the shared writer, and both publishers use it. No contract byte moves:
  `make proto-check` and `make lint-contracts` pass.
- **Naming.** `write_contract_file` replaces the private cross-module import; `urn_family` is the
  inverse of `contract_urn`, so no caller splits a URN by hand. `STAMPED_FAMILIES` names the families
  the stamp pins, once, for the stamp and the gate.
- **Algorithms.** The history gate took 3.1 seconds over 59 registry revisions on this checkout
  (`time make lint-contracts`), one `git show` per revision; no change. The stamp check of a
  stamped root reads one small file; walk costs are in records 0104 and 0108. The `fsync` change is
  for durability, not speed: five development freezes of `record/frame-set` on a private copy took
  1.600 to 1.679 seconds at the starting commit and 1.618 to 1.739 after, alongside a running test
  suite, so within noise; validating the staged set dominates. The one-off script was not kept.
- **Gaps.** The stamp pins only record and shared contracts, and nothing held a record's shape to
  those families: a record contract could `$ref` a declaration or result definition, which an
  in-place edit would change while every stamp still matched. The gate now refuses that reference
  (`schema/registry/references.py`, split from `check.py` at that seam), and spec section 17.7
  says so; no shipped contract had one. Section 17.7 rules without a failing fixture now have one;
  see the table below. `corpus compare` reads another host's sealed staged-hashes record with no
  contract pins, contrary to the 17.7 handoff rule (reproduced below), and a run bundle will hold
  formats shaped by event packages the stamp does not pin; both are routed.
- **Ideas.** A root stamped before a contract was added refuses although it cannot hold a record of
  that contract, so every task that adds a record contract would force the whole development root
  to be regenerated, with an authorized re-acquisition. Routed as an optional improvement. A
  whole-root validation command was considered and dropped: every record is validated before it is
  sealed, the stamp proves the set it was sealed under, and `corpus verify` and `discover verify`
  recheck the evidence.

Specification: section 17.7 now states the reference rule, that a format shaped by another family
joins the stamp before it is written to a root, that another host's staged hashes are a handoff,
and that the gate refuses a registry revision whose stage it cannot read; section 17.4 says that a
development `RunManifest` names fingerprints. No sealed record, seal, contract file, pin, refusal
code, CLI flag or dependency changed. Current pages: [Contracts](../current/contracts.md) and
[Corpus](../current/corpus.md), with the authoring guide and `AGENTS.md`.

### Section 17.7 rules and their fixtures

| Rule | Failing fixture, or human judgment |
| --- | --- |
| One stage for the whole set, and the gate enforces it | `meta/registry.json` requires `stage`; `test_stage.py` `test_the_shipped_set_is_in_the_development_stage`, `test_reading_an_unknown_stage_is_refused` (new) |
| Development: one `1.0.0` per contract, every record at `schema_version: 1` | `test_a_second_version_is_refused_in_development`, `test_freeze_refuses_any_other_version_in_development`; the gate's stamp check and `test_agreement.py` hold each writer to its contract's major |
| An edit in place re-pins hash and fingerprints, with writers, fixtures and tests | `test_an_edit_in_place_passes_only_with_its_re_pin`, `test_freeze_re_pins_the_one_version_in_place`; examples and `test_agreement.py` catch a writer left behind. Whether every writer changed is review judgment |
| A planning-mistake fix is an edit, never a version | A second version is refused (above); calling a change a mistake fix is human judgment |
| No view, disposition, retired major or historic fixture keeps old data readable | `test_a_retired_major_is_refused_in_development` (new), `test_installed_reader_refuses_a_broken_stage_rule` (new), `test_the_development_install_keeps_no_older_format_readable` (new); a historic fixture file is review judgment |
| Released: frozen versions, 17.3 classification, a major's disposition | `tests/schema/compatibility/` on private sets moved to `released` |
| Released: older data read under its disposition, a real record per major | `contract-release-freeze` (human-gated); synthetic majors in `test_read_window.py` |
| The stamp pins record and shared structure and meaning before the first sealed write | `test_first_write_stamps_every_record_contract_and_a_read_preserves_it`, `test_stamp_precedes_sealed_write`; `test_a_record_may_reference_only_what_the_data_root_stamp_pins` (new) |
| Unstamped sealed evidence is refused; checked before a read and under the lock | `test_unstamped_evidence.py`, `test_unstamped_scan_reuse.py` |
| A fresh or operator-only root stays usable with no read-side write | `test_fresh_and_operator_inputs_do_not_create_a_stamp`, `test_read_only_command_on_fresh_root_writes_no_stamp` |
| Every root-taking command, and an explicit sealed output inside the root, checks first | `tests/commands/test_root_checks.py` (new, every command but named exemptions, on unstamped and stale roots), `test_explicit_path_root.py` |
| A difference names the changed contracts with the regenerate remedy | `test_a_root_written_before_an_edit_is_refused_with_the_regenerate_remedy`, the sweep above |
| Structural, meaning-only and shared edits refuse stale evidence | `test_stamp_after_freeze.py` (new): real `contracts freeze` of each, `changed_contracts` names exactly that contract |
| Housekeeping still runs | `test_data_clean_serves_a_stale_root`, `test_clean_can_inspect_unstamped_evidence` |
| A stamp without meanings is refused | `test_legacy_structure_only_stamp_refuses_without_deleting_data` |
| A description edit asks for regeneration | `test_stamp_after_freeze.py` meaning case; whether prose changes a meaning is human judgment by design |
| Another major gets the same remedy | `test_sealed.py` `test_a_refusal_states_the_record_its_major_its_age_and_the_remedy` |
| A development handoff binds the contract set and refuses before writing | `test_portable_provenance.py` for the review archive. Staged hashes: fails, routed as `AUD-data-contracts-audit-1` |
| Released handoffs follow versions | `test_a_released_handoff_carries_no_pins_and_reads_by_major` |
| Classifier, oracle, dispositions and views stay installed, tested on synthetic pairs | `tests/schema/compatibility/`, `tests/corpus/records/test_read_window.py` |
| A shape change edits every retained operator input | `test_retained_inputs.py` (new) for the inputs the repository keeps; inputs kept only under `$DATA_DIR` are the operator's |
| Release is one owner decision and the gate refuses a return | The four history tests in `test_stage.py`, and `test_history_fails_closed_on_a_stage_it_cannot_read` (new); the decision is human |
| A fix found while preparing release is a development edit | Human judgment, in `contract-release-freeze` |
| Evaluation: the regenerated root validates under the current set | [Regeneration record](0106-data-contracts-development-data-root-regenerate.md); the root check on `$DATA_DIR` passes in this audit |

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Every 17.7 rule has a failing fixture or is named as human judgment | The table above | pass; the staged-hashes handoff rule fails and is routed |
| Regressions fail before their fix | `test_stage.py` unknown-stage cases and `test_check_schemas.py` reference cases, run with `src/` stashed | fail as expected before, pass after; the retired-major and no-older-format fixtures pass on the old code, being missing fixtures rather than bugs |
| The sweep detects a missing root check | `tests/commands/test_root_checks.py` with `reported_on_data_root` changed to skip its check, then restored | fails as expected; 51 cases pass on the real code |
| Staged-hashes reproduction | One-off script, not kept: a copy of `$DATA_DIR/run/pilot-hashes-origin-grouped/staged-hashes.json` as both sides, `corpus compare` on a fresh scratch root under an install whose `record/staged-hashes` meaning pin differed | comparison sealed `identical`, exit 0; scratch removed, `$DATA_DIR` only read |
| Full quality gate | `make quality` | see Close or resume |

## Audit handoff

- `AUD-data-contracts-audit-1` (bug, nonblocking): `corpus compare` reads another host's sealed
  staged-hashes record that binds no contract set, so a comparison can be sealed between hosts that
  read the records differently; reproduced above. The fix edits `record/staged-hashes` in place,
  which stales `$DATA_DIR`. Owner: `development-staged-hashes-provenance`, added in this change.
- `AUD-data-contracts-audit-2` (improvement, nonblocking): a root stamped before a contract was added
  refuses although it cannot hold that contract's records, forcing a full regeneration whenever a
  record contract is added. Owner: `development-stamp-added-contracts` (optional), added in this
  change, which states the stamp-mutability risk to the read fast path.
- `AUD-data-contracts-audit-3` (gap, nonblocking until run bundles exist): a run bundle's manifest
  takes its shape from `event/analytics` and its event lines from event packages, which a
  development edit changes in place while the stamp, which pins record and shared contracts only,
  still matches; and a development "contract set in force" listed by version cannot tell edits
  apart. Owner: `run-bundle-store`, whose execution path and gates now state both.

Dropped, each with its reason: a whole-root validation command (see Ideas); the 3.1-second history
gate (no measured problem). Everything else found was fixed in this change.

## Close or resume

In progress.
