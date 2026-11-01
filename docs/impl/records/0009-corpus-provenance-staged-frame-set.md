# Staged frame set

## Task and scope

- Id / capability: `staged-frame-set` / `corpus-provenance`
- State: accepted.
- Source: plan task; starting commit `8904ca3ab938b2638b017c7d4ee7cde23ee1a4a3`; clean worktree.
- Plan counts at start: 88 tasks (67 agent, 21 human). Next agent: staged-frame-set;
  next human: select-development-workload.
- Accepted task:

```markdown
#### staged-frame-set

Nothing pins which frames a corpus version staged, so a run could read a bundle no scenario
declared.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` writes one sealed frame-set record naming every stream and
  generated-case bundle hash and each source record, and a scenario can pin its single hash.
- Scope boundary: One record per corpus version, beside its manifest. Runner enforcement belongs to
  the scenario and runner tasks.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`,
  `$DATA_DIR/corpus/<corpus-id>/frame-set.json`.
- Execution path: Write the record after the last bundle under the staging lock, and compare it in
  `corpus verify`.
- Acceptance gates: Two stagings give one frame-set hash, across data roots. A replaced or missing
  bundle fails `corpus verify` by name, and an interrupted stage leaves no frame set.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus stage` now seals one `frame-set.json` beside the corpus manifest, after the last bundle and
