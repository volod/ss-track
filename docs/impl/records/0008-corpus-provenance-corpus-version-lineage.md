# Corpus version lineage

## Task and scope

- Id / capability: `corpus-version-lineage` / `corpus-provenance`
- State: accepted.
- Source: plan task; starting commit `bb82dda65b136cc278525a2ba52b532b15f1c629`; clean worktree.
- Plan counts at start: 88 tasks (67 agent, 21 human). Next agent: corpus-version-lineage;
  next human: select-development-workload.
- Accepted task:

```markdown
#### corpus-version-lineage

A later corpus version can move material that was already evaluated into a held-out split, and
nothing compares versions.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A corpus may declare the version it supersedes. A source moved to another
  split or group is refused, and the build result lists what was added, removed and kept.
- Scope boundary: Declared predecessors only, by source hash. A version that names none reports that
  it has no lineage. Near-duplicates are out of scope.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add an optional `supersedes` key to the corpus declaration, a pure comparison of
  two sealed manifests in `grouping.py`, and hand-built version pairs.
- Acceptance gates: A source moved from `development` to `locked` is `SPLIT_LEAKAGE`, naming both
  versions. Added sources build, and a missing predecessor is `CORPUS_NOT_BUILT`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`corpus build` now compares a version with the versions it declares it supersedes. The new optional
`supersedes` key names one version, and the sealed manifest stores
`supersedes: {corpus_id, manifest_sha256}`. A moved source or group is `SPLIT_LEAKAGE` naming every
move and both versions of each, and the build result always carries `lineage`: `linked` with
`added`, `removed`, `kept` and `compared_versions`, or `no_lineage`. `build_corpus` reads the chain
before it hashes any source, so a missing predecessor fails cheaply, and compares after the rules of
one version have passed. The [current corpus contract](../current/corpus.md#version-lineage) states
the behavior.

Three decisions go beyond the task's wording, all within its scope of declared predecessors by
source hash:

- The rules cover the whole declared chain. A comparison of two manifests alone can be walked around:
  a middle version drops a source and the next places it in `locked`, and each pair looks clean. The
  installed command refused exactly that case. `added`, `removed` and `kept` still read only the named
  version, as the task says, and `compared_versions` states what the rules read.
- A group keeps its split, even holding only new sources. A group's name claims its encounters are
  related, and no source hash can see a new recording from the same session. A name reused for
  unrelated material is refused with a fix an operator can apply, which beats a silent leak. Encounter
  names are not compared: unlike a group, nothing makes one the unit of independence across versions,
  and a false refusal on a reused counter-style name would have no reason behind it.
- The link pins a hash, not only a name. A predecessor rebuilt differently under its old name is
  `CORPUS_CONFLICT` when walked, and the pin also proves the chain ends: a loop would need a manifest
  to contain its own hash. `CORPUS_CONFLICT` already means that an id holds other content, so no new
  code was added.

The manifest stays schema 3 and the key is absent when nothing is named. A required `supersedes: null`
under schema 4 was rejected: it would change every existing hash and invalidate every staged bundle
to record a fact that its absence already states. No migration runs, and a corpus built by the code
at the starting commit rebuilds as `unchanged` under this code. `supersedes: null` in a declaration
is `MANIFEST_INVALID`, because absence is how a version says it names nothing.

The comparison lives in the new `src/ss_track/corpus/lineage.py`, not in `grouping.py` as the
execution path said. `grouping.py` rules read one version, and adding this would have taken it past
the size target with `duplicate-frame-detection` still to come. The module touches no disk: the
chain walk takes its loader as an argument, so `builder.py` keeps the one read path. `builder.py` is
286 lines and `tests/corpus/test_lineage_build.py` about 460, both above the approximate target; each
stays one cohesive unit. There is no change to environment variables, `pyproject.toml` or `uv.lock`.
The public result gains one key, and `BuildResult` gains a required `lineage` field.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A source moved from `development` to `locked` is `SPLIT_LEAKAGE`, naming both versions | `tests/corpus/test_lineage_build.py::test_a_source_moved_from_development_to_locked_is_leakage`, `test_a_refused_move_exits_one_with_the_code_in_its_record` | Pass, with exit 1 through `main`. Both versions are named in `details`, and the message names the new one |
| A source moved to another group is refused | `test_lineage.py::test_a_source_moved_to_another_group_in_one_split_is_refused` | Pass |
| Added sources build, and the result lists what was added, removed and kept | `test_added_sources_build_and_the_result_lists_every_change` | Pass, comparing the whole record |
| A missing predecessor is `CORPUS_NOT_BUILT` | `test_a_missing_predecessor_is_not_built_and_reads_no_source`, `test_a_missing_older_version_of_the_chain_is_not_built` | Pass, with the stored source deleted to show that no source is read first |
| A version that names none reports that it has no lineage | `test_a_version_naming_no_predecessor_says_so_and_stores_no_link`, `test_a_version_that_links_nothing_is_not_compared_with_anything` | Pass. The second pins the declared limit |
| Chain and pin behavior | `test_a_chain_refuses_a_source_dropped_by_the_version_between`, `test_a_source_may_come_back_to_the_place_it_left`, `test_a_rebuilt_predecessor_is_refused_when_its_successor_is_named` | Pass |
| Existing corpora keep their hash | One-off: `corpus build` from the starting commit's `src/`, then this code on one declaration | Pass: `unchanged` with an equal `manifest_sha256`. Script not kept |
| Installed command flow | One-off: `python -m ss_track.cli` import, build, stage and verify of real generated media across linked versions, with each refusal | Pass on the final code. Script not kept |
| Tests pin each check | One-off mutation of 20 faults in `lineage.py`, `builder.py` and `declaration.py`, on a scratch copy with bytecode writing off | First pass: 17 caught. The 3 survivors confused nearest and farthest versions of a chain, so two tests were added. Final pass: 20 caught. Script not kept |
| Required gate | `make ci` | Pass: 533 tests, formatting, lint, typing, complexity, shell, links and plan integrity |
| Full gate | `make quality` | Pass: coverage 98.83% against a 90% floor, Markdown lint and package build |

Tests ran on generated media through the pinned library. No external footage or network-backed test
was needed.

## Audit handoff

- `AUD-corpus-version-lineage-1`: Source hashes cannot see a remux, so a linked version can place a
  remuxed copy in `locked` and pass both this task and `duplicate-frame-detection` as it was written,
  because that task compared groups of one version only. Nonblocking: the task's scope is by source
  hash. Owner: `duplicate-frame-detection`, amended in this change, with the specification and test
  plan updated.
- `AUD-corpus-version-lineage-2`: A version that names no predecessor, or branches from one, is
  compared with nothing, as observed with the installed command: a source in `development` under one
  version built in `locked` under an unlinked one. Nonblocking: this is the declared boundary, and
  the result says `no_lineage`. Owner: `unlinked-version-report`, added in this change as an optional
  report, with the specification amended. It reports and does not refuse, because independent work may
  reuse a recording.
- `AUD-corpus-version-lineage-3`: A locked evaluation of a `no_lineage` version could imply unseen
  material that nothing showed to be unseen. Nonblocking until a locked evaluation exists. Owner:
  `locked-split-guard`, amended in this change.
- Removing a superseded version's `manifest.json` blocks later versions of its chain with
  `CORPUS_NOT_BUILT`. Dropped, needing no work: refusing is correct when history is gone, and an
  accumulated placement list in every manifest would add a second record of one fact. The current
  corpus contract tells operators to remove frames and keep the manifest.
- `corpus stage` and `corpus verify` do not read the chain. Dropped, needing no work: lineage is
  decided at build and sealed, no frame depends on a predecessor, and retention must stay able to
  remove material. `test_stage_and_verify_do_not_need_a_versions_predecessors` pins it.
- `kept` does not say that a source's frame window changed. Dropped, needing no work: a cohort pins the
  corpus version, so no comparison crosses versions on this list, and the manifests state each window.
- Reviewed malformed declarations, self-reference, repeat builds, replaced, damaged and other-schema
  predecessors, a re-imported source, and loops. No additional work identified.

## Close or resume

All required gates passed. The current corpus page, its area index and the records index link this
record, and the specification and test plan are updated. Removed `corpus-version-lineage`, which no
task depended on, amended `duplicate-frame-detection` and `locked-split-guard`, and added
`unlinked-version-report`. Remaining plan: 88 tasks (67 agent, 21 human); next agent is
`staged-frame-set`, next human is `select-development-workload`. `corpus-provenance` remains planned
because its other tasks remain. No service, port or external resource was started, and scratch
evidence stayed outside the repository.
