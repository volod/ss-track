# Task Record

data-contracts-audit

## Task and scope

- Id / capability: `data-contracts-audit` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `c81ee0f`, no unrelated dirty files. Records 0102 and 0109
  hold the earlier runs of this audit; this run covers the work they left in the plan.
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
  remaining work: the carried contract pins that the review handoff and staged hashes share
  (`core/evidence/carried_pins.py`), the stamp's adoption of added contracts and its read recheck
  (`core/evidence/stamp_reads.py`), and their seams to the root stamp, the read path and section
  17.7. Verify that structural, shared and meaning changes still refuse stale evidence.
- Acceptance gates: Every section 17.7 rule has a failing fixture or is named as human judgment.
  Every finding is fixed, routed to a task or dropped with its reason, and `make quality` passes.
  Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: none.

## Implementation

Reviewed spec section 17.7, the [Contracts](../current/contracts.md) page, the Corpus sections
"Across hosts" and "Refusal codes", [Leakage review](../current/corpus/leakage-review.md), the
authoring guide, `AGENTS.md`, records 0109 to 0112, `core/evidence/` (`carried_pins.py`,
`contract_stamp.py`, `stamp_file.py`, `stamp_reads.py`, `checked_roots.py`, `sealed.py`,
`sealing.py`), the staged-hashes writer and comparison in `corpus/hosts/`, the handoff export,
archive and acceptance in `corpus/links/`, the acquisition's stamping, the tests those records
added, and every plan task that names a record contract or a contract version.

- **Integrity.** The Contracts page said `core/evidence/sealed.py` refuses an unstamped record on
  read; since record 0111 that is `core/evidence/stamp_reads.py`, and the page now says so. The
  Leakage review page said acceptance refuses before any record is written, which did not hold for
  the archive's staged-hashes pins (the acceptance gap below); the code now makes it true. Three
  texts outside this group still used released-stage vocabulary for development-time changes:
  `corpus-scale-pilot` asked for a `record/discovery-run` "minor", `telemetry-corpus-streams` for "a
  minor contract version", and the discovery-runs page called a mixed-precision mode "a contract
  minor". Section 17.7 allows no second version before release. `corpus-scale-pilot` is required,
  so it runs before release; its text now says to edit `1.0.0` in place, re-pin it, and regenerate
  the discovery runs in `$DATA_DIR` or add the Human-Assisted regeneration task.
  `telemetry-corpus-streams` is optional and may run after release, so its text now names the rule
  for each stage. Every handoff of records 0109 to 0112 reached an owner:
  `AUD-data-contracts-audit-1` and `-2` closed in records 0110 and 0111,
  `AUD-development-staged-hashes-provenance-1` closed in record 0112, and
  `AUD-data-contracts-audit-3` is still stated by `run-bundle-store`. The observations those
  records dropped still hold. The refusals in this run fit the existing `RECORD_SCHEMA_UNSUPPORTED`
  row of the Corpus refusal table, which already names an unpinned contract and handoff or
  staged-hashes pins.
- **Repetition.** Three places named the families the stamp pins: `STAMPED_FAMILIES`, a literal
  `("record/", "shared/")` in `stamp_file._fingerprint_map`, and the `contract` pattern of
  `shared/types` `$defs/contract-set`. The stamp parser now reads the constant. The contract cannot
  import it, so `test_the_stamp_and_carried_pins_admit_exactly_the_stamped_families` holds the
  pattern to it, family by family. That test passes on the old code too: it is a guard, and no
  behavior changed. The `run-bundle-store` text that asked for three separate widenings now names
  the constant, what reads it, and the test. The post-load stamp check in `require_proven` now
  serves both kinds of guard (below), so one path handles it. During acceptance the archive's
  staged hashes are checked twice: early with the handoff remedy, then inside
  `compare_staged_hashes`, which `corpus compare` also runs alone. Both go through
  `require_carried_contract_set`, so the rule is stated once, and the second check cannot fail
  after the first passes. No change.
