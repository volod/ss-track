# Record read window

## Task and scope

- Id / capability: `record-read-window` / `data-contracts`
- State: accepted.
- Source: plan task; start commit `a70ff789e942960055714f7dad72e9536d164278`; working tree clean.
- Plan counts at start: 130 open tasks (108 agent, 22 human); next agent by priority:
  `decode-policy-reimport (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### record-read-window

A format change sends every record to a fresh data root, and a predecessor of another major cannot be
compared, so the only exit drops `supersedes` and the split guard with it.

- Serves: `data-contracts` -- [Reading older records](../design/spec.md#reading-older-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Each older major declares `view`, `facts` or `retired`. A view record serves
  as evidence with no byte, seal or cohort change, and `supersedes` works across majors.
- Scope boundary: Pure in-memory views stepping one major at a time, one comparison projection per
  major, and accepted majors in the registry. Nothing rewrites a sealed record. A view never derives
  an operator judgment or changes an algorithm revision. No views for the retired historic majors,
  whose records are test data only.
- Data and artifact paths: `src/ss_track/schema/`, `src/ss_track/corpus/`, `tests/schema/`,
  `tests/corpus/`.
- Execution path: Consume each major transition's `change.disposition` in the read path, then route
  `lineage.py`,
  `duplicate_frames.py` and the unlinked listing through the projection. Prove it with a synthetic next
  major of a real contract in the tests. Replace the `older_majors` argument and the older-major
  constant in `amendment.py` with the `facts` disposition, and keep `SEQUENCE_KEYS` as the check that
  a record holds the current facts. Read a predecessor's bundle through its projection, so
  `other_schema` means only that no projection exists, and rewrite the corpus-manifest `migration`
  text in `contracts/registry.yaml`, which warns that nothing checks splits against a version
  `supersedes` cannot name. The key check in `terms.py` still refuses a schema-3 corpus manifest
  sealed before source terms existed, such as `corpus-schema-3-d6b704d.json`, because no major tells
  it apart: give that shape one stated route on the read path and remove the check.
- Acceptance gates: A view major verifies with its frame-set hash and file bytes unchanged. A
  `facts` major is refused as evidence, stays inspectable, and a move of its source is
  `SPLIT_LEAKAGE` and not a schema refusal. A view that derives a rights field fails a test.
  `DECODE_POLICY_MISMATCH` still refuses through a view. A predecessor with no projection is
  `not_compared`, never a failure of its successor. The five real bumps replay to their
  dispositions: `view` for bundle 1 to 2, bundle 2 to 3 and corpus 2 to 3, and `facts` for corpus 1
  to 2 and source 1 to 2.
- Documentation target: [Current implementation](current.md#areas), pages `current/contracts.md` and
  `current/corpus.md`.
```

- Amendments: none.

## Implementation

**Read path.** `src/ss_track/corpus/sealed.py` keeps one module as the gate, now with three entries.
`read_sealed` is evidence: the current major as written, or a `view` major upcast in memory, with
`schema_version` restamped and the original seal kept, so no pin, frame set or cohort moves.
`read_stated` returns a `facts` or `view` record as written, with its disposition, and only the
amendment may call it. `read_comparable` returns the seal, the major and the major's comparison
projection, or none, for any major; a projection that hits a missing key is `RECORD_TAMPERED`. The
kind check moved into `_read_intact`, still after the seal. A refusal now names `disposition` for
an older record, and `accepted_schema_versions` lists the current major plus every major a chain of
views reaches.

**Dispositions.** `Contract.disposition_of` (`schema/store.py`) reads a `retired_majors` entry's
`status`, or the `change.disposition` of the major transition that replaced that major.
`older_disposition` (`schema/enforce.py`) takes the strictest step from the found major to the
current one, ordered `view`, `facts`, `retired`, and gives none for a step no change log states.
`contracts/meta/registry.json` now allows `facts` or `retired` as a historic major's status, and
`contracts/registry.yaml` lists source-manifest major 1 as `facts`, because `--amend-terms` reads its
stated facts; every other historic major stays `retired`. The corpus-manifest migrations for majors 1
and 2 no longer warn that `supersedes` cannot name them: major 2 is compared through its projection,
and major 1, which states no group or split, is reported `not_compared`.

