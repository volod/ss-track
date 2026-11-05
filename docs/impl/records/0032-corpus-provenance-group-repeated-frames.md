# Repeated frames in one group

## Task and scope

- Id / capability: `group-repeated-frames` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `814613a`; clean worktree.
- Plan counts at start: 132 tasks (110 agent, 22 human). Next agent:
  `group-repeated-frames (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### group-repeated-frames (optional)

A remux of one recording held twice inside one group counts each frame twice, in anything aggregated
by encounter, and only a frame in two streams of one source is refused today.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` and `corpus verify` refuse a run of identical frames in two
  streams of one group of one version with `STREAM_OVERLAP`, naming both streams and the first shared
  frame.
- Scope boundary: The run definition that `shared_runs.py` already applies, in one version. A copy
  replacing its original across linked versions stays accepted, because no version counts a frame
  twice.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Report same-group pairs from `find_shared_runs` for streams of one version, and
  raise them in `require_unshared_runs` beside the cross-group refusal.
- Acceptance gates: A remux in two encounters of one group and in one encounter are each
  `STREAM_OVERLAP`. A cross-group pair stays `SPLIT_LEAKAGE`, a copy replacing its original in a linked
  version stages normally, and adjacent windows of one recording still share nothing.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`find_shared_runs` now reports a run shared by two streams of one group when both streams belong to
the version being checked. A stream is not paired with its own earlier window, and a copy that
replaces its original in that group of a linked version is not a pair. `require_unshared_runs`
raises `STREAM_OVERLAP` for those pairs, with the same `shared_runs` details as the cross-group
refusal, naming both streams and the frame each one shows first. A version that also shares a run
with another group is `SPLIT_LEAKAGE`, and that refusal names only the cross-group pairs.

Stage and verify match a frame set that exists before the run, so a replaced bundle stays
`FRAME_SET_MISMATCH`. A first stage still refuses the run before writing cases or a frame set.
When verify finds no frame set, it names a repeated run before reporting that staging has not
finished. A generated case is still opened first, so a refusal that never staged the case is
`BUNDLE_NOT_STAGED`.

The run length, held-frame rule and predecessor walk are unchanged. No manifest, hash, schema,
refusal-code list, environment variable, `pyproject.toml` or `uv.lock` change. Build-time
`STREAM_OVERLAP` still names one source's overlapping windows. A corpus already staged with a remux
inside one group now fails `corpus verify`. Current page:
[shared frames](../current/corpus.md#shared-frames).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A remux in two encounters of one group is `STREAM_OVERLAP`, naming both streams and the first shared frame | `tests/corpus/bundles/test_group_repeated_frames.py::test_a_remux_in_one_group_is_overlap_naming_both_streams[two-encounters]` | pass, on the H.264 remux fixture; verify repeats the code |
| A remux in one encounter is `STREAM_OVERLAP` | same test, `[one-encounter]` | pass |
| Stage and verify exit 1 with that code and leave no frame set | `test_stage_and_verify_exit_with_the_overlap_and_leave_no_frame_set` | pass, through `main` |
| A cut copy names each stream's first shared frame | `test_a_cut_copy_in_one_group_names_where_each_stream_first_shows_the_frame` | pass, frames 0 and 9 |
| A version staged before the rule fails verify | `test_verify_refuses_a_same_group_remux_already_in_its_frame_set` | pass; the check was disabled only for that stage |
| A mismatched frame set is named before the run | `test_a_mismatched_frame_set_is_named_before_the_overlap` | pass, `FRAME_SET_MISMATCH` |
| A cross-group pair stays `SPLIT_LEAKAGE` | `tests/corpus/bundles/test_duplicate_frames.py::test_a_remux_in_two_groups_is_leakage_naming_both_streams`, `tests/corpus/bundles/test_shared_runs_group.py::test_a_cross_group_run_stays_leakage_when_the_same_group_also_overlaps` | pass; a mixed version names only the cross-group pairs |
| A copy replacing its original in a linked version stages | `tests/corpus/bundles/test_duplicate_frames_chain.py::test_a_copy_in_its_originals_group_across_versions_stages_normally` | pass, and verify does too |
| Adjacent windows of one recording share nothing | `tests/corpus/bundles/test_duplicate_frames_allowed.py::test_adjacent_windows_of_one_recording_in_one_group_stage_normally`, `test_adjacent_windows_of_a_remux_share_no_frame_and_stage_normally` | pass, inside one group and across groups |
| The run rule on its boundaries, including a loop and a short same-group stretch | `tests/corpus/bundles/test_shared_runs.py`, `test_shared_runs_group.py` | pass |
| Required gate | `make ci` | pass: 1667 tests, format, lint, typing, complexity, shell, links, plan and contracts |

## Audit handoff

- A generated case is not staged after the refusal, so `corpus verify` names `BUNDLE_NOT_STAGED`
  rather than the run. Dropped, needing no work: stage already named the run, and the missing case
  is the state of the bundles. The current page states it.
- A version that both repeats a run inside a group and shares one with another group reports only
  `SPLIT_LEAKAGE`. Dropped, needing no work: one refusal states one problem, and the next stage
  names the same-group pairs. The current page states the order.
- A re-encoded copy still shares no frame hash. Dropped, needing no work: `near-duplicate-detection`
  already states it.
- Adjacent windows of one recording stay invisible to frame hashes. Dropped, needing no work: the
  frames are not in both streams, and the current page states it.
- A copy that replaces its original across linked versions stays accepted. Dropped, needing no
  work: that is the task's scope boundary, and no version counts the frame twice.

## Close or resume

All gates passed. The current corpus page states the rule, the stage and verify order and the
remaining limits, and links this record. The plan task is removed; no task depended on it. Plan
counts after: 131 tasks (109 agent, 22 human); next agent is `unlinked-version-report (optional)`,
next human is `select-development-workload`. `corpus-provenance` stays planned because its other
tasks remain. No service, port or external resource was started.