- **Explicit patterns.** The stamp is written only by `stamp_before_write`, under `directory_lock`
  and through `write_atomically`. Every sealed read goes through `_read_intact`, then
  `check_before_read` and `require_proven`. Carried pins are written by one function
  (`carried_contract_set`) for both writers and checked by one (`require_carried_contract_set`) for
  both readers. The acquisition stamps through `stamp_before_write` before `write_once`. No
  change.
- **Naming.** `ReadGuard.contract` set to None meant "the root had no stamp". That reading
  conflated it with "a kind the stamp does not cover", and the conflation is what hid the race
  below. `ReadGuard` now has an explicit `unstamped` field. `require_matching_contract_set` takes
  the archive member it checks.
- **Algorithms.** Measured read-only on `$DATA_DIR` with two one-off scripts, not kept:
  `check_before_read` costs about 36 us per stamped read. About 31 us of that is
  `checked_roots.holding`, mostly the two path resolutions in `holds_path`. A 14,448-byte frame-set
  read costs about 99 us in total. `corpus verify` of `pilot-two-source-grouped-20261113` made 76
  guarded reads, which took 4.1 ms of its 53.9 s; `hawk-drone-pilot-v1` made 6, taking 0.4 ms of
  1.5 s. No change, because no command would gain measurably. The race fix adds one stamp read only
  where the root had no stamp when checked, where every record-shaped read was already refused.
  Reads of pinned contracts in a stamped root are unchanged
  (`test_a_read_of_a_pinned_contract_does_not_reread_the_stamp`).
- **Gaps.** Two were reproduced and fixed. First, a read race: a root has no stamp when a read is
  checked, and another command's first write stamps it and writes a record before the load. The
  record was refused with "has no development contract stamp" although the root then had one, and
  when that stamp held another pin the refusal did not say `changed_contracts`.
  `require_proven` now judges an unstamped guard's record-shaped object by the stamp the root holds
  after loading, as it already did for a contract the stamp lacked (`test_stamp_read_recheck.py`).
  Second, acceptance wrote early: it wrote `run/<identity-run>/staged-hashes.json` before it checked
  the archive's staged-hashes pins. An archive whose manifest pins match but whose resealed
  staged-hashes member carries other pins was refused only in the comparison, after that local
  write. This is contrary to section 17.7 ("before writing anything") and to the Leakage review
  page. `portable_accept._verify_archive_records` now checks the member with the handoff remedy
  (`test_a_staged_hashes_member_under_other_pins_refuses_before_any_local_write`).
  `review-unpack` reads no carried record and writes only recipes, so the manifest's binding
  covers it, unchanged. Meaning-only conflicts of an adopted contract go through the same
  `_conflicts` as structure, and `test_stamp_after_freeze.py` covers them for stamped contracts.
- **Ideas.** Records 0106 and 0112 each rebuilt `$DATA_DIR` with an untracked one-off script that
  followed steps spread over the Corpus page and the two-source recipe, and each compared seals
  with a one-off snapshot. A tracked regeneration target was considered. A read-only
  data-root status command was considered too. Both are dropped; the reasons are in the handoff.

