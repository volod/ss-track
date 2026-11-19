# Task Record

development-unstamped-scan-reuse

## Task and scope

- Id / capability: `development-unstamped-scan-reuse` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `361d4fa`, no unrelated dirty files.
- Plan counts at start: 127 agent, 30 human; next agent `development-unstamped-scan-reuse`
  (optional), next human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-unstamped-scan-reuse (optional)

On a root without `contract-set.json`, one command can walk the whole root several times: the CLI
check, the operation's own check, each sealed read before the first write, and the locked check
before that write. One measured scan of 25,000 PNG files took about 0.7 seconds, so a command on a
large unstamped root can spend several seconds in repeated scans, and the documented cost states
only one scan.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A command on a large unstamped root scans it as few times as safety allows,
  and the Contracts page states the per-command cost.
- Scope boundary: Scan scheduling within one command. Keep the locked recheck before the first
  stamp and the recheck before a read when a record could have arrived since the last scan; do not
  weaken fail-closed handling or change released behavior.
- Data and artifact paths: `src/ss_track/core/evidence/`, `tests/corpus/records/`.
- Execution path: Count scans per command on a representative root, then reuse a scan result for
  repeated checks of the same root where no write or read window separates them, for example
  between the CLI check and the operation's first check.
- Acceptance gates: A test counts scans for a read-only command and a first-write command on an
  unstamped root and shows fewer full walks; every existing unstamped-evidence regression still
  refuses. Report before and after per-command time on a large root. `make ci` passes.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: none.

## Implementation

Baseline, counted by wrapping `first_unstamped_record` on fresh unstamped roots: `corpus stage`,
`corpus verify` and `corpus build` walked three times before refusing (the CLI check, the
operation's check and the manifest or source reader's check), and a first `import` walked three
times (CLI, operation, locked first stamp). A sealed read on a root still unstamped would have
walked once more per read.

`core/evidence/checked_roots.py` now holds the checked-roots context that `contract_stamp.py` kept,
with the containment rule `holds_path`. Each entry records whether a clean walk happened in the
current command. `commands/report.py` `reported` runs every command inside `one_command`, and a
later `require_current_data_root` of the same unstamped root in that command reuses the walk when
no sealed read or write of a path under it came between them. A read (`check_before_read`) or a
write (`stamp_before_write`) ends the reuse for every checked root holding its path, so an
enclosing root walks again after a nested root receives a record. The first-stamp check under the
root lock always walks. A stamp present at a check is always parsed and verified, so a stale stamp
written since still refuses. Library calls outside a command walk at every check, as before.

The read recheck no longer walks the root. `check_before_read` verifies a stamp that appeared since
the check, and otherwise returns the missing stamp; `core/evidence/sealed.py` then refuses the JSON
object it loaded when it holds both `kind` and `manifest_sha256` (`unstamped.is_record_shaped`, the
walk's key rule), with the same `RECORD_SCHEMA_UNSUPPORTED` refusal and remedy as a walk, naming
that record. This is exact: a sealed read passes only an object holding both keys, and in an
unstamped root such a file is unstamped evidence whatever else the root holds. Judging the bytes
actually loaded also closes the gap between a walk and a later read of a swapped file. A read that
fails anyway, of a missing or non-record file, now reports `RECORD_TAMPERED` where a walk might
have found other evidence first and reported `RECORD_SCHEMA_UNSUPPORTED`; nothing unproven is
served either way.

After this command writes the first stamp, its entry is marked stamped, so later reads take the
stamped fast path. The stamp file's parser and writer moved to `core/evidence/stamp_file.py`
(with `STAMP_NAME`, `STAMP_KIND` and `REGENERATE_REMEDY`) to keep `contract_stamp.py` near the
module-size guide; importers and the sealed-read gate's allow-list now name that module. No CLI
contract, refusal code, record byte, seal, contract file or dependency changed. Rejected: reusing a
walk across read or write windows or outside a command, which would move the refusal of a record
that arrived meanwhile from the check to the read or write. The
[Contracts page](../current/contracts.md#development-stage) states the per-command cost.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Fewer walks for read-only and first-write commands | `.venv/bin/pytest -q tests/corpus/records/test_unstamped_scan_reuse.py` | pass: `stage`, `verify`, `build` 3 to 1 walk; first `import` 3 to 2; stamped repeat 0 |
| Reuse ends at reads, writes and nested roots; stamps still verified | Same file | pass: late record refused at read with no walk and at write by the locked walk; nested write forces outer rewalk; stale stamp refused; another command's stamp verified and its record served |
| Existing unstamped-evidence regressions still refuse | `.venv/bin/pytest -q tests/corpus/records/` | pass, including `test_unstamped_evidence.py` and `test_contract_stamp.py` unchanged in behavior |
| Before and after per-command time on a large root | Scratch script, not kept; baseline from a `HEAD` worktree; fresh root per run of 25,000 4 KiB PNG files (102.4 MB) in 50 directories, warm cache, three runs each | `corpus stage` (refused `CORPUS_NOT_BUILT`): 0.671, 0.620, 0.617 s with 3 walks before; 0.277, 0.216, 0.216 s with 1 walk after. First `import`: 0.640, 0.635, 0.644 s with 3 walks before; 0.476, 0.491, 0.486 s with 2 walks after |
| Required CI | `make ci` | pass: 2706 passed, 155 deselected |
| Plan, links and Markdown | `make lint-md lint-spec-plan lint-doc-links` | pass |

## Audit handoff

none identified. Reviewed every `require_current_data_root`, `check_before_read` and
`stamp_before_write` caller, the command entry points in `commands/report.py`, nested and linked
roots, a stamp appearing or disappearing between checks, the released stage and library calls
outside a command. Every read of an unstamped root still refuses a record-shaped object and every
first stamp still walks under the lock.

## Close or resume

Every gate passed. The task left the plan; the Contracts page and records index are updated. Plan
counts after: 126 agent and 30 human tasks; next agent `data-contracts-audit` (optional), which
reviews this change with the rest of the group. `data-contracts` remains planned.
