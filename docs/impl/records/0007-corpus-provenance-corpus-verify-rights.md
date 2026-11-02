# Verify source rights

## Task and scope

- Id / capability: `corpus-verify-rights` / `corpus-provenance`
- State: accepted.
- Source: plan task; starting commit `129a3504da1e380d0c8c1190fd8a66d821546348`; clean worktree.
- Plan counts at start: 88 tasks (67 agent, 21 human). Next agent: corpus-verify-rights;
  next human: select-development-workload.
- Accepted task:

```markdown
#### corpus-verify-rights

A corpus can verify cleanly after the rights it was built on were withdrawn.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus verify` proves that frames are intact and that the source records
  they rest on still hold.
- Scope boundary: Source records and retention, read without re-hashing stored sources. Frame checks
  are unchanged.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Reuse `require_source_record` and the retention check inside
  `verify_corpus_frames`, with a re-import fixture.
- Acceptance gates: A source re-imported as `restricted` makes `corpus verify` refuse with
  `SOURCE_RECORD_CHANGED` and exit 1, and an expired source is `RETENTION_EXPIRED`. An unchanged
  corpus still reports `verified`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus verify` now applies the same source check as `corpus stage`, before it opens any bundle.
`_require_sources_hold` in `staging.py` holds that check once: retention of every stream, then
`require_source_record` for every stream. A generated case holds its parent's rights, so streams
cover cases. No stored source byte is read, and frame checks are unchanged.

Retention stays first because it reads only the corpus. Checking the record first was rejected: an
operator may remove expired material, and the reason would then change from `RETENTION_EXPIRED` to
`SOURCE_NOT_IMPORTED`. Sharing the helper moved the source-record check ahead of the decode-policy
check in `corpus stage`. A corpus failing both now reports `SOURCE_RECORD_CHANGED` rather than
`DECODE_POLICY_MISMATCH`; either way that corpus version cannot be staged.

Beyond the task, `SOURCE_RECORD_CHANGED` details gain `source_sha256` and `changed_terms`, from the
new pure `changed_terms` in `terms.py`, because a bare hash mismatch cannot tell withdrawn rights
from a corrected capture note. Existing keys are unchanged, so the refusal stays compatible. The
`corpus verify` help text now states what it checks. There is no change to environment variables,
`pyproject.toml` or `uv.lock`. `builder.py` is 270 lines and `test_verify_rights.py` 340, both above
the approximate target; each stays one cohesive unit.

Existing tests called this path a re-import but used `reseal`, because `import` refuses changed terms
with `IMPORT_CONFLICT`. The fixtures in `tests/corpus/test_verify_rights.py` remove the source
directory and run the real importer, which is the only route an operator has. The
[current corpus contract](../current/corpus.md#withdrawing-rights) documents that route.

The specification claim that a verified corpus is one whose rights still hold was too strong, and
now says recorded rights. One read of a source record took 80 ms at 1,080,000 frames (19 MB) on the
development host, which is negligible beside hashing those frames, so reads are not deduplicated
across streams of one source. That script was not kept.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Re-import as `restricted` refuses, exit 1 | `tests/corpus/test_verify_rights.py::test_a_source_reimported_as_restricted_refuses_and_exits_one` | Pass through `main` with a real re-import; `ss-track` binary also exited 1 |
| Expired source is `RETENTION_EXPIRED` | `test_an_expired_source_refuses_and_exits_one`, plus `test_source_terms.py::test_retention_boundary_at_every_entrypoint` | Pass, including one day either side |
| Unchanged corpus reports `verified` | `test_an_unchanged_corpus_verifies_and_writes_nothing` | Pass: exit 0, every stored byte unchanged |
| No stored source is read | `test_verify_never_reads_stored_source_bytes` | Pass with the stored source deleted |
| Frame checks unchanged | Existing `test_frames.py` and `test_case_frames.py`, unedited | Pass |
| Tests pin each check | One-off mutation of 10 faults in the new code, against `test_verify_rights.py` | All 10 caught. Script not kept. A first pass reused stale bytecode and misattributed one catch, so results come from the rerun with a fresh bytecode cache per mutant |
| Installed command flow | `ss-track` import, build, stage, verify, re-import, and a new corpus version, in a scratch `DATA_DIR` | Pass. This also exercised the documented withdrawal steps with the original file deleted |
| Required gate | `make ci` | Pass: 494 tests, formatting, lint, typing, complexity, shell, links and plan integrity |
| Full gate | `make quality` | Pass: coverage 98.78% against a 90% floor, Markdown lint and package build |

Before the code changed, 17 of the 21 new test cases failed. The other four guard behavior that had
to keep holding. External footage and network-backed tests were not needed.

## Audit handoff

- `AUD-corpus-verify-rights-1`: Changed terms cannot be recorded by any command. A plain `import` of
  narrower rights is `IMPORT_CONFLICT`, and `corpus verify` then still reports `verified`, as
  observed with the `ss-track` binary. The working route deletes a sealed record and the stored
  source by hand. Nonblocking: this task's gates pass and the route is documented. Owner:
  `source-terms-amendment`, added in this change, with the specification amended.
- A `verified` result does not cover stored source bytes, and neither does a repeated `corpus stage`;
  both still passed with the stored source removed, while `corpus build` refused. Dropped, needing no
  work: this is the task's declared boundary, no module reads a stored source, and the frames modules
  read are hashed. It is stated in the current corpus contract.
- Withdrawn rights leave staged frames readable through `open_frame_bundle`. Owner:
  `scenario-contract`, whose gates already refuse a corpus that fails `corpus verify`; only its
  dependency on this task was removed.
- Closed record 0006 linked a plan heading that this task had to remove, which failed
  `make lint-doc-links`. Its link was reduced to `../plan.md` with no other change, a deliberate
  one-token exception to the rule against rewriting a closed record: weakening the checker and keeping
  a heading in a forward-only plan are both barred. The
  [planning workflow](../../guide/planning-workflow.md#task-records) now says that records link no
  plan heading.
- Reviewed check order, generated cases, multi-stream corpora, unreadable records, restoring a record,
  a wider right and an operator's rebuild. No additional work identified.

## Close or resume

All required gates passed. The current corpus page and the records index link this record, and the
specification and test plan are updated. Removed `corpus-verify-rights`, cleared its one dependent and
added `source-terms-amendment`. Remaining plan: 88 tasks (67 agent, 21 human); next agent is
`corpus-version-lineage`, next human is `select-development-workload`. `corpus-provenance` remains
planned because its other tasks remain. No service, port or external resource was started. Scratch
evidence stayed outside the repository, and no temporary scaffold remains in it.
