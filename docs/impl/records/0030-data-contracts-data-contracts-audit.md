# Data contracts group audit

## Task and scope

- Id / capability: `data-contracts-audit` / `data-contracts`
- State: accepted.
- Source: plan task; starting commit `f571624`; working tree clean.
- Plan counts at start: 125 open tasks (103 agent, 22 human); next agent
  `decode-policy-reimport (optional)`, next human `select-development-workload`.
- Accepted task:

```markdown
#### data-contracts-audit (optional)

Contracts, readers and disposition rules arrive in separate tasks, so a format can still be stated
twice and an older-major rule can sit in code the registry should own.

- Serves: `data-contracts` -- [Reading older records](../design/spec.md#reading-older-records)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Each format has one statement, its contract, and each older major has one
  stated route, with no record byte moved.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `tests/corpus/records/`,
  `contracts/`, `src/ss_track/schema/`, `tests/schema/`, `docs/guide/authoring-contracts.md`,
  `contracts/declaration/`, `contracts/record/`, `contracts/result/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from the
  code that still knows a version: `SEQUENCE_KEYS`, the projection table in `corpus/projections.py`,
  the stated-shape table in `corpus/read_window.py`, and any structural rule left in a hand-written
  reader. `PROTECTED_PROPERTIES` in `schema/dispositions.py` names operator judgments and algorithm
  revisions by property name, a rule the contracts could state as an annotation: state it there in
  each next major or keep it as a named code rule. A view's purity and undeclared derivations are
  checked by `check_view` in tests only, because walking every value of a million-frame bundle on
  each read costs seconds: decide whether a view's first read should check it. `Fields.text` in
  `corpus/fields.py` refuses whitespace-only text and a value YAML read as a date, which
  `declaration/recording` 2.0.0 and `declaration/corpus` 3.0.0 do not state, so `contracts validate`
  accepts what a reader refuses: state both in each next declaration major or keep them as named
  reader rules. Then replay every
  record in `tests/corpus/records/` and compare the change log with the real bumps.
- Acceptance gates: Every historic record reads under its disposition with its bytes and seal
  unchanged, a static search finds no version check outside the read path, and `corpus verify` on a
  million-frame index is no slower than before, as `tests/corpus/test_read_cost.py` shows. Every
  finding is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding
  nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), pages `current/corpus.md` and
  `current/contracts.md`.