**Views** (`corpus/read_window.py`). A `View` holds kind, major, the pointers it derives and a pure
`upcast`. `view_findings` refuses a derived pointer that names a protected property, the seal, `kind`
or `schema_version`; `apply_views` composes steps and refuses, as `CONTRACT_SET_INVALID`, a declared
view with no function or with findings, and logs each step. `check_view` walks every value of a real
record and names undeclared derivations and a mutated input; it runs in tests only. No installed
major is a view, so the table is empty, per the scope line.

**Disposition floor** (`schema/dispositions.py`). `PROTECTED_PROPERTIES` holds operator judgments
(rights, sensitivity, scenario rights, retention, split, group, encounter) and algorithm revisions
(decode policy, transform, recipe, revision). `disposition_floor` returns `facts` when a major change
that is not a removal names one on its pointer, or inside an added node outside what an added list
holds, since a view may derive an empty list. `transition_findings` refuses a `view` below the floor,
so `freeze` and `make lint-contracts` both apply it. The replay of the five real bumps uses the same
function on observed shapes.

**Stated shape.** The schema-3 corpus manifest sealed before source terms is
`corpus-3-without-source-terms` in `read_window.py`: one test, whether every stream's `rights` holds
`retain_until` and `derived_frames`, applied at whatever major the record stamps, with disposition
`facts` and the amendment remedy. `read_sealed` refuses it with `shape` and `lacking`, and a view
never serves it, since the shape takes the stricter of its own and its major's disposition. The key
check in `terms.py` `require_retention` is gone.

**Projections and comparison** (`corpus/projections.py`). Corpus majors 2 and 3 project `corpus_id`,
seal, decode policy hash, `supersedes` and each stream's id, source, group and split; bundle majors 2
and 3 project pins and `(frame_index, sha256)` pairs. `builder.load_predecessor` reads a declared
predecessor through it and returns `Unprojected` (seal and id only) when the major keeps none.
`lineage.py` compares projections, pins an unprojected predecessor's seal in `supersedes`, ends the
chain there and reports it as `not_compared` with reason `other_schema`, so the build succeeds.
`duplicate_frames.py` reads predecessor bundles through `read_comparable`, so `other_schema` means
only that no projection exists, and the pin checks moved to one `frames.require_bundle_place` shared
with `open_corpus_bundle`. `NotCompared` moved to `projections.py`.

**Amendment.** `amendment.py` reads through `read_stated`; `_require_current_facts` runs for a `facts`
record, and `SEQUENCE_KEYS` stays as the check that such a record holds today's decoded facts. The
`older_majors` argument and `_SCHEMA_WITHOUT_TERMS` are gone. The static scan in
`tests/corpus/test_sealed_reads.py` now refuses `read_stated` outside the amendment, a read entry
with other than a path and a format, and a comparison of a record's `schema_version` outside the read
path.

**Contract and classifier.** `result/command` 1.3.0 (minor) widens a historic major's `status` from
`const: retired` to `enum: [facts, retired]`, lets a linked lineage hold `compared_versions: []`, and
adds optional `not_compared`. The classifier treated `const` to a superset `enum` as an added
constraint (major); `evolution._scalars` now reports it as one minor change at `/enum`, and the oracle
agrees on the 1.2.0 to 1.3.0 transition. `evolution._resolved` became public `resolved`, and
`ENTRY_ADDED` and `ENTRY_REMOVED` name the reason suffixes the floor reads.

**Refactors.** Record kinds moved to `corpus/kinds.py` so the read path can name them without an
import cycle. The source-record loaders moved from `builder.py` to `corpus/sources.py`, so the
builder only builds.

