# Recording capture vocabulary

## Task and scope

- Id / capability: `recording-capture-vocabulary` / `corpus-provenance`
- State: accepted
- Source: plan task; start commit `89886a2`, clean worktree.
- Plan counts at start: 164 (136 agent, 28 human); next agent `recording-capture-vocabulary`, next human `define-locked-test-policy`.
- Accepted task:

```markdown
#### recording-capture-vocabulary

Recording declarations accept arbitrary control descriptions and lack observer platform. Closing
these vocabularies without an explicit successor path would strand retained source evidence.

- Serves: `corpus-provenance` -- [Capture compatibility](../design/spec.md#capture-vocabulary-and-historical-source-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: New sources declare closed capture values; an operator can migrate an old
  source explicitly while retaining its exact original record and all source bytes.
- Scope boundary: Control values are `operator_steered`, `fixed_camera`, `autonomous_camera`,
  `unknown`; platform values are `ground_fixed`, `ground_handheld`, `airborne`, `unknown`.
  Omission in a new declaration means unknown. Historical values are never mapped by guesswork.
  Only explicit capture amendment may replace these two judgments; other capture facts stay put.
- Data and artifact paths: `contracts/declaration/recording/`, `contracts/record/source-manifest/`,
  `src/ss_track/corpus/declarations/`, `src/ss_track/corpus/sources/`, `tests/corpus/`,
  `docs/impl/workloads/`, existing imported-source and retained-record paths under `$DATA_DIR`.
- Execution path: Freeze major 3 contracts with the previous major's `facts` disposition and a
  tested migration remedy. Protect both judgment properties in the compatibility gate. Add
  `import --amend-capture` through the shared source replacement transaction, composing with
  `--amend-terms` and `--redecode` when needed. Update declaration producers and workload YAML;
  restate only supported facts, using unknown otherwise. Keep all historical fixtures unchanged.
- Acceptance gates: Invalid values name the field. Every historical source major has a tested
  inspection and migration/refusal path. A successful migration preserves source identity, media,
  other capture facts, terms and decoded facts unless their explicit operation is also requested.
  Old records retain bytes and seals; repeated amendments are unchanged; interrupted publication
  loses no record. Pinned versions refuse and are listed; a successor builds with the same groups
  and splits. Metadata-only migration needs no media, and incomplete combined migrations publish
  nothing and name the missing operations. No new reproducible artifact kind is introduced.
  Frozen contracts and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).
```

## Implementation

Frozen recording and source-manifest major 3 use closed camera-control and observer-platform
judgments; omission becomes `unknown`. Both fields are protected from view migrations. The
`--amend-capture` operation composes with terms and redecode through the existing source lock,
preflights missing operations, preserves other facts and lists pinned versions. Replaced records
are copied atomically as their exact original bytes. Historical declarations and retained fixtures
are unchanged. The selected aerial workload states `airborne`; the pool declaration producer uses
the new major and leaves unknown judgments omitted. See [Corpus](../current/corpus.md).

The public Python amendment function retains its existing defaults and gains optional keyword-only
capture and terms switches; redecode gains a capture switch. No dependency, environment variable,
or data artifact kind was added.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Closed values, historical inspection, byte retention, missing operations, repeat, pinned versions and successor | `tests/corpus/sources/test_capture_amendment.py`, `tests/corpus/records/test_source_inspection.py` | pass; deterministic local fixtures, no network |
| Major 1 migration, combined operations, interrupted publication | `tests/corpus/sources/test_amend_records.py`, `tests/corpus/sources/test_redecode.py`, `tests/corpus/records/test_historic_commands.py` | pass; real retained major 1 and 2 records and simulated interruption |
| Compatibility floor and frozen contracts | `tests/schema/compatibility/test_dispositions.py`; `make lint-contracts` | pass; both capture judgments require `facts` |
| Required project gate | `make ci` | pass; format, lint, typing, complexity, shell, links, plan integrity, contracts and local tests |
| Reproducible artifacts | Source changes and data-root registry review | pass; no new reproducible artifact kind |

## Audit handoff

None identified. Reviewed historical source dispositions, atomic publication, declaration producers,
impact reporting, dependency updates and current documentation; the separately planned encounter
counts and image-sequence import remain outside this task.

## Close or resume

All acceptance gates passed. Updated the corpus current page and records index, removed the completed
task and its dependencies from the plan, and retained `corpus-provenance` as shipped. Plan counts
after: 163 tasks (135 agent, 28 human); next agent `capture-encounter-counts`, next human
`define-locked-test-policy`.
