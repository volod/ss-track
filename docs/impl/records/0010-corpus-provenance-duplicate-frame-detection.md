# Duplicate frame detection

## Task and scope

- Id / capability: `duplicate-frame-detection` / `corpus-provenance`
- State: accepted.
- Source: plan task; starting commit `fd982a11a0a0ae640084f71c6f619736fcb66fc1`; clean worktree.
- Plan counts at start: 87 tasks (66 agent, 21 human). Next agent: duplicate-frame-detection;
  next human: select-development-workload.
- Accepted task:

```markdown
#### duplicate-frame-detection

A remuxed copy of one recording crosses a split with every frame identical, because sources are
compared by byte hash.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` refuses two groups that hold a run of identical decoded
  frames, within one corpus version or against the versions it supersedes. A source hash cannot see
  a remux, so version lineage alone lets one change split between versions.
- Scope boundary: Exact frame hashes from sealed indexes, over a named minimum run of frames that
  are not all alike. No new decode. Re-encoded copies belong to `near-duplicate-detection`. A
  predecessor whose bundles were removed cannot be compared, and is reported rather than treated as
  clear.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add a pure run search over frame indexes to `grouping.py`, called before the frame
  set is written, with remuxed real-media fixtures. Walk the chain with `read_predecessors` in
  `lineage.py`, and open each predecessor's indexes through `open_frame_bundle`.