**Compatibility.** No record byte, seal, frame-set hash or refusal code changed, and `uv.lock` is
untouched. Behavior that moved: a build naming a predecessor of another major is compared or reports
`not_compared` instead of `RECORD_SCHEMA_UNSUPPORTED`; a predecessor bundle of major 2 is compared,
so an unrelated one is `BUNDLE_CONFLICT` instead of `other_schema`; a pre-terms corpus is refused by
every evidence read, including `corpus hashes`, which accepted it before, and a rebuild over it is
`RECORD_SCHEMA_UNSUPPORTED` instead of `CORPUS_CONFLICT`; that refusal's details name `shape` and
`lacking` instead of `stream_id` and `source_sha256`. `read_sealed` lost `older_majors`.

**Interpretation.** The scope rules out views for the historic majors, so the gate "the five real
bumps replay to their dispositions" is met by replay, not by installed views: for each bump the
floor on observed shapes and a test-local candidate view, checked by `check_view` on the real older
record and validated against the successor's observed shape, give `view` for bundle 1 to 2, bundle 2
to 3 and corpus 2 to 3; for corpus 1 to 2 and source 1 to 2 the floor gives `facts` and a view naming
the needed judgment is refused. The registry keeps the historic majors' in-service status, which is
`retired` for those no retained record needs.

