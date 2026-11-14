# Corpus discovery contract

## Task and scope

- Id / capability: `corpus-discovery-contract` / `self-supervised-corpus`
- State: accepted.
- Source: plan task; starting HEAD `68bd006` on branch `st-06-self-supervised-corpus`, clean tree.
- Plan counts at start: 127 tasks, 104 agent and 23 human. Next agent
  `corpus-discovery-contract`; next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-discovery-contract

Reviewers cannot reconstruct why a frame or interval entered a candidate list without stable records.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A portable, validated candidate inventory records authorized source lineage,
  frame or time windows, group, model and processing revision, scores, selection and audit status.
- Scope boundary: Versioned interchange contracts and validators; predictions are not labels and
  scores do not authorize a source or assign a final split.
- Data and artifact paths: `contracts/`, `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Reuse source and frame identities, define candidate and run contracts and validate
  golden records without either external service. Feature provenance names the package commit,
  library versions, weight revisions and SHA-256, device, dtype, batch size and preprocessing; a
  window from a sibling time names its ffmpeg version and sampling rate
  ([frame mapping](current/corpus/sibling-integration.md#frame-mapping)).
- Acceptance gates: Fixtures reject missing rights references, ambiguous frame/time identity, a
  frame named only by a sibling time, missing model provenance and invalid selection probability;
  contract-only consumers validate unchanged records and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

Two record contracts, owned by `self-supervised-corpus`, frozen at 1.0.0 with
`ss-track contracts freeze`:

- `record/discovery-run`: the corpus version and frame-set seal read, ss-track version and
  revision, feature extractors with full provenance, score definitions, ss-video hint sources, the
  pool window length, the selection method and the independent audit design, and one line per
  stream sealing its inventory.
- `record/candidate-inventory`: one per stream, repeating its group, bundle, source and source
  record seal and the bundle's frame window, and listing every candidate window with its origin,
  scores, selection and audit status.

New package `src/ss_track/corpus/discovery/`: `records.py` seals and writes (`seal_discovery`,
`write_discovery`), `reader.py` reads and verifies (`read_discovery`, `verify_discovery`),
`run_rules.py` and `inventory_rules.py` check the `x-rules` the dialect cannot state, `binding.py`
binds a run to its staged corpus, `findings.py` reports every broken rule at once. `kinds.py` gains
both `RecordFormat`s and `storage/layout.py` the run paths under
`$DATA_DIR/self-supervised-corpus/<run-id>/`. Reused: the sealed read path, `seal`,
`write_sealed`, `read_frame_set`, `load_corpus_manifest`, the corpus-manifest half-open window form
and the source-record seal as the rights reference. No dependency, CLI command, environment
variable or refusal code was added, so `result/command` and `uv.lock` are unchanged;
`pyproject.toml` lists the new `ss_track.corpus.discovery` package. Current state:
[discovery records](../current/corpus/discovery-records.md).

Decisions:

- Two formats, not one: one inventory per stream keeps each sealed record bounded by its stream, as
  frame bundles are, while the run states provenance once and seals the inventories, as a frame set
  seals bundles. The run therefore holds no `x-references` to the inventory contract, which keeps
  the two freezable in order.
- Every candidate names a half-open window of source frame indexes; a sibling time is an `origin`
  that must still carry frames, and names a run hint source holding the ffmpeg version and
  sampling rate. A time-only candidate cannot be stated.
- Pool windows tile each bundle with no gap or overlap, so processed exposure is the pool and a
  missing window is a refusal.
- Audit eligibility depends only on origin: excluded and unselected pool windows stay in the audit
  pool so missed positives can be measured; a sibling window is always ineligible. The
  specification section 4.1a now states this.
- Selection probabilities are bounded per status by the schema (selected in (0, 1], not selected in
  [0, 1)), and to exactly 1 and 0 under deterministic selection by the rules; audit inclusion
  probabilities equal `sample_size / eligible_count` within a relative 1e-12.
- Discovery binds only to streams, never generated cases.
- Rule violations reuse `RECORD_INVALID` with a `findings` list; a missing run is
  `RECORD_TAMPERED`, as the sealed read path already reports a missing record; a reused run id with
  other records is `CORPUS_CONFLICT`; a run over another frame set is `FRAME_SET_MISMATCH`.
- Rejected: a CLI command now, since no producer exists and it would need a `result/command` minor
  for no user; it moves to the adapter task that writes runs. Rejected: recomputing the sibling slot
  rule here, which the adapter owns with its fixtures.

`tests/schema/compatibility/test_history.py` deleted `record/frame-set` to test that history sees
a removed contract. The discovery contracts now reference the frame set, so the set check refused
first and hid the history message; the test now deletes `record/hash-comparison`, which nothing
references. The gate still fails closed either way.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Rejects missing rights references | `test_discovery_contract.py::...no-rights-reference`, `test_standalone.py::..._no_rights_reference`, `test_discovery_store.py` binding cases | pass: no source-record seal is `RECORD_INVALID`; a seal other than the frame set's is a `binding` finding |
| Rejects ambiguous frame/time identity | `test_discovery_rules.py::test_a_window_must_name_frames_unambiguously` | pass: empty, reversed, out-of-bundle, off-tiling, missing and repeated pool windows and repeated ids are refused |
| Rejects a frame named only by a sibling time | `sibling-time-alone`, `sibling-time-in-seconds`, `undeclared-hint-source`, `hint-without-ffmpeg`, `hint-without-rate`; standalone `_sibling_time_alone`, `_time_instead_of_frames` | pass; the slot rule itself is not recomputed (`AUD-...-1`) |
| Rejects missing model provenance | `test_the_contract_refuses_a_record_missing_identity_or_provenance` | pass: commit, weight hash, revision, weights, libraries, batch size, dtype, preprocessing and device are each required |
| Rejects invalid selection probability | `test_the_contract_refuses_an_impossible_probability`, `test_selection_and_audit_state_probabilities_their_design_produces`, standalone `_certain_but_unselected` | pass: bounds per status, NaN, deterministic 1 and 0, ranks, budget, audit inclusion probability and stratum counts |
| Contract-only consumers validate unchanged records | `tests/schema/registry/test_standalone.py` over `tests/schema/examples/record-discovery-run.json` and `record-candidate-inventory.json`; `test_the_golden_records_seal_and_match_their_examples` | pass: `jsonschema` with only `contracts/` accepts the golden records, which equal the writer's bytes |
| Write, read, verify, tamper | `tests/corpus/discovery/test_discovery_store.py` over a staged two-stream corpus | pass: round trip, idempotent repeat, `CORPUS_CONFLICT`, `FRAME_SET_MISMATCH`, `RECORD_TAMPERED`, resealed `RECORD_INVALID`, no generated case |
| Contract freeze and history | `ss-track contracts freeze`; `make lint-contracts` | pass: `[contract evolution] 0 finding(s)` against `origin/main` |
| Documentation | `make lint-md`, `make lint-doc-links`, `make lint-spec-plan` | pass, 0 findings each |
| Quality suite | `make quality` | pass: 2017 passed, 1 skipped; coverage 97.25%, discovery modules 94 to 100%; wheel and sdist built |
| Final gate | `make ci` | pass: 2017 passed, 1 skipped |

## Audit handoff

Reviewed scope: both contracts, `corpus/discovery/`, the layout and kind additions, the tests and
the documentation changes of this task.

- `AUD-corpus-discovery-contract-1`: `verify_discovery` checks a `sibling_time` window for a
  declared hint source and bundle bounds only; it does not recompute the window from bundle PTS by
  the slot rule, so a wrongly mapped sibling window passes. Nonblocking: no writer produces sibling
  windows yet. Owner: `corpus-video-index-adapter`, whose execution path and gates now state it.
- `AUD-corpus-discovery-contract-2`: a run names no owner's source approval, because no approval
  record exists. Blocking for real-source runs only. Owner: `corpus-video-index-adapter` (a
  `record/discovery-run` minor and a refusal without it), which now states it.
- `AUD-corpus-discovery-contract-3`: `write_discovery` takes no lock; two writers of one run id can
  leave a run whose lines name the other's inventories. Reads refuse such a run as
  `RECORD_TAMPERED`, so nothing wrong is served. Owner: `corpus-video-index-adapter`, whose gates
  now require serialized writers.
- `AUD-corpus-discovery-contract-4`: no command writes or verifies a run, and feature rows have no
  contract. Owner: `corpus-video-index-adapter`, which now states the command, its
  `result/command` minor and a feature-row contract.
- `AUD-corpus-discovery-contract-5`: crop modes are `center` and `none`; tiled coverage needs a
  mode and grid. Owner: `corpus-ssl-selection`, which now states the contract minor.
- Dropped: overlapping pool windows and audit designs other than `stratified_fixed_size`. No planned
  consumer needs them, and either is a contract minor when one does.
- Dropped: current source terms such as an expired `retain_until` are not checked by
  `verify_discovery`. `corpus-review-and-freeze` already refuses expired terms before a corpus is
  frozen from candidates, and a run grants nothing.
- Fixed in this change: the history test that deleted `record/frame-set` stopped testing history
  once other contracts referenced it; it now deletes an unreferenced contract.

## Close or resume

Every gate passed. The new [discovery records](../current/corpus/discovery-records.md) page is
linked from the corpus page and the current-state index, and the contracts page lists both
contracts. The task is removed from the plan; `corpus-video-index-adapter`,
`corpus-group-and-leakage-review` and `corpus-selection-evaluation` drop the dependency, and
`corpus-ssl-selection` keeps only its adapter dependency. The adapter and SSL selection tasks carry
the routed findings. Plan counts moved from 127 (104 agent, 23 human) to 126 (103 agent, 23
human). The next agent task is `corpus-video-index-adapter`; `self-supervised-corpus` stays
planned.