- Acceptance gates: A remux of one recording in `development` and `locked` is `SPLIT_LEAKAGE`,
  naming both streams and the first shared frame. So is a remux that a linked version places in
  another group than its original, naming both versions. Two independent clips sharing a black frame
  stage normally, and a generated case never compares against its own parent. A predecessor with no
  staged bundles is named as not compared.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus stage` and `corpus verify` now refuse two groups holding a run of identical decoded frames,
in one version or against the versions it supersedes, and both report what they compared as
`shared_frames`. The new `src/ss_track/corpus/shared_runs.py` owns the rule and touches no disk, and
the new `src/ss_track/corpus/duplicate_frames.py` reads the sealed indexes and says what it could
not read. `lineage.py` gains `follow_links`, which `read_predecessors` now uses, and
`_open_for_corpus` moved from `staging.py` to `frames.py` as `open_corpus_bundle`, so a
predecessor's bundle gets the same checks. The [current corpus
contract](../current/corpus.md#shared-frames) states the behavior.

Decisions beyond the task's wording:

- The pure search is in `shared_runs.py`, not `grouping.py` as the execution path said. It took
  `grouping.py` to 296 lines, and it has its own data and its own seam. `grouping.py` is unchanged.
- "A run not all alike" is stricter than two different frames: eight different frames in a row. A
  capture card showing `no signal`, then black, would otherwise refuse two independent clips, with
  no override. Eight frames with two states, or a blinking screen, are not evidence of one
  recording.
- A frame held in place counts once. Without this a clip repeating every frame, as 12.5 fps content
  in a 25 fps file does, has no eight different frames in eight positions, so its remux would pass.
- `corpus verify` runs the check too, which the task did not ask for. A predecessor staged after its
  successor was not there to compare with, and a corpus staged by earlier code holds a frame set
  over a leak. Both then verified with nothing noticing.
- The check runs after streams and before cases, earlier than the task required, so a refused
  version spends nothing on its cases.
- A predecessor with no frame set is not compared, and is named. Without this rule, the documented
  repair fails: a version refused for holding both copies stays in the chain, and its successor,
  which dropped one, shares a run with the dropped copy. Such a version was never pinned.
- A removed predecessor manifest is named and ends the walk, rather than refusing. A build requires
  a whole chain, but `test_stage_and_verify_do_not_need_a_versions_predecessors` pins that stage and
  verify do not. A rebuilt predecessor and a damaged record are refused, as the specification
  requires.
- A predecessor under another decode policy is compared and also named, as `other_decode_policy`.
  Listing it only as compared would claim a clear result that differing hashes cannot give.
- The report is not sealed. It depends on what one data root holds, and the frame set is identical
  on every data root.

Rejected: seeding on every shared frame, whose posting lists are quadratic on a black lead-in; and
comparing bundle hashes, which cover the source hash and differ for a remux by construction.

Compatibility: `FramesResult` gains a required `shared_frames`, and `to_record` gains that key.
Stage and verify now read the declared chain, so a rebuilt predecessor or a damaged predecessor
record they used to ignore is now refused. A corpus already staged with a run across groups stays on
disk and is refused. No manifest, hash or schema changes, no new refusal code, and no change to the
environment, `pyproject.toml` or `uv.lock`. `frames.py` grew to 292 lines, past the 250 target: the
move took `staging.py` from 250 to 233, and the function belongs with bundle opening.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A remux in `development` and `locked` is `SPLIT_LEAKAGE`, naming both streams and the first shared frame | `tests/corpus/test_duplicate_frames.py::test_a_remux_in_two_groups_is_leakage_naming_both_streams`, `test_a_cut_copy_names_where_each_stream_first_shows_the_frame` | Pass on H.264 with B-frames remuxed from Matroska to MP4 and back, and on a copy cut 9 frames in |
| The fixture is a real remux | `test_a_remux_keeps_every_decoded_frame_and_changes_every_source_hash` | Pass: other source hash, equal frame hashes |
| A remux a linked version places in another group is refused, naming both versions | `tests/corpus/test_duplicate_frames_chain.py::test_a_remux_a_linked_version_places_elsewhere_is_leakage_naming_both_versions`, `test_a_version_that_keeps_only_the_copy_elsewhere_is_refused_by_its_predecessor`, `test_a_copy_is_compared_with_the_whole_declared_chain` | Pass, inside one split and two versions back |
| Independent clips sharing a black frame stage normally | `test_a_shared_black_frame_stages_normally`, `test_a_lead_in_longer_than_a_run_stages_normally` | Pass on lossless clips, each asserting the frames really are shared |
| A generated case never compares against its own parent | `test_a_generated_case_never_compares_against_its_own_parent` | Pass, asserting the case's frames are a subset of its parent's. A case shares its parent's group, so reading only streams is what the test can observe |
| A predecessor with no staged bundles is named as not compared | `test_a_predecessor_with_no_staged_bundles_is_named_as_not_compared`, `test_a_never_staged_predecessor_is_named_and_checked_once_it_is_staged`, `test_a_removed_manifest_ends_the_chain_and_is_named` | Pass for removed bundles, no frame set and a removed manifest |
| The repair path works | `test_a_version_repaired_by_dropping_its_copy_stages_normally` | Pass |
| The run rule on its boundaries | `tests/corpus/test_shared_runs.py` | Pass: exact minimum, one short, held, blinking and looped frames, stream edges, pair order |
| Installed command flow | One-off: `python -m ss_track.cli` import, build, stage and verify of a 100-frame H.264 clip and its remux, in one version and across a linked version | Pass: exit 1 naming 100 shared frames, with no frame set, and `v1` still verified. Script not kept |
| A corpus staged by the previous code | One-off: import, build and stage a leaking corpus with `src/` from the starting commit, then this code | The old code staged and verified it. This code refused both commands with `SPLIT_LEAKAGE`, leaving the frame set's bytes unchanged. Script not kept |
| Tests pin each check | One-off mutation of 41 faults in `shared_runs.py`, `duplicate_frames.py`, `staging.py`, `lineage.py` and `frames.py`, on a scratch copy with bytecode writing off | 41 caught, against a passing baseline with the copy's package confirmed under test. Script not kept |
| Cost | One-off: run search over synthetic indexes, and `open_frame_bundle` on a million-frame index | About 1 s per million frames searched, 2 s per million read, and 600 MB per million. Synthetic hashes, no staged footage |
| Required gate | `make ci` | Pass: 617 tests, formatting, lint, typing, complexity, shell, links and plan integrity |
| Full gate | `make quality` | Pass: coverage 98.94% against a 90% floor, Markdown lint and package build |

A first mutation run reported 41 of 41 caught and was discarded: the scratch copy lacked
`AGENTS.md`, so the baseline itself failed and every fault looked caught. The harness now stops on a
failing baseline. The valid run caught 36, and the five survivors became tests. Tests ran on
generated media through the pinned library. No external footage or network-backed test was needed.

## Audit handoff

- `AUD-duplicate-frame-detection-1`: A remux inside one group counts a frame twice, which the
  specification forbids for one source. Nonblocking: it crosses no group. Owner:
  `group-repeated-frames`, added in this change, with the specification stating the limit.
- `AUD-duplicate-frame-detection-2`: `shared_frames.not_compared` is logged once and sealed nowhere,
  so a locked evaluation could call material unseen that no check compared. Nonblocking until a
  runner exists. Owner: `locked-split-guard`, amended in this change to report each one by name.
- `AUD-duplicate-frame-detection-3`: A re-encoded copy shares no frame hash, so it still crosses a
  split. Nonblocking: the task scoped it out. Owner: `near-duplicate-detection`, whose text states
  it.
- A copy cut to windows sharing no frame stays invisible. Dropped, needing no work: frame hashes
  cannot show it, and neither can a near-duplicate search over frames that do not exist in both.
  Grouping stays the operator's judgment, and the current page and the specification state it.
- A stream with fewer than eight different frames cannot hold a run. Dropped, needing no work: that
  is the named minimum, and the current page states it.
- Independent clips truly sharing eight different frames are refused with no override. Dropped,
  needing no work: no such case has been observed, and `selection` is the way past one. The current
  page states it.
- A remux in an unlinked version or sibling branch is not compared. Dropped, needing no work:
  `unlinked-version-report` lists only source hashes by its own scope, and the specification says
  independent work may reuse a recording.
- A rebuilt predecessor is found only after a stage has staged its streams. Dropped, needing no
  work: it refuses, the streams stay valid, and it needs no frame set.
- Reviewed malformed, removed, partial, rebuilt and foreign predecessors, stage order, and repeated
  stages. No additional work identified.

## Close or resume

All required gates passed. The current corpus page, its area index and the records index link this
record, and the specification and test plan are updated. Removed `duplicate-frame-detection`,
dropped it from the dependencies of `near-duplicate-detection`, which needed nothing further from
it, added `group-repeated-frames` and amended `locked-split-guard`. Remaining plan: 87 tasks (66
agent, 21 human); next agent is `arm64-reproducibility`, next human is
`select-development-workload`. `corpus-provenance` remains planned because its other tasks remain.
No service, port or external resource was started, and scratch evidence stayed outside the
repository.