```

- Amendments: none.

## Implementation

Reviewed together: records 0016 to 0029 and their audit handoffs, specification section 17, the
contracts and corpus current pages, the authoring guide, `contracts/`, `src/ss_track/schema/`, the
read path and every writer in `src/ss_track/corpus/`, and their tests. Findings by question:

**Integrity.**

- The not-blank and YAML-date text rules lived in `Fields.text` only, so `contracts validate`
  accepted what a reader refused, and a capture fact took an unquoted date that a text field
  refused. The date rule now sits in the validator: `schema/validation/strict.py` accepts a
  `YamlDate` only where its node states `format: date`, so readers and `contracts validate` refuse
  it alike. The dialect cannot state "holds a character other than whitespace" over any script, so
  `declaration/recording` 2.1.0 and `declaration/dataset` 1.1.0, frozen with `ss-track contracts
  freeze`, state it under `x-rules` as `text` on each of their 11 free-text properties, and
  `Fields.text` enforces it under that name. `declaration/corpus` holds no free text. The `YamlDate`
  docstring claimed YAML rewrites `2024-1-5` into `2024-01-05`; PyYAML reads `2024-1-5` as text, so
  the stated reason is now the true one: a YAML 1.1 and a YAML 1.2 reader type the value
  differently.
- Section 17.4 names a transform revision among the algorithm revisions no view restates, and
  `REVISION_PROPERTIES` lacked `transform_revision`, which a corpus case holds outside any protected
  parent. A view deriving `/generated_cases/*/transform_revision` passed, and a major changing it
  floored at `view`. It is protected now, with a test for each.
- Record 0019 stayed `active` with its final `make ci` pending; this audit's run closes it.
- Every handoff that named this audit is closed below. The handoffs to other owners
  (`decode-policy-reimport`, `amendment-impact-report`, `unlinked-version-report`,
  `corpus-provenance-audit`, `event-schema-contract`) still name code that exists.

**Repetition.**

- `SEQUENCE_KEYS` and `_POLICY_KEYS` restated, from today's dataclasses, which decoded facts a source
  record holds, a fact `record/source-manifest` already requires. The amendment now asks the
  contract: `sealed.seal_violations` checks the record it would write, and a `facts` record short of
  a fact is `RECORD_SCHEMA_UNSUPPORTED` listing the contract `violations` instead of `missing_facts`.
  The refusal code is unchanged, and the check also serves the re-decode that
  `decode-policy-reimport` adds.
- A record's kind and major were stated by a constant pair, a `RecordFormat`, and again by hand in
  each of six writers. `RecordFormat` is now the one statement and `stamp()` writes it; every kind is
  in `corpus/records/kinds.py`; hash comparison gained its `RecordFormat`, which a test built by hand.
- The descriptor repeated the bundle read and its hash check from `frames.py`, the frame-row layout
  of `descriptor_public.py`, the split vocabulary of the corpus contract, contract names, the
  newest-version rule and the contract-set paths. `frames.read_bundle_record`,
  `descriptor_rows.frame_rows`, `SPLITS` (held to the contract by a test), `records_by_kind`,
  `Contract.newest`, `relative_path` and the store's file-name constants replace them, and one
  contract set serves a description.
- JSON pointer unescaping was written three times; `evolution.pointer_parts` beside `pointer` serves
  all. `versions[-1]` stood in for `newest()` five times, and `freeze.py` looked a contract up twice
  and loaded the set twice for one diff. The change classes are named once in `schema/registry/store.py`.
- Kept, with reason: `commands._require_seal` and `sealed._read_intact` both compare a seal, because
  `ss_track.schema` must not import `ss_track.corpus`; the comparison is one call of `seal_of`.

**Explicit patterns.** Four readers converted a missing key of a sealed record into
`RECORD_TAMPERED` by hand, with three messages; `sealed.incomplete_record` is the one guard.
`_read_document` keeps its private name on purpose: `test_sealed_reads.py` holds that the deep check
exposes no reader.

**Naming.** The floor's refusal said "operator judgment" while it also floors algorithm revisions;
it names both. No other drift found.

**Algorithms.** Measured with a script that was not kept, best of three, the starting commit's code
and this change's run alternately on this host. Opening the million-frame bundle took 2.675 s and
2.660 s before and 2.680 s and 2.676 s after. Validating a 100k-frame bundle before sealing took
3.130 s and 3.135 s before and 3.106 s and 3.117 s after. Two first versions measured slower and
were changed: the date rule in every validation cost 5% of pre-seal validation (3.230 s against
3.076 s), so only YAML documents take it (`YamlValidator`), since a JSON record cannot hold a YAML
date; and a `content_frame_index` call per frame cost about 2% of the million-frame open, so that
loop keeps the expression inline. `tests/corpus/records/test_read_cost.py` still shows that a
sealed read walks no contract. After the read-path split below, three more alternating runs gave
2.636 s to 2.683 s before and 2.649 s to 2.674 s after for the open, and 3.060 s to 3.135 s before
and 3.110 s to 3.170 s after for validation, overlapping ranges on a code path the split did not
change.

**Gaps.** Untested before: that each projection reads its era's kept record, that each installed
view passes `check_view` on its kept record, that each writer's major matches its contract, and that
the static scan sees a major named through `VERSION_FIELD`. Each has a test now.

**Ideas.** None beyond the fixes above.

Decisions the task asked for:

- `PROTECTED_PROPERTIES` stays a named code rule: the read path checks a view's derived pointers by
  name with no contract walk, and an annotation would need a dialect widening and a new version of
  every contract to protect nothing more. A test holds each name to a property an installed contract
  states, and the authoring guide says a new judgment or revision property joins the list.
- `check_view` stays out of the read path. It walks every value, seconds on a million-frame bundle,
  and a view is fixed code, so a first read proves no more than the kept record of its major, which
  `test_historic_records.py` now checks for every installed view.
- The projection and stated-shape tables stay read-path code: a retired major has no frozen contract
  to state a projection, and section 17.4 places a shape's one test on the read path.
- Replay of `tests/corpus/kept_records/`: each kept record read through `read_sealed`, `read_stated`
  and `read_comparable` gives the disposition its change log states (bundle and corpus majors 1 and
  2 `retired`, source major 1 `facts`, the schema-3 corpus without terms the `facts` shape, current
  majors as evidence), and no byte or seal moved. Against the real bumps, source 1 to 2 is `facts`
  as warranted; corpus 1 to 2 warranted `facts` and the three `view`-warranted bumps are `retired`,
  which is stricter and correct while no retained record needs them.

**Code organization.** At the user's request, the code was reorganized into smaller logical modules
for readability, with no behavior change. The package root holds only the `cli.py` entry point:
shared primitives moved to `ss_track/core/` and the command groups to `ss_track/commands/`. `corpus`
and `schema` group their modules into subpackages by responsibility (`corpus/records/` holds the
sealed-record read path and writer, for example), large modules and test files were split along
their responsibilities, repeated test helpers were merged, and tests mirror the subpackages, with
the kept real records in `tests/corpus/kept_records/`. Every test still runs. Tests exercise current
public interfaces, algorithms and protocols: tests of a former API, a superseded search kept only
for comparison and hand-built stand-ins for real kept records were removed, and tests that reached
into private helpers now go through the public function with a fake at the third-party boundary.

Compatibility: `declaration/recording` 2.1.0 and `declaration/dataset` 1.1.0 change no accepted
value. A capture fact written as an unquoted `YYYY-MM-DD` is now `MANIFEST_INVALID`, as a text
field already was. The amendment refusal for a record short of a
decoded fact names `violations` instead of `missing_facts`, with the same code. No sealed byte,
hash, score or refusal code moved, and no dependency changed. Current pages:
[contracts](../current/contracts.md) and [corpus](../current/corpus.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Historic records read under their disposition, bytes and seal unchanged | `tests/corpus/records/test_historic_records.py`; replay over every file in `tests/corpus/kept_records/` through the three read entries (script not kept) | pass: 13 records, each as its change log states, every seal intact and every file byte-identical |
| No version check outside the read path | `tests/corpus/records/test_sealed_reads.py`, now also matching `VERSION_FIELD` | pass |
| `corpus verify` on a million-frame index no slower | `tests/corpus/records/test_read_cost.py`; timing above | pass: no contract walk on a read; open 2.680 s and 2.676 s against 2.675 s and 2.660 s, within run-to-run spread |
| Descriptor bytes unchanged by the refactor | Both visibilities described on one fixed data root by the starting commit and by this change, digest per file (script not kept) | pass: every file outside `contracts/` identical, measured before the new minors were frozen; the minors then change only the copied set and `contracts.json` |
| Findings fixed, routed or dropped | Audit handoff below | pass |
| `make quality` | `make quality` | pass: tests, coverage floor, format, lint, typing, complexity, shell, links, spec-plan, contracts, Markdown and the package build |
| `make ci` | `make ci` | pass |

## Audit handoff

Every finding was fixed in this change, and no plan task was added. Each item another record routed
here is closed:

- `AUD-contract-enforced-readers-2` (`Fields.text` rules not in a contract): fixed, as above.
- `AUD-record-read-window-1` (`PROTECTED_PROPERTIES` in code): kept as a named code rule, with a
  test, and `transform_revision` added.
- `AUD-record-read-window-2` (`check_view` in tests only): kept in tests, now run on every installed
  view's kept records.
- `AUD-record-read-window-3` (version tables in code): kept on the read path, each projection now
  held to its kept record.

Dropped, each a chore or an observation needing no work: the two seal comparisons across the
`schema` and `corpus` boundary, and the private parser name, both kept for the reasons above.

## Close or resume

Every gate passed. The task left the plan, which leaves the `data-contracts` group with no open task,
so the capability is `shipped` in the registry with its link to the
[contracts page](../current/contracts.md). Both current pages, the specification's section 17.4 and
annotation table, the authoring guide and `contracts/README.md` describe the result. Record 0019 is
closed with this run's evidence. Plan counts after: 124 open tasks (102 agent, 22 human); the next
tasks by lane priority stay `decode-policy-reimport (optional)` and `select-development-workload`.
