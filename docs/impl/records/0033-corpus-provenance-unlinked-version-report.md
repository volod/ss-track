# Unlinked version report

## Task and scope

- Id / capability: `unlinked-version-report` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `f571884`; clean worktree.
- Plan counts at start: 131 tasks (109 agent, 22 human). Next agent:
  `unlinked-version-report (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### unlinked-version-report (optional)

A version that names no predecessor, or branches from one, can place an evaluated source in another
split, and its build says only that it has no lineage.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus build` lists every other built version on its data root that places
  one of its sources in another group or split, for an operator's decision.
- Scope boundary: A report that refuses nothing, because independent work may reuse a recording.
  Source hashes on one data root only. Versions in the declared chain stay with the refusal.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/`.
- Execution path: Scan `$DATA_DIR/corpus/*/manifest.json` and reuse the placement comparison in
  `lineage.py`, reading every major through `read_comparable` and its projection, and naming a
  manifest it cannot read, or one whose major keeps no projection, rather than skipping it.
- Acceptance gates: A source placed in `locked` by an unlinked version and by a sibling branch are
  each listed with both versions, and both builds succeed. One state gives one listing in one order,
  and a version in the declared chain is never listed.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus build` now adds `unlinked` to its result when another version on the same data root places
one of its sources in another group or split, or when a corpus manifest there cannot be compared.
The build still succeeds. `from` is the other version and `to` is the one being built, the same
shape as a split-leakage move. The field is absent when there is nothing to report, and it is not
sealed, so a later version on the data root does not change a corpus hash. An `unchanged` rebuild
reports the data root as it is.

`sources_placed_elsewhere` in `lineage.py` is the one comparison. The declared-chain refusal still
keeps only the nearest version of each source. The report keeps every other version.
`scan_corpus_manifests` in `unlinked.py` reads `$DATA_DIR/corpus/*/manifest.json` through
`read_comparable`. A manifest that cannot be read is `unreadable`. A major with no projection is
`other_schema`. A major that has one, including corpus schema 2, is compared. The version being
built and every declared predecessor are left out, so an unprojected predecessor stays in
`lineage.not_compared` and is not listed again. The name is the directory under `corpus/`.

Placements are ordered by source hash, then by that directory name. Manifests that were not
compared are ordered by directory name. The command result contract gained minor `1.6.0` for the
optional field. No manifest schema, refusal code, environment variable, `pyproject.toml`, or
`uv.lock` change. `amendment-impact-report` now names `scan_corpus_manifests` as its walk. Current
page: [version lineage](../current/corpus.md#version-lineage).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A source placed in `locked` by an unlinked version is listed with both versions, and the build succeeds | `tests/corpus/versions/test_unlinked_versions.py::test_an_unlinked_version_placing_a_source_in_locked_is_listed_and_builds` | pass; lineage stays `no_lineage` |
| A source placed in `locked` by a sibling branch is listed with both versions, and the build succeeds | `test_a_sibling_branch_placing_a_source_in_locked_is_listed_and_builds` | pass; the shared parent is not listed |
| One state gives one listing in one order | `test_one_state_lists_every_displaced_source_in_one_order` | pass; two sources and two versions, ordered by hash then directory name |
| A version in the declared chain is never listed | `test_a_version_in_the_declared_chain_is_never_listed`, `tests/corpus/versions/test_unlinked_scan.py::test_an_unprojected_predecessor_stays_on_lineage_and_is_not_listed` | pass; a same-place predecessor is omitted, and an unprojected one stays on `lineage` only |
| An independent reuse is not refused | `test_the_same_placement_and_another_groups_new_source_are_not_listed` | pass; the same place is not listed, and a new source in another version's group is not listed |
| A manifest that cannot be read, or whose major keeps no projection, is named | `test_an_unreadable_manifest_is_named_and_the_build_succeeds`, `test_a_major_with_no_projection_is_named_and_not_compared`, `test_a_projected_older_major_is_compared` | pass; bad JSON, a broken seal, an incomplete record, an unreadable file, schema 1 and 4, and schema 2 is compared |
| The listing is not sealed, and a repeat matches | `test_the_listing_is_not_sealed_and_a_repeat_matches` | pass; manifest bytes stay equal while the second result lists the new neighbor |
| The command exits 0 and the result matches the contract | `test_the_command_lists_a_displaced_source_and_an_unreadable_manifest` | pass, through `main`; the suite validates the logged result against `result/command` 1.6.0 |
| A declared move is still refused | `tests/corpus/versions/test_lineage_leakage.py` | pass |
| Required gate | `make ci` | pass: 1687 tests, format, lint, typing, complexity, shell, links, plan and contracts |

## Audit handoff

- `AUD-corpus-version-lineage-2` and `AUD-record-version-refusal-1` asked for this listing. Fixed in
  this change: a build names the other version and still succeeds. Dropped, because the report now
  exists.
- A remux in an unlinked version still shares no comparison of frame hashes. Dropped, needing no
  work: this listing is source hashes, as the specification says, and the current page states that
  the frame check does not read that version.
- The listing is not sealed, so a later locked evaluation does not replay it. Dropped, needing no
  work: `locked-split-guard` already requires the no-lineage statement, and repeating `corpus build`
  reports the data root as it is. The specification says the listing is not sealed.
- Versions on another data root are not listed. Dropped, needing no work: the task and the
  specification limit the scan to one data root.
- A group's split is not applied to an undeclared version that holds different sources. Dropped,
  needing no work: the specification limits the listing to source hashes. The declared chain still
  refuses a group that changes split.
- `docs/impl/current/contracts.md` omitted `result/command` 1.5.0. Fixed in this change. Dropped as
  a chore: the inventory now lists 1.5.0 and 1.6.0.

## Close or resume

All gates passed. The current corpus page states the listing, its order, what it does not compare,
and that it is not sealed, and links this record. The plan task is removed.
`amendment-impact-report` now names `scan_corpus_manifests`. Plan counts after: 130 tasks (108
agent, 22 human); next agent is `amendment-impact-report (optional)`, next human is
`select-development-workload`. `corpus-provenance` stays planned because its other tasks remain.
No service, port or external resource was started.