Specification: no change. Section 17.7 already requires a handoff to refuse before writing
anything, and requires that a record of a contract the stamp lacked be served only once the stamp
pins it as the reading install does. The race fix applies that same rule to a root that had no
stamp. No contract file, pin, sealed byte, seal, refusal code, CLI flag or dependency changed. The
new refusals use `RECORD_SCHEMA_UNSUPPORTED`, as the same conditions already did elsewhere. Current
pages: [Contracts](../current/contracts.md#development-stage),
[Leakage review](../current/corpus/leakage-review.md) and
[Discovery runs](../current/corpus/discovery-runs.md).

### Section 17.7 rules and their fixtures

Carried forward from record 0109, with the rows records 0110 and 0111 and this run changed.

| Rule | Failing fixture, or human judgment |
| --- | --- |
| One stage for the whole set, and the gate enforces it | `test_stage.py` `test_the_shipped_set_is_in_the_development_stage`, `test_reading_an_unknown_stage_is_refused` |
| Development: one `1.0.0` per contract, every record at `schema_version: 1` | `test_a_second_version_is_refused_in_development`, `test_freeze_refuses_any_other_version_in_development`; `test_agreement.py` holds each writer to its contract's major |
| An edit in place re-pins hash and fingerprints, with writers, fixtures and tests | `test_an_edit_in_place_passes_only_with_its_re_pin`, `test_freeze_re_pins_the_one_version_in_place`; whether every writer changed is review judgment |
| A planning-mistake fix is an edit, never a version | A second version is refused (above); calling a change a mistake fix is human judgment. Plan texts that asked for a development minor are amended in this run |
| No view, disposition, retired major or historic fixture keeps old data readable | `test_a_retired_major_is_refused_in_development`, `test_installed_reader_refuses_a_broken_stage_rule`, `test_the_development_install_keeps_no_older_format_readable`; a historic fixture file is review judgment |
| Released: frozen versions, 17.3 classification, a major's disposition | `tests/schema/compatibility/` on private sets moved to `released` |
| Released: older data read under its disposition, a real record per major | `contract-release-freeze` (human-gated); synthetic majors in `test_read_window.py` |
| The stamp pins record and shared structure and meaning before the first sealed write | `test_first_write_stamps_every_record_contract_and_a_read_preserves_it`, `test_stamp_precedes_sealed_write`, `test_a_record_may_reference_only_what_the_data_root_stamp_pins`; `test_the_stamp_and_carried_pins_admit_exactly_the_stamped_families` (new) |
| Unstamped sealed evidence is refused; checked before a read and under the lock | `test_unstamped_evidence.py`, `test_unstamped_scan_reuse.py`; between the read check and the load, `test_stamp_read_recheck.py` (new) |
| A fresh or operator-only root stays usable with no read-side write | `test_fresh_and_operator_inputs_do_not_create_a_stamp`, `test_read_only_command_on_fresh_root_writes_no_stamp` |
| Every root-taking command, and an explicit sealed output inside the root, checks first | `tests/commands/test_root_checks.py`, `test_explicit_path_root.py` |
| A difference names the changed contracts with the regenerate remedy | `test_a_root_written_before_an_edit_is_refused_with_the_regenerate_remedy`, the sweep above |
| An added contract is no difference; the next sealed write adds its pins; a read of it is served only once pinned alike | `test_stamp_added_contracts.py`: read-only serve, exact adoption, another pin then refuses, a record pinned otherwise after the check refuses, pinned alike serves, never pinned refuses, concurrent extensions |
| A contract the stamp names that the install lacks is a difference | `test_a_changed_or_removed_contract_still_refuses` |
| Structural, meaning-only and shared edits refuse stale evidence | `test_stamp_after_freeze.py`: real `contracts freeze` of each |
| Housekeeping still runs | `test_data_clean_serves_a_stale_root`, `test_clean_can_inspect_unstamped_evidence` |
| A stamp without meanings is refused | `test_legacy_structure_only_stamp_refuses_without_deleting_data` |
| A description edit asks for regeneration | `test_stamp_after_freeze.py` meaning case; whether prose changes a meaning is human judgment by design |
| Another major gets the same remedy | `test_sealed.py` `test_a_refusal_states_the_record_its_major_its_age_and_the_remedy` |
| A development handoff binds the contract set and refuses before writing | Review archive: `test_portable_provenance.py`, with `test_a_staged_hashes_member_under_other_pins_refuses_before_any_local_write` (new). Staged hashes: `test_staged_hashes_provenance.py` `test_a_host_under_another_contract_set_refuses_before_any_write` |
| Released handoffs follow versions | `test_a_released_handoff_carries_no_pins_and_reads_by_major`, `test_released_records_carry_no_pins_and_compare_by_major` |
| Classifier, oracle, dispositions and views stay installed, tested on synthetic pairs | `tests/schema/compatibility/`, `tests/corpus/records/test_read_window.py` |
| A shape change edits every retained operator input | `test_retained_inputs.py`; inputs kept only under `$DATA_DIR` are the operator's |
| Release is one owner decision and the gate refuses a return | The history tests in `test_stage.py`, `test_history_fails_closed_on_a_stage_it_cannot_read`; the decision is human |
| A fix found while preparing release is a development edit | Human judgment, in `contract-release-freeze` |
| Evaluation: the regenerated root validates under the current set | [Regeneration record](0112-data-contracts-development-data-root-regenerate-provenance.md); `corpus verify` of `pilot-two-source-grouped-20261113` and `hawk-drone-pilot-v1` exit 0 in this audit |

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Every 17.7 rule has a failing fixture or is named as human judgment | The table above; every named test exists at the closing tree | pass |
| Regressions fail before their fix | `.venv/bin/pytest -q tests/corpus/records/test_stamp_read_recheck.py` and `tests/corpus/links/test_portable_provenance.py` on the code at `c81ee0f` | fail as expected: 2 of 3 read-race cases (`KeyError: 'changed_contracts'`, and a refusal of a served record), and the acceptance case, whose refusal named the temporary file while `run/receiver-identity/` existed; the still-unstamped case passes on both, as a guard |
| Fixes pass, with the affected areas | `.venv/bin/pytest tests/corpus/records tests/corpus/links tests/corpus/hosts tests/commands tests/core tests/schema/registry` | pass: 1099 passed |
| Contract-artifact tests `make ci` omits | `.venv/bin/pytest -m external tests/schema tests/corpus/records tests/corpus/links tests/corpus/hosts tests/commands` | pass: 128 passed |
| Plan integrity | `make lint-spec-plan` | pass: 0 findings |
| Full quality gate | `make quality` | pass: format, lint, typing, complexity, shell, links, plan, contracts and events; 2957 passed, 8 skipped, coverage 91.22%; Markdown lint; sdist and wheel built. It ran before one line of this record was rewrapped |
| Required CI and Markdown on the final tree | `make ci`, `make lint-md` | pass: 2818 passed, 147 deselected; spec-plan, contracts and events 0 findings; Markdown lint and 0 broken links |

## Audit handoff

No finding is left open. Fixed in this change: the read race between the check and the load, the
acceptance write before the staged-hashes pin check, the repeated statement of the stamped families,
and the drift of the Contracts and Leakage review pages.

Amended, with each owner's text stating it: `run-bundle-store` (the families to widen are now one
constant and a test, the AUD-data-contracts-audit-3 seam), `corpus-scale-pilot` (a precision mode is
an in-place edit with a re-pin and a regeneration of the discovery runs, not a minor) and
`telemetry-corpus-streams` (the declaration and frame-set extension follows the stage then in
force).

