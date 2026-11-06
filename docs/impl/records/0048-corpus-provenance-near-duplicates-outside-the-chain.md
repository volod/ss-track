# Near-duplicates outside the chain

## Task and scope

- Id / capability: `near-duplicates-outside-the-chain` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `6c9a7577b36c6ef3f3d449bcc421bd6be25ccc93`; clean worktree.
- Plan counts at start: 130 open (107 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=102, HUMAN-GATED=13, RUN NEEDED=5. Next agent
  `near-duplicates-outside-the-chain (optional)`; next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### near-duplicates-outside-the-chain (optional)

A re-encoded copy in a corpus version the declaration does not link still crosses a split, and the
build report never reads that version.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: none.
- User-visible outcome: A corpus build also reports a likely re-encode that sits in a version on the
  same data root and outside the declared chain.
- Scope boundary: The same fingerprint and threshold. It still reports and does not refuse. It does
  not scan another data root, and it does not assign a group.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/`.
- Execution path: After the declared chain, compare the same fingerprint with every other built
  version on the data root whose group differs.
- Acceptance gates: An unlinked re-encode across groups is named, with both corpus ids. An unlinked
  independent clip is not. A missing or unreadable version is named rather than skipped. The corpus
  hash is unchanged.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus build` still reports a likely re-encode and refuses nothing. After the declared chain,
`near_duplicate_scan.py` reads every other version directory on the same data root. A version whose
groups cannot meet another group is not fingerprinted. A match still assigns no group.

The report stays off the sealed manifest, so the corpus hash does not change when another version
is present. `result/command` 1.14.0 adds reason `unreadable` and optional `scan`. A missing
manifest, an unreadable manifest, and a version directory that cannot be read are `unreadable`.
A major with no projection is `other_schema`. A missing source is `source_unreadable`. When the
corpus directory cannot be listed, `scan` is `unreadable` and the declared chain is still compared.

The same `luma-grid-16` fingerprint and threshold 0.90 are unchanged. The frame window is part of
the corpus comparison projection, so a retired major that still carries one, corpus major 2
included, is compared instead of being named `window_unknown`. A fourth record reader was rejected:
comparison stays on the projection, and the read path stays three entries. The source-hash listing
does not name a directory that has no manifest; this report does. No new dependency, environment
variable, or command flag.
Current page: [Near-duplicates](../current/corpus.md#near-duplicates).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| An unlinked re-encode is named with both corpus ids, and the corpus hash is unchanged | `tests/corpus/versions/test_near_duplicate_outside.py::test_an_unlinked_re_encode_is_named_and_the_corpus_hash_is_unchanged` | pass; the sealed manifest has no `near_duplicates` field and the second build is `unchanged` |
| An unlinked independent clip is not reported | `tests/corpus/versions/test_near_duplicate_outside.py::test_an_unlinked_independent_clip_is_not_reported` | pass; the field is absent |
| A missing or unreadable version is named, and the build stands | `tests/corpus/versions/test_near_duplicate_outside_gaps.py::test_a_missing_and_an_unreadable_version_are_named` and `test_an_unreadable_corpus_directory_is_named_and_the_build_stands` | pass; a missing manifest, a broken manifest, and a directory that cannot be read are `unreadable`; an unlistable corpus directory is `scan` `unreadable` |
| `make ci` | `make ci` | pass; 1908 passed, 4 warnings |

## Audit handoff

`none identified`. Reviewed the near-duplicate report, the outside-chain scan, the shared version
walk, and the build path that calls them. A match is not sealed and does not refuse. The scan does
not leave the data root and does not assign a group.

Dropped, each because it needs no work:

- A re-encode that stays in one group. Section 4.1 leaves that copy unnamed.
- A version on another data root. The task bounds the scan to one data root.
- Windows that share no frame, and a window of uniform frames. Section 4.1 states that neither is
  evidence of a copy.
- Six of sixteen high-frequency noise copies fall below 0.90. The measured threshold already states
  that recall.
- A directory under `corpus/` with no manifest is `unreadable` here and is still absent from the
  source-hash listing. That is the missing-version report, and the listing's own rule is unchanged.

## Close or resume

Gates passed. Current page, specification section 4.1, the capability evaluation, contracts page,
test plan, records index, and the plan are updated. Plan counts after: 129 open (106 agent, 23
human). Statuses: BLOCKED BY HUMAN=10, CLEAR=101, HUMAN-GATED=13, RUN NEEDED=5. Next agent
`corpus-provenance-audit (optional)`; next human `define-locked-test-policy (optional)`.
`corpus-provenance` stays `planned`.
