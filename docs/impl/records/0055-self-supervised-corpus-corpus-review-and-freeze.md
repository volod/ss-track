# Corpus review and freeze

## Task and scope

- Id / capability: `corpus-review-and-freeze` / `self-supervised-corpus`
- State: accepted.
- Source: plan task; starting HEAD `b3bcbdb` on branch `st-06-self-supervised-corpus`, clean tree.
- Plan counts at start: 123 tasks, 100 agent and 23 human. Next agent
  `corpus-review-and-freeze`; next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-review-and-freeze

Large candidate inventories need bounded human decisions before they become benchmark inputs.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: Reviewers can inspect candidates and export a frozen, reproducible corpus
  version with source terms, group, split, exclusions and decision provenance.
- Scope boundary: Review and source-to-corpus manifest export; label adjudication uses the existing
  annotation contract and the locked split requires its existing custodian policy. Selection never
  ranks a locked stream, but the audit sample, which depends only on origin, draws from locked
  groups' strata; review offers none of those windows without that policy and says why.
- Data and artifact paths: `contracts/`, `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Provide bounded review decisions and manifest generation through existing import,
  corpus build, stage and verify flows, with refusal on expired terms or unresolved split conflicts.
  An unresolved split conflict is a link across splits that the version's
  [link review](current/corpus/leakage-review.md) left undecided: freezing reads the review with
  `read_links`, requires it to name the frozen version's manifest and frame set, and refuses an
  unresolved link across splits. A link review covers one version, so freezing also applies the
  reviewer's link decisions to every version the frozen one supersedes and refuses a related
  recording held in another split there.
- Acceptance gates: Replaying frozen reviewed decisions yields the same membership and hashes;
  rejected, unknown or unreviewed cases cannot masquerade as verified labels; denied, expired and
  conflicting sources refuse. Fixture tests and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

A reviewer now decides the windows a discovery run offers, and a frozen corpus version is made from
those decisions through the existing build, stage and verify flows (current state:
[review and freeze](../current/corpus/review-and-freeze.md)).

- `ss-track discover queue` reports what a run offers and writes a review template: every offered
  window `unreviewed`, each after a comment with its frames, offers, selection, audit and scores,
  and an empty reviewer the contract refuses.
- `ss-track discover export` reads the review, verifies the run, checks each included source's
  current terms and writes the corpus declaration: one stream per maximal run of overlapping or
  adjacent included windows, named `<pool-stream>.<start>-<end>`, in its pool stream's group and
  split, one encounter per stream, with the pool's decode policy and scenario rights.
- `ss-track corpus freeze` checks current terms, replays the review and requires the version to hold
  exactly those streams, reads the link review with `read_links` bound to this manifest and frame
  set, refuses an undecided link across splits (`LINKS_UNRESOLVED`), applies every related decision
  to the versions the frozen one supersedes (`SPLIT_LEAKAGE`), verifies every frame and seals
  `corpus/<corpus-id>/freeze.json`.

New package `corpus/review/`: `queue.py`, `decisions.py`, `membership.py`, `template.py`,
`export.py`, `superseded.py`, `freeze.py`, `freeze_record.py` and `result.py`. Reused: discovery
verification, `require_sources_hold` for retention and record pins, `read_links`,
`follow_links` and comparison projections for the chain, `verify_corpus_frames`, the corpus
contract for the export, and the scratch and lock writers. `links/run.py` exposes its frame-set
reader as `staged_frame_set`; layout and record kinds gain the freeze record.

Contracts frozen: `declaration/corpus-review` 1.0.0, `record/corpus-freeze` 1.0.0 and
`result/command` 1.18.0 (`queue`, `review`, `superseded`, `declaration_path`,
`declaration_sha256`, `LINKS_UNRESOLVED`). `pyproject.toml` lists `ss_track.corpus.review`; no
dependency changed. Specification section 4.1a states review and freeze.

Decisions:

- Review is bounded by the run: selected, audit-sampled and sibling windows only, so review cost is
  the budget plus the audit sample and an unselected window is reviewed only through the
  independent sample. A decision on any other window is refused, not ignored.
- A locked stream's windows are withheld and named `locked_without_policy` in the queue, template
  and record, and a decision on one is refused.
- Every include and exclude states an observation from a closed list, `unknown` included; the
  record keeps it verbatim beside the decision, never in the manifest, and `label_revision` is
  always null, so no observation, exclusion or unreviewed window can pass as a label.
- Groups and splits stay those of the pool version; review neither moves nor merges them.
- The link review must be of the frozen version itself, as the task states, so the flow is export,
  build, stage, links, freeze; a related decision about a recording the version does not hold is
  kept outside its links and applied to the chain at freeze.
- An undecided link inside one split does not refuse; it is counted in the record.
- Rejected: freezing straight from the pool version without a build (the existing flows would not
  check the frozen membership), automatic split assignment at review, and per-window streams
  (adjacent windows would cut tracks apart).

## Acceptance evidence

Run: `$DATA_DIR/self-supervised-corpus/freeze-eval-20261107/` over a copy of the leakage-review
data root (13 clips, four windows of the real hawk-and-drone flight, hawk-d locked);
`results/summary.md` states the steps, `results/scripts/decide.py` the scripted reviewer.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Replaying frozen reviewed decisions yields the same membership and hashes | `test_replaying_the_review_on_another_data_root_gives_the_same_hashes`, `test_the_export_writes_one_declaration_...`; real export and freeze retries | pass: identical freeze record, manifest, frame set and link seals on a second data root; retries `unchanged` |
| Rejected, unknown or unreviewed cases cannot masquerade as verified labels | `test_freezing_seals_membership_exclusions_and_decision_provenance`, `test_no_observation_reaches_the_frozen_manifest`, `test_an_unreviewed_entry_...`; real run | pass: exclusions and unreviewed windows are never members, observations kept verbatim including `unknown`, none in the manifest, `label_revision` null; real run 19 included, 10 excluded, 2 unreviewed |
| Denied sources refuse | `test_withdrawn_rights_after_the_run_refuse_the_export`, `test_terms_that_no_longer_hold_refuse_the_freeze` | pass: `SOURCE_RECORD_CHANGED` naming `rights.sharing` |
| Expired sources refuse | `test_retention_that_ended_refuses_the_export`, `test_retention_that_ended_refuses_the_freeze` | pass: `RETENTION_EXPIRED` the day after `retain_until` |
| Conflicting sources refuse | `test_an_undecided_link_across_splits_refuses_...`, `test_a_related_recording_a_superseded_version_held_...`, `test_a_version_built_from_another_declaration_is_refused`, `test_a_link_review_of_another_version_is_refused`; real `freeze-v2-refused.err` | pass: `LINKS_UNRESOLVED`, `SPLIT_LEAKAGE` across the chain (real: hawk-a related to locked hawk-d of `links-eval-v1`), `CORPUS_CONFLICT`, `FRAME_SET_MISMATCH` |
| Locked windows withheld with the reason | `test_the_queue_offers_every_sampled_and_selected_window_...`, `test_a_decision_on_a_locked_or_unoffered_window_...`; real queue | pass: real run withheld hawk-d's 2 sampled windows |
| Record integrity | `test_a_forged_freeze_record_is_refused` | pass: `RECORD_INVALID` for a changed window and a changed count |
| Resources | `results/*.err` | measured: queue 0.4 s, export 0.5 s, freeze 0.6 s and 80 MB on 16 streams |
| Fixture tests and `make ci` pass | `.venv/bin/pytest tests/corpus/review`; `make ci` | pass: 32 review tests; `make ci` 2249 passed, 7 skipped (sibling probes needing `SST_PERCEPTION_PYTHON`), every check including `lint-contracts` green |

## Audit handoff

Reviewed scope: the new package, the three contracts and their examples, the command wiring,
the layout and kind additions, tests, documentation and the real run.

- `AUD-corpus-review-and-freeze-1`: freezing verifies the discovery run against its pool version's
  staged frames, so a pool's frames must stay on disk until its versions are frozen. Nonblocking;
  storage only. Owner: `corpus-scale-pilot`, whose execution path now measures that storage.
- `AUD-corpus-review-and-freeze-2`: review withholds every locked window while no custodian policy
  exists. Nonblocking; the withholding is stated. Owner: `locked-split-guard (optional)`, whose
  execution path now lets a review naming the policy's hash decide locked windows.
- `AUD-corpus-review-and-freeze-3`: observations are recorded for the selection evaluation, which
  must read them. Owner: `corpus-selection-evaluation`, whose execution path now reads them and
  counts `unknown` and unreviewed windows as unknown. `review-video-corpus-sample` now names the
  review file and `corpus freeze`.
- Dropped: each frozen stream is its own encounter, so two cameras' windows of one event count as
  two encounters of one group. Pairing them would invent a clock relation the corpus does not
  record, and the group, the unit of independence and split, is unchanged; no work is needed.
- Dropped: no change in ss-video or ss-fusion is needed; review and freeze read ss-track records
  only.
- Chore done: record 0054 was left `active` though its task left the plan; it is closed in this
  change with this change's `make ci` and `make lint-contracts`, which run its code unchanged.

## Close or resume

Every gate passed. The new [review and freeze](../current/corpus/review-and-freeze.md) page is
indexed from the corpus page and the current-state index; the corpus, contracts, leakage review,
discovery records and discovery runs pages and specification section 4.1a are updated. The task is
removed from the plan: `corpus-scale-pilot` and `review-video-corpus-sample` drop it from their
dependencies, and `corpus-scale-pilot`, `corpus-selection-evaluation`, `locked-split-guard
(optional)` and `review-video-corpus-sample` state the routed items. Plan counts moved from 123
(100 agent, 23 human) to 122 (99 agent, 23 human). The next agent task is
`corpus-selection-evaluation`; `self-supervised-corpus` stays planned.