Dropped, each with its reason:

- A stamp whose structure and meaning maps name different contracts refuses
  `RECORD_SCHEMA_UNSUPPORTED` with `changed_contracts`, not `RECORD_TAMPERED`. No writer can produce
  one, it fails closed, and the remedy is the same; no work.
- A carried staged-hashes record placed inside a root whose stamp lacks `record/staged-hashes` is
  refused as a record of an unpinned contract. No current root lacks that contract, the refusal
  fails closed, and a carried record kept outside the root reads normally; no work.
- A tracked regeneration target: the only open task that edits a stamped contract in place is
  `corpus-scale-pilot`, and only if it adds a precision mode. Its text now states the regeneration,
  and since record 0111 an added contract needs none. No scheduled regeneration needs a script, and
  records 0106 and 0112 keep the procedure; no work.
- A read-only data-root status command: every root-taking command already refuses before any work
  with the same `changed_contracts` and remedy, so it would state the check a second time and save
  the operator no step; no work.
- With this audit closed, `data-contracts` keeps only `contract-release-freeze`, in the
  Human-Assisted lane, and no Agent-lane group. That task changes code itself, so its own per-change
  audit covers it at completion; no work.

## Close or resume

Every gate passed. The task has left the plan, and the `data-contracts` group no longer has an
Agent-lane section. The Contracts, Leakage review and Discovery runs pages and the records index
are updated. `run-bundle-store`, `corpus-scale-pilot` and `telemetry-corpus-streams` are amended.
Plan counts after: 125 agent and 30 human tasks; next agent `scenario-contract`, next human
`define-locked-test-policy` (optional). `data-contracts` remains planned for
`contract-release-freeze` alone.
