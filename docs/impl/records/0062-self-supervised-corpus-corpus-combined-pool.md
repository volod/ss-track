# corpus-combined-pool

## Task and scope

- Id / capability: `corpus-combined-pool` / `self-supervised-corpus`
- State: accepted
- Source: plan task, start commit `805e568`; working tree clean.
- Plan counts at start: 105 agent, 23 human; next agent `corpus-combined-pool`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-combined-pool

Combining recordings needs a reproducible pool that preserves independent source and split boundaries.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A combined corpus can be prepared, audited and reused for future cases while
  tracing each recording to its collection, terms and upstream metadata.
- Scope boundary: Fixture preparation and existing import, build, stage and link review; no real
  source acquisition, automatic split adjudication, new label authority or locked access.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `contracts/`,
  `$DATA_DIR/import/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Map approved source selections into existing recording and corpus declarations;
  preserve original video, collection and upstream split identity and separate annotation evidence.
  Group related and duplicate footage across sources before assigning splits, expose unresolved
  links, and retain rights and source-specific accounting in later versions and cases. Acquisition
  stores selected Hugging Face metadata files but does not associate or parse their YAML and source
  links per video. Inspect fixture metadata and join only evidenced matches; report missing or
  conflicting associations, which otherwise obscure source attribution and rights evidence.
- Acceptance gates: Network-free two-source fixtures build, stage, verify and replay; source and
  license lineage survive, per-video metadata associations and mismatches are reproduced from
  pinned metadata and unresolved associations remain visible, duplicates cannot cross splits, and
  missing origin or terms refuses rather than fabricates facts; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

`ss-track discover pool` reads a `declaration/corpus-pool` 1.0.0 selection and writes recording
declarations, a corpus declaration and sealed `record/corpus-pool` 1.0.0 under
`$DATA_DIR/self-supervised-corpus/<run-id>/`. Import, build, stage, verify and link review stay the
existing commands. Link review uses its own run id. The command result reuses `status`, `run_id`,
`corpus_id`, `manifest_path` and `manifest_sha256`, so `result/command` is unchanged.

`declaration/recording` 2.4.0 and `record/source-manifest` 2.4.0 add optional `origin`. An import
omits it when the declaration has none. An amendment that adds or drops it is `IMPORT_CONFLICT`.
Public descriptors omit origin because the source-manifest field is sensitive.

The pool joins YAML, CSV and source-link files by an exact path, a unique sibling stem, or a source
line that names the path or that video's source reference. A license stays on the origin. Rights
and sensitivity are copied from the operator's declaration. The same bytes become one recording,
with one origin entry per collection. An upstream `test`, `test_set` or `locked` split withholds
that video and footage that shares its bytes or source. `account_corpus` counts later streams and
cases from the imported origin. YAML goes through `parse_unique_document` in `core/strict_yaml.py`.
A repeated key stays unresolved.

Current behavior is in [Corpus](../current/corpus.md) and [Contracts](../current/contracts.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Two-source prepare, stage, verify, replay, lineage and later-case accounting | `tests/corpus/sources/test_pool.py` | pass, inside `make ci`; fixtures only |
| Exact joins, unresolved names, secrets, query URLs and a repeated YAML key | `tests/corpus/sources/test_metadata_join.py` | pass, inside `make ci` |
| Missing terms, split leakage, rights conflict, a changed declaration and related withhold | `tests/corpus/sources/test_pool_refusals.py` | pass, inside `make ci` |
| An amendment keeps origin and cannot add or drop it | `tests/corpus/sources/test_amend_refusals.py` | pass, inside `make ci` |
| `make ci` | `make ci` | pass: 2230 passed, 112 deselected. Format, lint, typing, complexity, shell lint, doc links, spec-plan and contracts reported no findings |

## Audit handoff

- Fixed in this change: `AUD-corpus-source-acquisition-1`. Acquired YAML, CSV and source-link files
  are joined by the pool. The closed acquisition record still names this task; that record is
  history.
- Dropped: a published Drone Detection CSV `name` such as `no_drone/birds_only/rgb/1` does not equal
  a path under `videos/no_drone_footage/`. Exact join leaves it unresolved, as
  [Corpus](../current/corpus.md) states. A fuzzy match would invent an association.
- Dropped: `pool_group.py` is 254 lines. The grouping rules belong in one module.
- Dropped: no ss-video or ss-fusion change. The pool writes ordinary ss-track recording and corpus
  declarations and calls no sibling interface.

## Close or resume

All acceptance gates passed. The task is removed from the plan. `corpus-blinded-audit-review`,
`corpus-evaluation-by-source`, `corpus-two-source-pilot` and `corpus-wetland-evidence` no longer
depend on it. The plan has 127 tasks: 104 agent and 23 human. The next agent task is
`corpus-blinded-audit-review` and the next human task is `define-locked-test-policy (optional)`.
`self-supervised-corpus` remains planned.
