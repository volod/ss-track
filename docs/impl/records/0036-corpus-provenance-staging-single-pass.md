# Single-pass staging

## Task and scope

- Id / capability: `staging-single-pass` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `d20d0e2`; clean worktree.
- Plan counts at start: 128 open (106 agent, 22 human). Next agent
  `staging-single-pass (optional)`; next human `select-development-workload`.
- Accepted task:

```markdown
#### staging-single-pass (optional)

A long recording cut into many streams is decoded in full once per stream.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` decodes each source once, however many streams it feeds.
- Scope boundary: Fan-out of one strict decode. Seeking is out of scope, because the whole decode
  proves a source still matches its import.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Group pending streams by source and let one `inspect_media` consumer write several
  bundles.
- Acceptance gates: Bundle hashes match per-stream staging exactly, a failure leaves no partial
  bundle, and decode count equals source count on a multi-encounter fixture.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus stage` groups streams that have no bundle yet by `source_sha256`, in corpus order, and
decodes each such source once. `src/ss_track/corpus/bundles/staging.py` groups them.
`src/ss_track/corpus/bundles/bundle_writer.py` runs one `inspect_media` and fans frames out to every
pending selection. A frame outside those selections is decoded and not converted. Each stream keeps
its own converter and sees only its own frames, so the bytes match a stage of that stream alone. A
frame two selections both name is stored in each; a build already refuses that overlap.

`src/ss_track/corpus/bundles/publish.py` renames the scratch directories only after every manifest
of the pass is sealed. A failure or an interrupt while they are moving removes any directory that
pass already published. An earlier source stays staged. A repeated stage leaves a source unread
when every one of its streams is present. A reduced-precision or missing-matrix warning is logged
once for the source.

One stream's `DECODE_DRIFT` still names `stream_id`. Several streams name `stream_ids`, in corpus
order. No new dependency, refusal code, environment variable, manifest field, or command field.
Section 4.1 now states the one full decode. Current page:
[Frame bundles](../current/corpus.md#frame-bundles).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Bundle hashes match per-stream staging exactly | `tests/corpus/bundles/test_single_pass.py::test_encounters_of_one_source_share_one_decode_and_match_solo_bundles` and `test_distinct_sources_are_decoded_once_each_when_one_is_cut_apart` | pass; head/tail hashes, one head frame's bytes, and interleaved streams `a`/`b`/`c` match solo corpora |
| A failure leaves no partial bundle | `test_a_failed_frame_write_publishes_no_bundle_of_that_source`, `test_a_stopped_rename_removes_bundles_already_published_in_that_pass`, and `test_decode_drift_names_every_stream_of_the_pass_and_publishes_none` | pass; a failed frame write, a failed rename, and an interrupt publish none of that pass, and drift names `head` and `tail` |
| Decode count equals source count on a multi-encounter fixture | the two hash tests above, `test_a_source_finished_before_the_refusal_stays_staged`, and `test_replacing_one_missing_stream_decodes_that_source_once` | pass; two encounters of one source decode once, two sources decode twice, a repeat decodes nothing, and one missing stream decodes its source once |
| `make ci` | `make ci` | pass |

## Audit handoff

Reviewed the stage grouping, the single decode, publish and rollback, drift details, and the
current-page description of a pass.

Dropped, each because it needs no work:

- A kill the process cannot catch during the rename loop can leave a complete bundle of that pass.
  The current page says the next stage keeps it and decodes the source again only for streams that
  are still missing. The bundle is complete, and the next lock removes scratch.
- Free space is checked for one source's pending frames before that source is decoded, and an
  earlier source can already be published. The current page says so. This is the previous
  keep-finished-work rule, now per source rather than per stream.

## Close or resume

Gates passed. Current page, specification section 4.1, records index, and the plan are updated.
The task is removed from the plan. Plan counts after: 127 open (105 agent, 22 human). Next agent
`bundle-frame-sharing (optional)`; next human `select-development-workload`. `corpus-provenance`
stays planned.