under the staging lock, and `corpus verify` compares the staged bundles with it before hashing frames.
Both report `frame_set_sha256`, so a scenario has one hash to pin. The new
`src/ss_track/corpus/frame_set.py` owns the record, `refusal.py` gains `FRAME_SET_NOT_STAGED` and
`FRAME_SET_MISMATCH`, and `staging.py` calls it. The
[current corpus contract](../current/corpus.md#frame-set) states the behavior.

Decisions beyond the task's wording:

- The record is written once and never rewritten. A stage that recomputed it would make a replaced
  bundle pass, which is the failure the test plan names, so a repeated stage compares and refuses.
- The hash is the record's ordinary seal, reported as `frame_set_sha256`. A second identity hash would
  be another rule for one fact.
- It carries `corpus_manifest_sha256`, so it pins membership and splits as well as bytes. Versions that
  share every bundle therefore have different frame sets, which bundle hashes alone would not show.
- A directory no line names is refused, at stage and at verify, as `unnamed`. The specification says
  such a bundle is not part of the corpus, and a stage that succeeded while verify refused would be
  worse, so a first stage beside one writes no record.
- A missing bundle stays `BUNDLE_NOT_STAGED`, naming the first, with its existing details. Existing
  tests pin that contract, and the check runs first, so a mismatch reports only bundles that exist.
- The frame set's own path sits outside `frames/`, so a killed write can leave a partial file beside
  the manifest, which the existing scratch cleanup did not reach. The lock now clears those too, and
  `SCRATCH_PREFIX` moved to `sealed.py`, which had a second copy of the literal. A stage needs a built
  manifest, so no concurrent build can own such a file.

Rejected: comparing each bundle's source and selection with the corpus before sealing. Reaching that
state needs a deliberately re-sealed bundle, because `_open_for_corpus` already requires this corpus
version and this stream, and an unkeyed seal cannot stop someone who re-seals on purpose. The check
would add a recipe comparison for a case and protect nothing a pin does not.

Compatibility: bundle and corpus manifests, their hashes and every schema are unchanged. `FramesResult`
gains a required `frame_set_sha256`, and `FramesResult.to_record` gains that key. A corpus staged
before this change is refused by `corpus verify` until one `corpus stage` adds the record without
touching a bundle. No environment variable, `pyproject.toml` or `uv.lock` change. `staging.py` is 250
lines, at the target, so `duplicate-frame-detection` should not add its search there; its execution
path already places it in `grouping.py`. `tests/corpus/test_frame_set.py` is about 490 lines and stays
one cohesive unit over one record.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| `corpus stage` writes one sealed record naming every bundle and source record | `tests/corpus/test_frame_set.py::test_staging_names_every_bundle_and_the_source_record_it_rests_on` | Pass, comparing the whole record, including a case resting on its parent's source record |
| A scenario can pin a single hash | `test_a_verified_corpus_reports_the_hash_a_scenario_pins`, `tests/test_cli.py::test_stage_then_verify_report_json_results` | Pass through `main`. Enforcing the pin belongs to `scenario-contract` |
| Two stagings give one hash across data roots | `test_two_stagings_give_one_hash_across_data_roots`, `test_a_second_process_writes_identical_bytes` | Pass, comparing bytes, with a case in the corpus, and across a process boundary |
| A replaced bundle fails `corpus verify` by name | `test_a_replaced_bundle_fails_verify_by_name`, `test_every_replaced_bundle_is_named_at_once`, `test_a_replaced_parent_of_a_case_is_named` | Pass. A replaced parent is `BUNDLE_CONFLICT` naming the case and parent |
| A missing bundle fails `corpus verify` by name | `test_a_missing_bundle_fails_verify_by_name_and_staging_restores_one_hash` | Pass, and re-staging restores the hash |
| A changed bundle does not keep its frame set | `test_a_stage_cannot_carry_the_record_along_with_a_replaced_bundle` | Pass: refused, with the record's bytes unchanged |
| An interrupted stage leaves no frame set | `test_a_failed_stage_leaves_no_frame_set_and_a_repeat_writes_one`, `test_a_case_that_fails_after_every_stream_leaves_no_frame_set`, `test_a_killed_run_leaves_no_partial_record_after_the_next_run` | Pass for a refusal, a failing case and a leftover partial file |
| An interrupted stage, killed for real | One-off: `SIGKILL` from inside `corpus stage` before a case, before the record write, and after the temporary file but before the rename, on the final code | Pass at all three: no `frame-set.json`, `corpus verify` refused, a resumed stage gave the expected hash, the partial file was removed and `corpus verify` passed. Script not kept |
| The record is written under the lock | `test_the_record_is_written_while_the_staging_lock_is_held` | Pass |
| Installed command flow | One-off: `python -m ss_track.cli` import, build, stage, verify and repeat of generated media, on two data roots | Pass with equal hashes. Script not kept |
| A corpus staged by the previous code | One-off: import, build and stage with `src/` from the starting commit, then this code | Pass: verify refused with `FRAME_SET_NOT_STAGED`, stage reported every bundle `unchanged` and wrote the expected hash, verify passed. Script not kept |
| A remux changes the hash over identical frames | One-off: two runs of the test media writer gave clips differing at byte 221 with equal frame hashes, and different frame-set hashes | Observed, not pinned by a test. This is why the page states it |
| Tests pin each check | One-off mutation of 24 faults in `frame_set.py` and `staging.py`, on a scratch copy with bytecode writing off | 24 caught, including the write moved outside the lock. Script not kept |
| Required gate | `make ci` | Pass: 563 tests, formatting, lint, typing, complexity, shell, links and plan integrity |
| Full gate | `make quality` | Pass: coverage 98.87% against a 90% floor, Markdown lint and package build |

A first timed `SIGKILL` sweep from outside the process was discarded as evidence: every delay landed
after the small clips had finished, so it exercised no interruption. The in-process kills above replaced
it. Tests ran on generated media through the pinned library. No external footage or network-backed
test was needed.

## Audit handoff

- `AUD-staged-frame-set-1`: A seal is unkeyed, so deleting `frame-set.json` and staging over a replaced
  bundle writes a new, self-consistent hash. Nonblocking until a scenario pins one. Owner:
  `scenario-contract`, amended in this change so that a pin differing from the `frame_set_sha256` of
  `corpus verify` refuses, with the specification stating the limit.
- `AUD-staged-frame-set-2`: `open_frame_bundle` reads any bundle directory without consulting a frame
  set, so a run could still read a bundle no scenario declared, which is the problem this task opened
  with. Nonblocking until a runner exists; the task's scope assigns it to the runner tasks. Owner:
  `lockstep-runner`, amended in this change to open only bundles its pinned frame set names.
- `AUD-staged-frame-set-3`: The two new refusals were absent from the codes `lockstep-runner` maps to
  `RUNNER_INVALID`, so a frame-set failure had no defined run outcome. Owner: `lockstep-runner`, amended
  in this change.
- `AUD-staged-frame-set-4`: One hash makes the cross-architecture comparison a single equality, and a
  bundle that re-stages differently on another host is now a refusal, not silent drift. Owner:
  `arm64-reproducibility`, amended in this change to compare `frame_set_sha256` first.
- `corpus verify` hashes every frame, so a scenario that runs it pays for a full read before a run.
  Dropped, needing no work: `read_frame` already hashes each frame it returns, and no runner exists to
  measure. `scenario-contract` keeps the gate as written.
- A frame set outlives a bundle removed under retention. Dropped, needing no work: it holds only hashes,
  which is what lets `corpus verify` keep refusing, and the current page states it.
- `corpus verify` takes no lock, so one run during a stage can be refused for a bundle not yet
  published. Dropped, needing no work: it refuses rather than passes, and repeating it settles it.
- Reviewed malformed, other-schema and damaged records, a record of another corpus state, one-sided
  lines, a stray directory, and legacy staging. No additional work identified.

## Close or resume

All required gates passed. The current corpus page, its area index and the records index link this
record, and the specification and test plan are updated. Removed `staged-frame-set`, dropped it from
the dependencies of `duplicate-frame-detection` and `scenario-contract`, which needed nothing further
from it, and amended `scenario-contract`, `lockstep-runner` and `arm64-reproducibility`. Remaining plan:
87 tasks (66 agent, 21 human); next agent is `duplicate-frame-detection`, next human is
`select-development-workload`. `corpus-provenance` remains planned because its other tasks remain. No
service, port or external resource was started, and scratch evidence stayed outside the repository.
