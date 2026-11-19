# Task Record

development-explicit-path-revision-root

## Task and scope

- Id / capability: `development-explicit-path-revision-root` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `49214bb`, no unrelated dirty files.
- Plan counts at start: 128 agent, 30 human; next agent `development-explicit-path-revision-root`,
  next human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-explicit-path-revision-root

`ss-track annotate freeze` with `--source`, `--labels-out` and `--revision-out` runs without a
data-root check. A `--revision-out` inside `DATA_DIR` therefore publishes a sealed
`record/annotation-revision` without a contract stamp and without scanning for unstamped evidence.
On a fresh root, the next root-checking command finds that record and refuses the operator's new
revision with the regenerate remedy. On a stamped root the write skips the stamp check that every
other sealed write gets. Reproduce: set `DATA_DIR` to an empty directory, freeze with
`--revision-out "$DATA_DIR/revision.json"`, then run `ss-track corpus inspect-source`; it refuses
`RECORD_SCHEMA_UNSUPPORTED`. Expected: a sealed write that lands in the data root is held to the
root's contract set and stamps it, and a write outside the root stays standalone.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An explicit-path freeze into `DATA_DIR` checks and stamps the root before
  publishing, so the next command accepts its revision; a freeze outside the root is unchanged.
- Scope boundary: The explicit-path write route of `annotate freeze` and any other explicit-output
  sealed writer found by the same review. Do not change record bytes, the `--corpus --stream`
  route, released behavior or frozen contracts.
- Data and artifact paths: `src/ss_track/commands/annotate.py`, `src/ss_track/annotate/review/`,
  `src/ss_track/core/evidence/contract_stamp.py`, `tests/annotate/`, `tests/corpus/records/`.
- Execution path: When an explicit sealed output resolves inside the data root, check the root
  before work so `write_sealed` stamps it; review other explicit `--out` sealed writers for the same
  route.
- Acceptance gates: A fresh root receiving an explicit-path revision is stamped and a following
  root-checking command succeeds; a root with unstamped evidence refuses the freeze before writing;
  an output outside `DATA_DIR` writes no stamp. `make ci` passes.
- Documentation target: [Contracts](current/contracts.md) and [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

`commands/report.py` `check_root_holding(*outputs)` resolves the data root and, when any explicit
output lies under it, runs `require_current_data_root` before the command does any work. The check
registers the root, so the later `write_sealed` stamps it under the root lock and rechecks it there,
exactly as a root-taking command does. An output outside the root does not read the root and writes
no stamp. `commands/annotate.py` calls it for the `--labels-out --revision-out` route of
`annotate freeze`, before the inputs are loaded, so a refused root receives neither file. The
`--corpus --stream` route already used `checked_data_root` and is unchanged.

Containment is one rule: `core/evidence/contract_stamp.py` `holds_path(root, path)` compares the
output as spelled and resolved with the root as spelled and resolved, so an output reached through
a link into the root, or by the real path of a root that `DATA_DIR` names through a link, counts as
inside. `_checked_root`, the write-time lookup of which root to stamp, now uses the same function
instead of its own spelling comparison. The check sits in the CLI rather than in `freeze_labels`,
because a path-only library call has no data root to infer; that boundary is the one the
[unstamped-evidence record](0104-data-contracts-development-unstamped-evidence.md) set.

No record bytes, seal, frozen contract, dependency or released-stage behavior changed: in the
released stage the root check returns before reading anything. Spec section 17.7 now names the
explicit-path rule. Current pages: [Contracts](../current/contracts.md#development-stage) and
[Corpus](../current/corpus.md#annotation-review).

Rejected: checking only `--revision-out`. The label document is written first and belongs with the
revision, so a refused root should receive neither; a check when only the labels land in the root
reads the root and stamps nothing, because no sealed record is written there.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Regression fails before the fix | `.venv/bin/pytest -q tests/annotate/review/test_explicit_path_root.py` on the starting code | fail as expected with `src/` stashed: 5 of 6 cases (fresh root at top level and nested, linked folder, linked root, unstamped root); the outside-root case already passed |
| Fresh root is stamped and the next root-checking command succeeds | Same file: `test_a_freeze_into_a_fresh_root_stamps_it_for_the_next_command` (top level and nested), linked-folder and linked-root cases | pass; `corpus inspect-source` passes the root check and answers `SOURCE_NOT_IMPORTED` |
| Unstamped evidence refuses before writing | `test_a_root_with_unstamped_evidence_refuses_the_freeze_before_writing` | pass; `RECORD_SCHEMA_UNSUPPORTED` with the remedy, no output folder, no stamp |
| Output outside `DATA_DIR` writes no stamp | `test_a_freeze_outside_the_root_writes_no_stamp` | pass; succeeds even though the root holds unstamped evidence |
| Plan reproduction with the real CLI | `ss-track annotate freeze ... --revision-out "$DATA_DIR/revision.json"` then `ss-track corpus inspect-source --source-sha256 <64 zeros>`, on a scratch `DATA_DIR` with fixture inputs | before the fix: no stamp, then `RECORD_SCHEMA_UNSUPPORTED`; after: `contract-set.json` written, then `SOURCE_NOT_IMPORTED`. Scratch data was not kept |
| Required CI | `make ci` | pass: 2693 passed, 155 deselected; `make lint-doc-links lint-spec-plan lint-md` rerun after the doc edits, 0 findings |

## Audit handoff

Reviewed every command that reports through `reported` without taking the data root, for a sealed
write to an explicit path: `annotate validate` and `compare` (read only), `annotate freeze` by paths
(fixed here), `discover inventory --out` (a declaration through `write_once`, no seal),
`discover review-unpack --out` (operator recipe files), `discover review-audit --review` (an
operator review draft), and `contracts list`, `validate`, `diff`, `freeze`, `export` and `docs`
(registry files and generated documents). None other publishes a sealed record. Root-taking
commands with `--out`, such as `discover queue`, `blind`, `unblind` and `export`, already check the
root; an output inside it is stamped, one outside it is standalone, which is the rule this change
states.

Dropped observations, each with its reason:

- `discover review-unpack --out` into the data root copies operator recipes, which may be `.json`,
  without a root check. They are operator inputs, not records ss-track publishes. If one carries
  both record keys, the unstamped scan refuses it, which is the fail-closed outcome; copying files
  into a stamped root by hand is outside any writer's contract. No work.
- `contracts validate --file` reads any JSON file, including one under `DATA_DIR`, without the root
  check. It is a standalone schema check that reports validity and does not treat the file as
  evidence for a later step. No work.
- The freeze adds the usual one CLI check plus one locked check on an unstamped root, the same as a
  root-taking first write. Scan reuse is already owned by `development-unstamped-scan-reuse`
  (optional), whose text names the CLI check and the locked check. No new routing.

No bug or improvement is left open by this change.

## Close or resume

Every gate passed. The task has left the plan; the Contracts and Corpus pages, spec section 17.7
and the records index are updated. Plan counts after: 127 agent and 30 human tasks; next agent
`development-unstamped-scan-reuse` (optional), next human `define-locked-test-policy` (optional).
`data-contracts` remains planned.
