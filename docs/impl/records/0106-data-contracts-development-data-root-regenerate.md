# Task Record

development-data-root-regenerate

## Task and scope

- Id / capability: `development-data-root-regenerate` / `data-contracts`
- State: accepted
- Source: plan task, added by `development-portable-handoff-provenance` in the same uncommitted
  change on top of `2db0c29`; the owner authorized the re-acquisition ("run it now").
- Plan counts at start: 128 agent, 31 human; next agent `development-explicit-path-revision-root`,
  next human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-data-root-regenerate

The development data root `$DATA_DIR` holds a structure-only `contract-set.json` written before
meaning fingerprints were required, so every root-checking command on it refuses
`RECORD_SCHEMA_UNSUPPORTED` with `unverified_contracts`; since the in-place edit of
`record/link-review-handoff`, `changed_contracts` also names that contract. Reproduce:
`.venv/bin/ss-track corpus verify --corpus hawk-drone-pilot-v1`. Expected: the hawk workload, the
two-source pilot corpora, discovery runs, link reviews and freezes verify under the current set.
Regeneration re-acquires the pilot sources, which counts against the owner's transfer cap stated in
the [two-source recipe](workloads/two-source-pilot/README.md).

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: HUMAN-GATED
- Dependencies: the owner's authorization of the re-acquisition transfer.
- User-visible outcome: The development data root is stamped with structure and meaning
  fingerprints and every pilot dataset verifies under the installed contract set.
- Scope boundary: Delete and rebuild sealed development datasets only. Keep operator-written
  declarations, labels, reviews and link decisions, `cache/`, `uv-cache/` and
  `preserved-operator-inputs-pre-baseline/`. Change no code or contract.
- Data and artifact paths: `$DATA_DIR/`, `docs/impl/workloads/two-source-pilot/`.
- Execution path: After authorization, move the sealed datasets and the stamp out of the root,
  rebuild with `make development-workload-prepare`, the hawk commands and the two-source recipe, then
  verify each corpus and discovery run; update the recipe's seal table where seals change.
- Acceptance gates: `corpus verify` of `hawk-drone-pilot-v1`, `pilot-two-source-grouped-20261113`,
  `pilot-frozen-diverse-20261113` and `pilot-frozen-uniform-20261113` and `discover verify` of both
  runs exit 0; `contract-set.json` holds meaning fingerprints; every retained operator input is
  still present.
- Documentation target: [Contracts](current/contracts.md) and the [two-source
  recipe](workloads/two-source-pilot/README.md).
```

- Amendments: none.

## Implementation

No code or contract changed. The sealed datasets and the structure-only `contract-set.json` were
moved from `$DATA_DIR` to a sibling directory on the same filesystem, keeping `cache/`,
`uv-cache/`, `workload-selection/` (the pinned hawk source and its declarations, no sealed record)
and `preserved-operator-inputs-pre-baseline/`. Every YAML, CSV and text file among the moved
datasets was generated or downloaded; the operator-written inputs are the repository's
`docs/impl/workloads/` files. The root was rebuilt with `make development-workload-prepare` and the
hawk commands of the [Corpus](../current/corpus.md) page, then the
[two-source recipe](../workloads/two-source-pilot/README.md) end to end with the cached
ss-perception GPU environment and `TORCH_HOME`.

The Zenodo archive was not downloaded again: `provider_http.download` verifies an existing target
by size and published MD5, so the verified `cache/source.zip` was hard-linked into the new
acquisition run. Only the Hugging Face videos and metadata were fetched, a small part of the
recipe's transfer. The recipe now says a host may reuse such an archive.

A power loss stopped the first rebuild during the diverse discovery run. Nothing had been written
after that step began except its lock file; the run publishes nothing until it finishes. Before
resuming, every sealed record's seal, every imported source and acquired file hash, the stamp and
both staged corpora (`corpus verify`) were checked, then the recipe resumed at its discovery runs.

Finding: the rebuilt root holds the same 939 sealed records with the same seals as the stale one;
only the stamp differs, now with meaning fingerprints. No record's bytes depended on the contract
edits that made the old stamp unverifiable. After that comparison the stale copy was deleted, as
authorized.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| `corpus verify` of the four corpora and `discover verify` of both runs exit 0 | Final verify loop of the rebuild: `hawk-drone-pilot-v1`, `pilot-two-source-grouped-20261113`, `pilot-frozen-diverse-20261113`, `pilot-frozen-uniform-20261113`, `pilot-diverse-grouped-20261113`, `pilot-uniform-grouped-20261113` | pass: all `verified`, no refusal in any step |
| Identities match the recipe | Seals of the three acquisitions, pool, corpus manifest, frame set, both runs (`cuda`, batch 64), links and both `freeze.json` | pass: all twelve equal the recipe's table, so the table is unchanged |
| `contract-set.json` holds meaning fingerprints | `$DATA_DIR/contract-set.json` | pass: 19 structure and 19 meaning pins, equal to the installed set |
| Integrity after the power loss | A one-off check of seals, `import/<sha>/source.*` hashes and acquisition `local_path` hashes, then `corpus verify` of both surviving corpora | pass: 86 records, 38 imports, 45 acquired files before resuming; 939 records, 0 problems at the end |
| Every retained operator input is still present | `docs/impl/workloads/` unchanged in Git; `preserved-operator-inputs-pre-baseline/` and `workload-selection/` kept in place | pass |
| Regeneration reproduces the data | Seal comparison of every sealed record, stale against rebuilt | pass: 939 of 939 identical, none missing or added |

## Audit handoff

Reviewed: the moved and kept paths, the cache reuse, the power-loss window and the rebuilt root.
`none identified`. Dropped observations: a read-only staged frame tree needs `chmod -R u+w` before
an operator can delete a copy outside `data clean`, which is the intended protection, so no work is
needed. The lock file left by the interrupted run is an empty `flock` target that the next run reused.

## Close or resume

Every gate passed. The task has left the plan; the two-source recipe states the archive reuse.
Plan counts after: 128 agent, 30 human; next agent `development-explicit-path-revision-root`, next
human `define-locked-test-policy` (optional). `data-contracts` stays `planned`.
