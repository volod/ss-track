# Near-duplicate detection

## Task and scope

- Id / capability: `near-duplicate-detection` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `fb348ba13df3127e001958202f894bec4bf00351`; clean worktree.
- Plan counts at start: 131 open (108 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=102, HUMAN-GATED=13, RUN NEEDED=6. Next agent `near-duplicate-detection (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### near-duplicate-detection (optional)

A re-encoded copy of a recording shares no bytes or frame hashes, so it can still cross a split.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: RUN NEEDED
- Research: yes
- Milestone: M2
- Dependencies: none.
- User-visible outcome: A corpus build reports likely near-duplicates across groups for an
  operator's decision.
- Scope boundary: A perceptual comparison at a measured threshold. It reports and does not refuse
  until its false-match rate is known.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Compare a small perceptual fingerprint on re-encoded fixtures across codecs and
  bitrates, in a declared run over the development corpus.
- Acceptance gates: The threshold states measured recall and false-match rate. If no threshold
  separates copies from independent clips, that negative result is recorded and grouping stays
  manual.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus build` reports a likely re-encode that crosses encounter groups and refuses nothing. The
report is not sealed. `src/ss_track/corpus/versions/fingerprint.py` owns method `luma-grid-16`:
16 samples spread through the window, each a 16 by 16 box average of luma, compared by normalized
correlation. The threshold is 0.90. A flat window and two windows with different sample counts
score 0. `near_duplicates.py` builds the report. `near_duplicate_samples.py` decodes each source
once and stops after the last sample. `builder.py` attaches the report after the stream records
and before the seal.

The comparison covers the version being built and the predecessors the declaration links. A
predecessor whose manifest cannot be read is `window_unknown` when one of its groups is not a
group of this version, and is omitted when every group matches. An unprojected predecessor is
`other_schema`. A missing source or a window that cannot be decoded is `source_unreadable`.

`result/command` 1.12.0 adds optional `near_duplicates`, present only when a pair or a gap is
reported. No new dependency, environment variable or command flag.

The threshold comes from a measurement on 2026-11-06 with PyAV 19.0.2 (FFmpeg libraries 9.0.2).
Normalized correlation of the 16 by 16 grids separated the hawk windows: copies stayed at or above
0.969 and independent windows at or below 0.733. An 8 by 8 difference hash also separated those
windows, and lost the gap on a synthetic clip split in half, so the product keeps the correlation.
The summary is `$DATA_DIR/near-duplicates/luma-grid-16/summary.json`. Current page:
[Near-duplicates](../current/corpus.md#near-duplicates). Specification section 4.1 states the
report.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Threshold recall and false-match rate | `$DATA_DIR/near-duplicates/luma-grid-16/summary.json`, measured 2026-11-06 | pass; recall 84/90, false-match rate 0 on 36 independent pairs. Hawk copies stayed at or above 0.969 and independent windows at or below 0.733. Six misses are heavy quantization of high-frequency noise |
| A re-encode across groups is reported and does not refuse | `tests/corpus/versions/test_near_duplicates.py` | pass; the build stands, the corpus manifest has no `near_duplicates` field, and the command record carries the pair |
| An independent pair, the same group, a missing source and an unprojected predecessor | `tests/corpus/versions/test_near_duplicates.py` and `tests/corpus/versions/test_near_duplicate_report.py` | pass; an independent pair and the same group add no field, and a missing or unprojected predecessor is named |
| `make ci` | `make ci` | pass; 1882 tests |

## Audit handoff

`AUD-near-duplicate-detection-1`, nonblocking. A re-encode in a version the declaration does not
link is not read. Evidence: `report_near_duplicates` takes the declared predecessor chain and no
other corpus directory. Impact: a copy placed in an unlinked version can still cross a split
without a report. Owner: `near-duplicates-outside-the-chain`, added in this change. Its text
states the unlinked version, both corpus ids, and that the report still does not refuse.

Dropped, each because it needs no work:

- A re-encode that stays in one group. The outcome is a report across groups, and section 4.1
  leaves that copy unnamed.
- Six of sixteen high-frequency noise copies fall below 0.90. The threshold states that recall.
  The next independent hawk pair reached 0.733, so a lower threshold would enter that range.
- Windows that share no frame, and a window of uniform frames, score 0. Section 4.1 states that
  neither is evidence of a copy.

## Close or resume

Gates passed. Current page, specification section 4.1, the capability evaluation, contracts page,
test plan, records index and the plan are updated.
Plan counts after: 131 open (108 agent, 23 human). Statuses: BLOCKED BY HUMAN=10, CLEAR=103,
HUMAN-GATED=13, RUN NEEDED=5. Next agent `bundle-reuse-across-versions (optional)`; next human
`define-locked-test-policy (optional)`. `corpus-provenance` stays `planned`.
