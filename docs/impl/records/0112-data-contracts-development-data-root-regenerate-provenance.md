# Task Record

development-data-root-regenerate-provenance

## Task and scope

- Id / capability: `development-data-root-regenerate-provenance` / `data-contracts`
- State: accepted
- Source: plan task, Human-Assisted lane; the owner authorized the transfer on 2026-11-18. Starting
  commit `f722275`, with the uncommitted change of `development-stamp-added-contracts` (record
  0111) in the working tree; this task changes no code or contract.
- Plan counts at start: 126 agent, 31 human; next agent `data-contracts-audit` (optional), next
  human `define-locked-test-policy` (optional).
- Accepted task:

```markdown
#### development-data-root-regenerate-provenance

The in-place edit that binds staged hashes to their contract set re-pinned `record/staged-hashes`,
`record/link-review-handoff` and `shared/types`, so every root-checking command on the development
data root `$DATA_DIR` now refuses `RECORD_SCHEMA_UNSUPPORTED` naming those three contracts.
Reproduce: `.venv/bin/ss-track corpus verify --corpus hawk-drone-pilot-v1`. Expected: the hawk
workload and the two-source pilot corpora, discovery runs, link reviews and freezes verify under the
installed set. The root holds one staged-hashes record and no handoff, so a rebuild should
reproduce every other seal. Regeneration downloads the pilot sources that the cache does not hold,
which counts against the owner's transfer cap stated in the [two-source
recipe](workloads/two-source-pilot/README.md).

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: HUMAN-GATED
- Dependencies: the owner's authorization of the transfer.
- User-visible outcome: `$DATA_DIR` is stamped under the installed contract set and every pilot
  dataset verifies again; its staged-hashes record carries contract pins.
- Scope boundary: Delete and rebuild sealed development datasets only. Keep operator-written
  declarations, labels, reviews and link decisions, `cache/`, `uv-cache/`,
  `workload-selection/` and `preserved-operator-inputs-pre-baseline/`. Change no code or contract.
- Data and artifact paths: `$DATA_DIR/`, `docs/impl/workloads/two-source-pilot/`.
- Execution path: After authorization, move the sealed datasets and the stamp out of the root,
  rebuild with `make development-workload-prepare`, the hawk commands and the two-source recipe,
  reusing a verified cached archive as the recipe allows, then verify each corpus and discovery run
  and compare every rebuilt seal with the moved copy before deleting it.
- Acceptance gates: `corpus verify` of `hawk-drone-pilot-v1`, `pilot-two-source-grouped-20261113`,
  `pilot-frozen-diverse-20261113` and `pilot-frozen-uniform-20261113` and `discover verify` of both
  runs exit 0; `contract-set.json` holds the installed pins; every seal other than the
  staged-hashes record's equals its stale copy, or the recipe's table is updated with the reason;
  every retained operator input is still present.
- Documentation target: [Contracts](current/contracts.md) and the [two-source
  recipe](workloads/two-source-pilot/README.md).
```

- Amendments: none.

## Implementation

No code or contract changed. The sealed datasets and the stamp (`contract-set.json`, `corpus/`,
`import/`, `run/`, `self-supervised-corpus/`, `pilot-inventory.json` and both
`pilot-frozen-*.yaml`) were moved out of `$DATA_DIR` to a sibling directory on the same filesystem,
keeping `cache/`, `uv-cache/`, `workload-selection/` and `preserved-operator-inputs-pre-baseline/`
in place. The verified WetlandBirds `source.zip` was hard-linked from the moved acquisition into the
new `pilot-wetland-acq-20261112/cache/`, as the [two-source
recipe](../workloads/two-source-pilot/README.md) allows. A one-off script, kept only in the session
scratch, then ran `make development-workload-prepare`, the hawk commands of the
[Corpus](../current/corpus.md) page and the recipe end to end: inventory, three acquisitions, pool,
37 imports, build, stage, verify, `corpus hashes --run-id pilot-hashes-origin-grouped`, both
discovery runs with the cached `ss-perception-gpu` environment and `TORCH_HOME`, both verifies, the
link review and both frozen versions, then every corpus and run verify again. It ran from 17:00 to
17:59 with no refusal; the diverse discovery run took about 35 minutes on the local GPU.

Transfer: the hawk source was reused from `workload-selection/` and the Zenodo archive from the
hard link, so only the two Hugging Face acquisitions were downloaded, 164,583,968 and 144,830,619
bytes on disk with their records and metadata, about 0.31 GB of the owner's 50 GB cap.

Finding: the rebuilt root holds the same 1,664 non-frame files as the stale one, 939 of them sealed
records. Every file and seal is identical except two: `contract-set.json`, now holding the installed
pins, and `run/pilot-hashes-origin-grouped/staged-hashes.json`, whose seal changed because it now
carries `contract_set`. All twelve identities in the recipe's table, including the archive hash,
match, so the table is unchanged. After that comparison the stale copy was deleted, as the task
states. The recipe now says that both hosts of a comparison must install one contract set, and the
[Contracts](../current/contracts.md#development-stage) page links this record.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Four corpora and both runs verify | Final verify loop of the rebuild: `corpus verify` of `hawk-drone-pilot-v1`, `pilot-two-source-grouped-20261113`, `pilot-frozen-diverse-20261113`, `pilot-frozen-uniform-20261113`; `discover verify` of `pilot-diverse-grouped-20261113` and `pilot-uniform-grouped-20261113` | pass: all `verified`, exit 0; frame sets `45e882cb...`, `e7b0a74e...`, `291de9e7...`, `a2dc21bb...`, runs `0dac2222...` and `696e7728...` |
| The plan's reproduction | `.venv/bin/ss-track corpus verify --corpus hawk-drone-pilot-v1`, after the stale copy was deleted | pass: `verified`, exit 0 |
| `contract-set.json` holds the installed pins | Its 19 structure and 19 meaning pins compared with `installed_fingerprints` and `installed_meanings`; `require_current_data_root` on `$DATA_DIR` | pass |
| The staged-hashes record carries pins | `run/pilot-hashes-origin-grouped/staged-hashes.json` `contract_set` compared with `carried_contract_set()` | pass: 19 rows, equal |
| Every other seal equals its stale copy | Snapshot of seals and non-frame file hashes of both roots, compared by path; 28,477 frame files skipped on each side, covered by bundle seals and `corpus verify` | pass: 1,662 of 1,664 files identical, 938 of 939 sealed records; only the stamp and the staged-hashes record differ, as expected |
| The recipe's identities | All twelve rows of the recipe's table against the rebuilt records and archive | pass: twelve of twelve; table unchanged |
| Every retained operator input is still present | `git status` of `docs/impl/workloads/` and `scenarios/`: no YAML input changed, only the recipe README gained one sentence; `tests/schema/registry/test_retained_inputs.py` passes; `preserved-operator-inputs-pre-baseline/` (24 files) and `workload-selection/` were never moved | pass |
| Transfer within the authorized cap | Acquired bytes on disk of the two Hugging Face runs | pass: about 0.31 GB |

## Audit handoff

Reviewed: the moved and kept paths, the archive reuse, every step's result line, the seal
comparison and the deletion. `none identified`. Dropped observation: the rebuild left 17 `.lock`
files, empty `flock` targets that the next run reuses, as the stale root held; no work.

## Close or resume

Every gate passed. The task has left the plan; the Contracts page and the two-source recipe are
updated. Plan counts after: 126 agent and 30 human tasks; next agent `data-contracts-audit`
(optional), next human `define-locked-test-policy` (optional). `data-contracts` remains planned.