Rejected: a code list of formats that may read an older major, which is what `older_majors` was; a
judgment annotation in every contract, which would change every contract's meaning for a rule the
audit can decide; walking each viewed record at read time, which costs seconds per million frames;
reading the `supersedes` link of a major with no projection, which interprets a format this tool does
not know. Current state: [corpus](../current/corpus.md#reading-sealed-records),
[lineage](../current/corpus.md#version-lineage) and
[contracts](../current/contracts.md#runtime-enforcement).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A view major verifies with its frame-set hash and file bytes unchanged | `tests/corpus/test_read_window.py::test_a_view_major_verifies_with_its_frame_set_and_bytes_unchanged` | pass: a synthetic corpus 4.0.0, frozen by `freeze_contract` with `view`, reads today's staged major-3 version; same frame-set seal, every file byte equal, seal kept |
| A `facts` major is refused as evidence and stays inspectable | `test_read_window.py::test_a_facts_major_is_refused_as_evidence_and_stays_inspectable`, `test_a_real_corpus_without_source_terms_is_facts_and_still_guards_its_groups`, `tests/corpus/test_historic_records.py::test_a_corpus_that_entered_schema_3_without_terms_refuses_by_name` | pass: `RECORD_SCHEMA_UNSUPPORTED` with `disposition: facts`; `read_stated` returns it unchanged; the real pre-terms record refuses at stage and verify |
| A move of its source is `SPLIT_LEAKAGE`, not a schema refusal | `test_read_window.py::test_a_move_from_a_facts_major_is_split_leakage_and_not_a_schema_refusal`, `test_a_real_corpus_without_source_terms_is_facts_and_still_guards_its_groups`, `tests/corpus/test_lineage_build.py::test_a_move_from_a_predecessor_of_another_major_is_leakage_not_a_schema_refusal` | pass: moved source and moved group named, under the synthetic `facts` major, the real pre-terms shape and a major-2 predecessor |
| A view that derives a rights field fails a test | `test_read_window.py::test_a_view_that_derives_a_rights_field_is_refused`, `tests/schema/test_dispositions.py::test_freeze_refuses_a_view_of_a_major_that_adds_an_operator_judgment` | pass: declared, the read is `CONTRACT_SET_INVALID`; undeclared, `check_view` names it; a freeze declaring `view` for a new rights property is refused |
| `DECODE_POLICY_MISMATCH` still refuses through a view | `test_read_window.py::test_a_decode_policy_mismatch_still_refuses_through_a_view` | pass |
| A predecessor with no projection is `not_compared`, never a failure | `test_lineage_build.py::test_a_predecessor_with_no_projection_is_not_compared_and_fails_nothing[newer,unstated]`, `test_historic_records.py::test_a_predecessor_of_major_1_holds_no_split_and_is_not_compared`, `test_duplicate_frames_major.py`, `test_read_window_rules.py::test_an_unprojected_version_ends_the_chain_behind_it` | pass: builds and stages, `other_schema` named; a real major-2 predecessor and its real bundle are compared |
| The five real bumps replay to their dispositions | `tests/schema/test_historic_evolution.py::test_three_real_bumps_replay_to_a_view`, `test_two_real_bumps_replay_to_facts` | pass: `view` for bundle 1-2, bundle 2-3, corpus 2-3; `facts` for corpus 1-2, source 1-2. Replay, not installed views, per the scope line |
| `older_majors` replaced by the `facts` disposition | `tests/corpus/test_amend_records.py::test_a_real_record_without_terms_gains_them_and_the_current_major`, `test_sealed_reads.py` | pass: real schema-1 records amend through `read_stated`; the scan finds no `older_majors` and no version comparison outside the read path |
| `corpus verify` on a million-frame index is no slower | `tests/corpus/test_read_cost.py`; scratch timing of `open_frame_bundle` on the kept bundle grown to 1,000,000 frames, best of three | pass: 2.15 s at `a70ff78` in a temporary worktree, 2.14 s after, same host and run |
| `make ci` | Each target's command run directly, as `make` is not installed: `ruff format --check`, `ruff check`, `mypy`, radon, complexipy, `bash -n`, shellcheck, `doc_links`, `plan_integrity`, `schema.history --base-ref origin/main`, pytest | pass: 1444 tests |
| `make quality` additions | pytest with coverage; `pymarkdown scan`; `uv build` | pass: 97.77% (floor 90%); 0 Markdown findings; the wheel holds `result/command/1.3.0.json` and the new modules |

## Audit handoff

Reviewed: every changed module and test, the registry, meta-schema and command-contract change,
the oracle's verdict on 1.2.0 to 1.3.0, the read path's order (seal, kind, disposition), and each
caller of a sealed read. The audit found two defects, fixed in this change with a test each: a stated
shape was tested only at the current major, so a later view of major 3 would have served a pre-terms
manifest as evidence (`test_a_view_never_serves_a_shape_that_lacks_source_terms`); and the floor
matched evolution's reason text by literal, now named constants.

- `AUD-record-read-window-1`, nonblocking: `PROTECTED_PROPERTIES` names judgments and revisions by
  property name in code, which the contracts could state. Owner: `data-contracts-audit`, whose
  execution path now states it.
- `AUD-record-read-window-2`, nonblocking: `check_view` runs in tests only, so a view's undeclared
  derivation is caught on kept records and not on every read. Owner: `data-contracts-audit`, which
  now states the decision.
- `AUD-record-read-window-3`, nonblocking: the projection and stated-shape tables are code that knows
  a version. Owner: `data-contracts-audit`, whose execution path now starts from both.
- `AUD-record-read-window-4`, nonblocking: a corpus projection holds no `source_manifest_sha256`, which
  `amendment-impact-report` needs to find versions pinning a replaced record. Owner:
  `amendment-impact-report`, whose execution path now adds it; `unlinked-version-report` now names
  `read_comparable` for its scan.
- `AUD-record-read-window-5`, dropped: a predecessor with no projection ends the chain, so versions
  behind it are unknown and not listed one by one. It is reported as `not_compared`, as a removed
  manifest is, and reading its link would interpret a format this tool does not know.
- `AUD-record-read-window-6`, dropped: module size, a chore. The code was later reorganized into
  smaller logical modules.

## Close or resume

Every gate passed. The task left the plan; `unlinked-version-report` and `amendment-impact-report`
no longer wait for it, and `data-contracts-audit` states the routed items. The specification
(sections 17.2 and 17.4), `contracts/README.md`, the authoring guide and both current pages describe
the read window. Plan counts after: 129 open tasks (107 agent, 22 human); next agent
`decode-policy-reimport (optional)`, next human `select-development-workload`. `data-contracts` stays
`planned`, with open work.
