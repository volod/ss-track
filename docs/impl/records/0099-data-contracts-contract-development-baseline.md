# Contract development baseline

## Task and scope

- Id / capability: `contract-development-baseline` / `data-contracts`
- State: accepted
- Source: plan task at `7823bde`; the working tree held the uncommitted section 17.7 policy
  (`AGENTS.md`, `docs/design/spec.md`, `docs/impl/plan.md`) that added this task.
- Plan counts at start: 157 open tasks (127 agent, 30 human). Next agent
  `contract-development-baseline`. Next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### contract-development-baseline

The registry holds many versions per contract, along with retired majors, views, projections and
historic fixtures. They exist only for development records that nobody outside this repository
holds. They keep outdated datasets and tests alive and make a first consumer read a long history of
formats that were never released.

- Serves: `data-contracts` -- [Development stage and
  release](../design/spec.md#177-development-stage-and-release)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Every contract has one file, `1.0.0`, equal in structure and meaning to its
  latest version today, and every writer stamps `schema_version: 1`. The registry states
  `stage: development`. `make lint-contracts` accepts an in-place edit of a `1.0.0` file that re-pins
  its registry entry, and refuses an unpinned edit or a second version. A record written under an
  earlier development contract set is refused with `RECORD_SCHEMA_UNSUPPORTED` and the remedy to
  regenerate it. The development data root is regenerated under the new set.
- Scope boundary: Contract files, registry, its meta-schema, the history gate and the read path.
  The section 17.3 classifier, the oracle, dispositions and views stay installed, tested on
  synthetic version pairs instead of repository history. `retired_majors`, the views and
  projections of majors other than 1, and the historic fixtures of those majors are removed. Event
  packages collapse to `1.0.0` through `make proto-gen` in the same way. No operator-written
  declaration, reviewed label or review decision is deleted: each one that the collapse changes is
  edited by this change, and the record states the edit.
- Data and artifact paths: `contracts/`, `src/ss_track/schema/`,
  `src/ss_track/core/evidence/read_window.py`, `src/ss_track/corpus/records/projections.py`,
  `src/ss_track/contract/proto/`, `tests/schema/`, `tests/corpus/records/`,
  `docs/guide/authoring-contracts.md`, `contracts/README.md`, `$DATA_DIR/`.
- Execution path: Rewrite each contract's latest version as `1.0.0`, with its `$id` and every
  `$ref` at `1.0.0`, and set every writer's major to 1. Remove the older files and the code and
  fixtures that only read them. Add `stage` to the registry and its meta-schema, and make the
  history gate apply the section 17.7 rule of the stage. Record the development contract-set digest
  on the data root and check it on the shared read path. Delete the sealed datasets under
  `$DATA_DIR`, regenerate them from the retained declarations, and rewrite the authoring guide and
  `contracts/README.md` for the development flow.
- Acceptance gates: Each contract has exactly one file, `1.0.0`. A fixture edit of a `1.0.0` file
  passes the gate with its re-pin and fails without it, and a fixture `1.0.1` under
  `stage: development` fails. A record carrying the previous contract-set digest is refused with
  the regenerate remedy. Every regenerated record validates under the new set, and no
  operator-written input is lost. Classifier and oracle tests cover every section 17.3 row on
  synthetic pairs. `make ci` passes.
- Documentation target: [Contracts](current/contracts.md).
```

- Amendments: one, authorized by the owner's request to implement the task and improve its
  documentation. The task text placed the stale-record check "on the shared read path" and the
  stamp "on the data root" as one digest. A sealed read takes only a path and no data root, so the
  check runs where every command resolves the data root, and the stamp holds one structure
  fingerprint per record contract, so a refusal names the changed contracts. Section 17.7 of the
  specification was amended to match:

```markdown
- Execution path: ... Record the development contract set on the data root as the structure
  fingerprint of each record contract, written when a command first seals a record there, and
  check it where every command takes the data root. ...
```

## Implementation

**Contract set.** A one-off script, not kept, rewrote each JSON Schema contract's newest version as
`1.0.0`: the `$id` and every internal `$ref` at `1.0.0`, `schema_version` const 1 for the five
formats that were at major 3 (`declaration/recording`, `declaration/corpus`,
`record/source-manifest`, `record/corpus-manifest`, `record/frame-bundle`), structure otherwise
unchanged. It removed the 81 older files and every `retired_majors` entry, pinned each new file
with change class `initial`, and added `stage: development` to `registry.yaml`. The five event
packages were already single `1.0.0` images and did not change. Two development edits then
exercised the in-place flow on `result/command`: `source_inspection.migration_operations` was
removed, and a description that named older records was corrected.

**Stage rules.** `contracts/meta/registry.json` requires `stage` (`development` or `released`).
`schema/registry/stage.py` holds the Git-free rules (one `1.0.0` per contract, class `initial`, no
retired major), which `schema/registry/check.py` applies. `schema/compatibility/history.py` reads
each revision's stage with `stage_of`: a development revision froze nothing, a released one keeps
the immutability check, and a working set that returns to development after a released revision
is refused. A registry without `stage` reads as development, so the merge base before this change
compares cleanly. `schema/compatibility/freeze.py` takes only a `1.0.0` candidate in development
and replaces it in place through `publishing.publish(..., replace=True)`, which restores the old
bytes when the registry cannot be replaced.

**Stale data.** `core/evidence/contract_stamp.py` keeps `$DATA_DIR/contract-set.json`, the
structure fingerprint of each record contract. `commands/report.py` `reported_on_data_root` and
`checked_data_root` refuse a root stamped under another set with `RECORD_SCHEMA_UNSUPPORTED`,
`changed_contracts` and the regenerate remedy; `data clean` opts out. `sealing.write_sealed` stamps
the checked root on the first sealed write, so read-only commands write nothing. In development,
`read_refusals` gives an older or newer major the same regenerate remedy. Rejected alternatives: a
per-record contract field, which would move every seal and outlive the development stage; a
whole-registry digest, which would ask for regeneration after a description edit; and stamping on
every command, which made `corpus verify` write a file.

**Code that only served old majors.** Major 3 became 1 in `corpus/records/kinds.py` and
`corpus/declarations/declaration.py`. Projections are keyed by the current major. The
`corpus-3-without-source-terms` stated shape (`corpus/records/shapes.py`), the source migration
route (`migration_operations`, `require_migration_operations` and the `facts` branch of
`successor_of`), `sealing.seal_violations` and `enforce.record_violations` were removed; the
amendment and redecode now carry the current record and `seal` refuses an invalid successor. The
view, stated-shape, disposition and projection machinery stays, empty.

**Tests.** `tests/corpus/kept_records/`, `tests/corpus/_historic.py`, `test_historic_records.py`,
`test_historic_commands.py` and `test_historic_evolution.py` were removed with the tests that
replayed old-major records. One sealed frame-set record moved to `tests/schema/frame-set-record.json`
as a sample of the current contract. The record examples were resealed at major 1. Evolution tests
run on a private set moved to `released` (`tests/schema/conftest.py` `release`); tests of a
projected or unprojected predecessor use a synthetic major 0 or 4
(`tests/corpus/conftest.py` `project_older_major`). New: `tests/schema/registry/test_stage.py`,
`tests/corpus/records/test_contract_stamp.py`, the development case in `test_retired.py` and the
released-remedy case in `test_sealed.py`.

**Documentation.** [Contracts](../current/contracts.md#development-stage) gained the development
stage and lost the version changelog; the corpus pages, the authoring guide, `contracts/README.md`,
the contract design note, `AGENTS.md` and specification sections 17.2, 17.4, 17.6 and 17.7 now
state the stage. No public API, CLI flag, environment variable or dependency changed;
`source_inspection` no longer reports `migration_operations`.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Each contract has exactly one file, `1.0.0` | `find contracts -name '*.json' -not -path '*/meta/*'` (36) and `contracts/event/*/1.0.0.binpb` (5); `test_stage.py::test_the_shipped_set_is_in_the_development_stage` | pass |
| An in-place edit passes with its re-pin and fails without it | `test_stage.py::test_an_edit_in_place_passes_only_with_its_re_pin`, `test_freeze_re_pins_the_one_version_in_place`; the two real `result/command` edits through `ss-track contracts freeze` | pass |
| A fixture `1.0.1` under `stage: development` fails | `test_stage.py::test_a_second_version_is_refused_in_development`, `test_freeze_refuses_any_other_version_in_development` | pass |
| History by stage | `test_stage.py::test_history_accepts_a_development_edit_in_place`, `test_history_compares_a_released_revision_and_refuses_a_return`; `make lint-contracts` against `origin/main` | pass |
| A record under the previous contract set is refused with the regenerate remedy | `test_contract_stamp.py` (stamp on first write, refusal naming `changed_contracts`, `data clean` exempt, damaged stamp, released set); `test_sealed.py` remedies in both stages | pass |
| Every regenerated record validates under the new set | `$DATA_DIR` deleted except `cache/` and `uv-cache/`, then rebuilt by `make development-workload-prepare` and the hawk commands, and by the two-source recipe in `docs/impl/workloads/two-source-pilot/README.md` (three authorized acquisitions, pool, 37 imports, build, stage, verify, hashes, both discovery runs, links, both exports, builds, stages, link reviews and freezes); `corpus verify` of `hawk-drone-pilot-v1`, `pilot-two-source-grouped-20261113`, `pilot-frozen-diverse-20261113`, `pilot-frozen-uniform-20261113` and `discover verify` of both runs | pass: every step exited 0 with no refusal; all six verified. The acquisition and pool seals equal the documented ones; the corpus, frame set, runs, links and freezes have new seals, now in the recipe's table |
| No operator-written input is lost | The recipe's declarations, link decisions and reviews are in the repository and replayed; the 24 YAML inputs found under the old root, including the completed blind audit review, are kept under `$DATA_DIR/preserved-operator-inputs-pre-baseline/` | pass |
| Classifier and oracle cover every section 17.3 row on synthetic pairs | `tests/schema/compatibility/` on a private set moved to `released` | pass |
| `make ci` | `make ci` | pass: 2631 passed, 123 deselected |
| Full suite and quality | `make test` (2746 passed, 8 skipped), `make quality` (coverage 91%, Markdown lint after line fixes, wheel and sdist build) | pass |

## Audit handoff

Reviewed: the collapsed set against the previous newest versions (structure equal apart from the
`$id`, `$ref` and major const, and the two development edits), the gate in both stages, the freeze
rollback, the stamp on every command entry, and every current-state page and guide that named a
version.

- `AUD-contract-development-baseline-1` (nonblocking): an event package cannot be edited in place;
  `make proto-gen` and `make proto-check` treat its `1.0.0` image as frozen, so an event message fix
  would still need a new version. Owner: `event-package-development-edit`, added in this change.
- `AUD-contract-development-baseline-2` (nonblocking): the data-root stamp holds structure
  fingerprints only, so a meaning-only change (an enum value's meaning, a unit) that alters how
  stored values are read asks for no regeneration. Owner: `data-contracts-audit`, whose text
  states the section 17.7 rules it reviews; the author of such an edit deletes the affected
  datasets by the `AGENTS.md` rule.
- `AUD-contract-development-baseline-3` (nonblocking): the recipe in
  `docs/impl/workloads/two-source-pilot/` regenerates the grouped version, both runs, the link
  review and both frozen versions, but not the superseded ungrouped versions
  (`pilot-two-source-20261112`, `pilot-two-source-20261113` and their runs), the blinded audit
  packet or the portable link-review hosts. They were evidence of closed tasks and no open task
  reads them; their operator-written inputs are kept under
  `$DATA_DIR/preserved-operator-inputs-pre-baseline/`. Dropped: no open work needs them.

## Close or resume

Every gate passed. [Contracts](../current/contracts.md#development-stage) states the development
stage and links this record. Plan counts after: 157 open tasks (127 agent, 30 human); this task
left the plan and `event-package-development-edit` joined the `data-contracts` group. Next agent
`event-package-development-edit`; next human `define-locked-test-policy (optional)`.
`data-contracts` stays `planned` with that task, its audit and `contract-release-freeze`.
