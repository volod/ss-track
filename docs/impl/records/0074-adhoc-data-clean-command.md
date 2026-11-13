# Data clean command

## Task and scope

- Id / capability: `data-clean-command` / `corpus-provenance`
- State: accepted
- Source: user request; start commit `a67aec8`; the working tree held the closed pilot and
  authorization work of records 0067 and 0068.
- Plan counts at start: 102 agent and 23 human; next agent `corpus-selection-evaluation`, next
  human `define-locked-test-policy (optional)`.
- Accepted request: "then please delete obsolete data. it's good to have a special command that
  make system clearance of development artifacts or temporary artifacts for runs. e.g. if we will run
  some tasks on other computer or temporary artifacts for data preparation in future tasks. please
  create sych command and update tsks that will create temporary artifact wit requirements to update
  such command for future cases"
- Amendments: none.

## Implementation

Added `ss-track data clean` under the `corpus-provenance` capability, which owns the data-root
layout; the specification states it in section 4.1 with what it does not do, and the registry row's
evaluation names it. It plans by default and removes only with `--apply`. Four kinds are
registered in `corpus/storage/clean_kinds.py`, each with its target, restore path and writer lock:
`staged-frames` (`--corpus`, under `.staging.lock`), `acquisition-cache` (`--run-id`, under
`.acquisition.lock`), `scratch` (every lock in the data root, so it runs alone) and `tool-caches`.
`corpus/storage/clean.py` validates targets before any lock creates folders, refuses links and
paths outside the data root, makes read-only bundle directories writable by their owner just before
removal, and reports each kind's entries and bytes. `commands/data.py` adds the command.
`result/command` 1.26.0 adds the `planned` and `cleaned` statuses, the `clean` object and
`DATA_ROOT_BUSY`. No dependency, environment variable or declaration contract changed.

Sealed records, imported sources, declarations and review decisions are never a kind. The command
does not choose what is obsolete, delete a whole data root or reach another host. Documented under
[cleaning the data root](../current/corpus.md#cleaning-the-data-root).

Future work is bound to it in three places: an AGENTS.md rule that reproducible bytes are removable
only through a registered kind and that a task first writing one registers it with a test, the
planning workflow's task-shape rule, and the acceptance gates of the open tasks that will create
such bytes: `corpus-scale-pilot`, `corpus-wetland-evidence`, `run-bundle-store`,
`container-module-sandbox`, `module-image-recipes`, `telemetry-bundle-store` and
`temperature-run-orchestration`, plus the second-host cleanup step of
`review-pilot-recording-links`.

Obsolete pilot data was then removed with the command and the owner's approval:

| Removed | Means | Bytes |
| --- | --- | --- |
| Frames of `pilot-two-source-20261112` and `pilot-two-source-20261113` | `data clean --kind staged-frames --apply`, 1.1 s | 137.5 GB |
| Frames of the fresh-root `pilot-two-source-grouped-20261113` | the same, with `DATA_DIR` set to the fresh root | 74.3 GB |
| The fresh root's WetlandBirds download cache | `data clean --kind acquisition-cache --apply` | 9.4 GB |
| The remaining fresh root, 1.3 GB of imports, acquisitions and records | `rm` after its `staged-hashes.json` was kept as `run/pilot-hashes-fresh-20261113/` | 1.3 GB |

Every sealed record of the superseded versions and runs is kept, along with the grouped corpus,
the imports, the acquisitions with the origin's WetlandBirds archive, and the audit packet. Pilot
storage fell from about 297 GB to about 88 GB. `discover verify` of the superseded runs now refuses
until their versions are staged again; the comparison `run/pilot-fresh-compare-20261113/` still
reads.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Plan, release and restage to the same frame set | `tests/corpus/storage/test_clean.py::test_frames_are_planned_released_and_staged_again_to_the_same_frame_set` | pass: records kept, verify refuses after release and passes after staging |
| Locks and refusals | `test_a_held_staging_lock_refuses_and_keeps_the_frames`, `test_an_unknown_corpus_refuses_without_creating_folders`, `test_a_request_without_its_target_or_with_a_stray_one_is_refused` | pass |
| Scratch, acquisition cache and tool caches | `test_scratch_is_removed_only_when_no_lock_is_held`, `test_an_acquisition_cache_is_removed_and_its_record_kept`, `test_tool_caches_leave_environments_and_other_caches` | pass |
| Result contract | `contracts freeze result/command` 1.26.0; logged results checked by the test harness | pass |
| Real use | the four removals above | pass: 221 GB released |
| Required gate | `make ci` | pass: 2357 passed, 112 deselected |
| Documentation | `make lint-md`, `make lint-doc-links`, `make lint-spec-plan` | pass |

## Audit handoff

- `AUD-data-clean-command-1`: the command removes a whole second data root only kind by kind; the
  remaining small directory was removed by hand. Dropped: deleting a data root is deliberately
  outside the command, and the rule is stated in the current page.
- `AUD-data-clean-command-2`: audit packets and isolated sibling environments are reproducible but
  not yet kinds. Owners: `corpus-scale-pilot` and `corpus-wetland-evidence`, whose gates now
  require registering the kinds they leave.
- Reviewed scope: the new modules, the command, the contract minor, the documentation and the
  real removals; nothing else identified.

## Close or resume

Accepted. The capability remains planned. Plan counts are unchanged at 102 agent and 23 human tasks.
