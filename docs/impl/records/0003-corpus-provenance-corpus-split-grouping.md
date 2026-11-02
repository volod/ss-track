# Corpus split grouping

## Task and scope

- Id / capability: `corpus-split-grouping` / `corpus-provenance`
- State: accepted
- Source: plan task at `294535c` on branch `st-corpus-provenance`. The working tree was clean.
- Plan counts at start: 71 open (51 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=47`,
  `HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `corpus-split-grouping` and
  `select-development-workload`.
- Accepted task:

```markdown
#### corpus-split-grouping

Related frames must stay together, or evaluation leaks across splits.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Corpus versions keep each encounter intact across development, calibration
  and locked splits, including every stream of a multi-stream encounter.
- Scope boundary: Grouping, split membership, stream identity and scenario rights. A locked test and
  near-duplicate detection are out of scope.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add encounter and stream records and split rules with deterministic fixtures.
- Acceptance gates: Fixtures prove no encounter or stream crosses a split. A rights conflict refuses
  the corpus build.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none to the task text. The corpus declaration moved to schema 2, spec section 4.1
  gained the structure and scenario rights semantics, and the test plan lists this case as existing
  behavior.

## Implementation

`ss-track corpus build` now reads groups, encounters, streams and scenario rights, and refuses
leakage, overlap and rights conflicts. `src/ss_track/cli.py` is unchanged apart from the result it
reports. Behavior is in `src/ss_track/corpus/`:

- `grouping.py` (new): membership, source separation, scenario rights and split counts.
- `declaration.py`: the group, encounter, stream and scenario rights declarations.
- `builder.py`: flat stream records with their membership, and `require_source_record`.
- `staging.py`: the pinned source record is checked first, and a bundle must belong to its stream.
- `sealed.py`: `require_schema`, used for corpus manifests and frame bundles.

Reused rather than repeated: `Fields` reads every new key strictly, `IDENTIFIER_PATTERN` covers the
new identifiers, and `sealed.py` still owns hashing and records.

Decisions and rejected alternatives:

- **Group is a level of its own:** the spec splits by independent encounter group, and two encounters
  of one session are not independent. Treating an encounter as the group was rejected: an operator
  could then only keep such encounters together by merging them.
- **A split is stated once, on the group:** an encounter or stream that names its own split can
  disagree with its siblings, so that form is not offered. What remains possible is a repeated
  identifier or a reused source, and those are the refusals.
- **`stream_id` replaces `sequence_id` (`AUD-frame-bundle-staging-6`):** one sequence is exactly one
  stream's frames, so keeping both names would give one thing two identifiers. It is unique in the
  corpus rather than local to an encounter, so one string identifies a stream in a path, a label or a
  `FrameRef`. The audit item ends here.
- **Flat `streams` in the manifest:** each record carries its membership, which is one filter for a
  later consumer and leaves staging almost unchanged. A nested manifest was rejected as more code in
  every reader for no gain, since the seal already covers the record.
- **A rights conflict is a scenario asking too much:** source rights are one fixed declaration per
  source, so they cannot disagree with themselves. Refusing any encounter with mixed sharing was
  rejected: it would block valid recordings when the corpus is restricted anyway.
- **`modality` is recorded, not declared:** import accepts only video, so a declared value could only
  be `camera` or false. A scenario list of permitted modalities would be dead code today.
- **The source-window rule covers the whole corpus:** it catches a frame in two streams of one
  encounter as well as across encounters, with one rule.
- **The policy check left `write_bundle`:** the corpus now pins the source record, the build checked
  that record's policy and `corpus stage` checks the corpus policy, so the check could not fire.
- **No exact-frame comparison at staging:** it would catch a remux, but two independent clips can
  share a black frame, and handling that is the near-duplicate detection the task puts out of scope.

Findings from running real media through the CLI, each with a regression test:

| Finding | Regression test |
| --- | --- |
| Swapping a development and a calibration bundle passed `corpus verify` and `corpus stage`, exit 0, because a bundle was only checked against its corpus | `test_a_bundle_moved_to_another_stream_cannot_cross_a_split` |
| A source re-imported as `restricted` after a `public` corpus was built staged without complaint | `test_staging_refuses_a_source_whose_rights_changed_after_the_build`, `test_repeating_a_stage_notices_rights_that_changed_after_staging` |
| An old corpus manifest would reach staging and fail on a missing key; the schema check was added before the first run and confirmed through the CLI | `test_a_corpus_from_another_schema_is_refused_by_name`, `test_a_bundle_from_another_schema_is_refused_by_name` |
| Windows declared against stream-id order had no test, shown by a surviving mutant | `test_adjacent_windows_share_no_frame[names-oppose-frames]` |

Compatibility: `corpus.yaml` is schema 2, so a schema 1 declaration is `MANIFEST_INVALID`. Corpus
manifests and frame bundles are schema 2, and a schema 1 record is `RECORD_SCHEMA_UNSUPPORTED`; such
a corpus must be rebuilt under a new `corpus_id`. Source manifests and `recording.yaml` are
unchanged, so sources need no re-import. In records and refusals `sequence_id` is now `stream_id`,
`sequence_count` is `stream_count`, and a result adds `splits`. Decode policy, `pyproject.toml` and
`uv.lock` are unchanged. `SOURCE_RECORD_CHANGED`, `SPLIT_LEAKAGE`, `STREAM_OVERLAP`,
`RIGHTS_CONFLICT` and `RECORD_SCHEMA_UNSUPPORTED` are new.

Limitations:

- Sources are compared by byte hash, so a remux or re-encoded copy passes as a different source.
- `locked` is a membership label. It restricts no access and supports no held-out claim.
- Nothing compares corpus versions, so a later version can move a source between splits.
- `holder`, `basis` and `retention` are never compared, and retention is free text.
- Streams of one encounter carry no clock relation.
- `corpus verify` does not read source records, so only `corpus stage` notices changed rights.

Current-state page: [Corpus](../current/corpus.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| No encounter crosses a split | `test_an_encounter_cannot_cross_a_split` | pass, for each of the three split pairs |
| No stream crosses a split | `test_a_stream_cannot_cross_a_split`, `test_a_recording_cannot_reach_two_splits_under_two_names`, `test_a_bundle_moved_to_another_stream_cannot_cross_a_split` | pass, by identifier, by source and for staged frames. Limit: identical bytes only, see the remux row below |
| A rights conflict refuses the corpus build | `test_a_public_scenario_refuses_a_restricted_stream_of_a_two_stream_encounter`, `test_a_source_more_sensitive_than_the_scenario_allows_is_refused`, `test_a_rights_conflict_is_a_structured_refusal_with_a_failing_status` | pass, no manifest written, exit 1 |
| Every stream of a multi-stream encounter stays together | `test_every_stream_of_an_encounter_inherits_its_group_and_split`, `test_each_stream_of_an_encounter_stages_its_own_bundle_and_frame_identity` | pass, from declaration to `FrameRef` |
| Deterministic fixtures | `test_declaration_order_at_every_level_does_not_change_the_corpus_hash` | pass |
| `make ci` | `make ci` | pass on Python 3.12, 332 tests |
| Fuller local gate | `make quality` | pass, coverage 98.51% |
| Second CI version | `pytest` in a locked Python 3.13 environment | pass, 332 tests, exit 0. Limit: tests only, not the lint gates |

The rest was a one-off investigation on the final code. Its scripts lived in session scratch space
and were not kept; the regression tests above are the lasting form.

| Investigation | Method | Result and limit |
| --- | --- | --- |
| Real encoders through the CLI | Four H.264 files from system `ffmpeg` in Matroska and MP4, built into two splits with a two-stream encounter and two encounters cut from one recording | Built, staged and verified, five bundles. Each refusal exited 1 and wrote no manifest |
| Bundle swap, before and after | A development bundle exchanged with a calibration bundle | Exit 0 before the fix, `BUNDLE_CONFLICT` after, and `verified` again once restored |
| Rights withdrawn, before and after | Import directory removed and the source re-imported as `restricted` under a `public` corpus | Staged before the fix, `SOURCE_RECORD_CHANGED` after. It also blocks any other corpus that pins that record |
| Remuxed copy | `ffmpeg -c copy` from MP4 to Matroska, one copy in `development` and one in `locked` | Accepted: 100 of 100 frames identical across the splits. Documented limit, not a fix |
| YAML aliases | One encounter list reused under two groups by anchor | `SPLIT_LEAKAGE` |
| Old schema through the CLI | A sealed schema 1 corpus manifest, staged and verified | `RECORD_SCHEMA_UNSUPPORTED`, exit 1, no traceback |
| Reproducibility | One declaration built in two data roots by two processes | Identical manifest bytes |
| Rule cost | The source, rights and summary functions on 20000 synthetic streams | 18 ms. One host, no media involved |
| Test strength | 37 safeguards undone one at a time in a scratch copy, from a passing baseline, naming the test that failed | 36 failed a test. The run stopped at the first failure, so some were caught by a neighboring test rather than the one written for that rule. The survivor became the `names-oppose-frames` case and is now caught. A first run was discarded: every mutant had failed on one collection error, not on the mutation |

## Audit handoff

Every entry is nonblocking and has one owner. `AUD-frame-bundle-staging-6` is resolved above.

- `AUD-corpus-split-grouping-1`: a generated case has no source of its own, so `grouping.py` cannot
  see it. Evidence: its rules key on `source_sha256`. Impact: the next task must place each case in
  its parent's encounter and split explicitly, not as a new group. Owner: `generated-fixture-cases`.
- `AUD-corpus-split-grouping-2`: `corpus verify` passes after a source record changes. Evidence:
  `verify_corpus_frames` reads frames only. Impact: a run must not treat a verified corpus as one
  whose rights still hold, so a scenario should pin the source records. Owner: `scenario-contract`.
- `AUD-corpus-split-grouping-3`: a stream has no clock domain, calibration or raw-format fields, and
  `modality` is always `camera`. Evidence: spec section 4.1 lists them for multi-sensor encounters.
  Impact: membership in one encounter must never imply synchronization, and non-camera streams will
  need permitted modalities in scenario rights. Owner: `g2-scenario-observation-bundles`.
- `AUD-corpus-split-grouping-4`: a remux crosses a split undetected, and nothing compares corpus
  versions. Evidence: the remux investigation above. Impact: split isolation rests on the operator
  until near-duplicate detection and a locked test exist; spec section 4.1 adds the first when volume
  justifies it, and section 15 lists the inputs for the second. No plan task exists for either.
  Owner: capability `corpus-provenance`.

## Close or resume

Every declared gate passed; the commit is left to the project owner. The task left the plan, and four
dependents dropped it: `generated-fixture-cases`, `scenario-contract`,
`g2-scenario-observation-bundles` and `label-development-corpus`. [Corpus](../current/corpus.md) is
updated and its index entry extended, and this record is indexed in the
[records README](README.md). The spec gained the corpus structure and scenario rights, and the test
plan lists this case as existing behavior.

Plan counts after: 70 open (50 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=46`,
`HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `generated-fixture-cases` and
`select-development-workload`. Capability `corpus-provenance` stays `planned`.
