# Record read gate

## Task and scope

- Id / capability: `record-read-gate` / `data-contracts`
- State: accepted
- Source: plan task, owner request at `3fe3d8d`, clean tree on `st-04-data-contracts`.
- Plan counts at start: 134 tasks (112 agent, 22 human). Next agent: `decode-policy-reimport`; next
  human: `select-development-workload`.
- Accepted task:

```markdown
#### record-read-gate

Four of nine sealed reads check no schema, an older source is misreported as `IMPORT_CONFLICT`, a
refusal never says what to do, and an unreadable predecessor fails a successor where section 4.1 says
it is reported.

- Serves: `data-contracts` -- [Reading older records](../design/spec.md#reading-older-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: One read path checks seal, kind and schema for every sealed record, and a
  refusal states the record, its major, whether it is older or newer, and the remedy.
- Scope boundary: Exact-version acceptance stays, and so does every refusal code except the import
  misreport. No registry, view or new dependency. A real record of each historic major enters the
  tests.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `tests/corpus/records/`.
- Execution path: Replace the `read_sealed` and `require_schema` pair with one function, covering
  `generated.py`, the existing-record reads in `builder.py` and `importer.py`, and `host_hashes.py`.
  Add `not_compared` reason `other_schema` for a predecessor's frames. Keep `amendment.py` able to
  read the older major it exists to replace, through the same function. Export each historic commit,
  have its own code write records from a generated clip, and keep only the JSON with a note of the
  commit, beside the two source records already there.
- Acceptance gates: A static test finds no sealed read outside the one function. Re-importing over an
  older source record is `RECORD_SCHEMA_UNSUPPORTED`, naming `--amend-terms` as its remedy, and that
  command still accepts the record. A successor whose predecessor
  holds another major's bundle stages and names it under `other_schema`. An older and a newer record
  are told apart. Each kept historic record refuses by name, with no traceback.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: one, made during implementation, which the owner has to confirm. The scope line keeps
  every refusal code "except the import misreport", but the execution path also routes the
  existing-record read in `builder.py` through the gate, and that read holds the same misreport. A
  rebuild over an older corpus manifest moves from `CORPUS_CONFLICT` to `RECORD_SCHEMA_UNSUPPORTED`.
  Keeping the old code would need a catch that undoes the gate at one call site. Revised line:

```markdown
- Scope boundary: Exact-version acceptance stays, and so does every refusal code except the two
  misreports of an older record that a read of the existing record held: re-import and rebuild. No
  registry, view or new dependency. A real record of each historic major enters the tests.
```

## Implementation

`read_sealed` in `src/ss_track/corpus/sealed.py` now takes a `RecordFormat` (kind, major, older
remedy)
and replaces the `read_sealed` and `require_schema` pair, so a caller cannot read a record and
forget
the check. It verifies the seal first, then the kind, then the major, in the order section 17.4
states;
the old code read the kind before the seal. Each format has one constant beside its writer:
`SOURCE_MANIFEST`, `CORPUS_MANIFEST`, `FRAME_BUNDLE`, `FRAME_SET` and `STAGED_HASHES`.

The four unchecked reads are gone. `generated.py` and the `_commit` reads in `builder.py` and
`importer.py` pass a format, and `host_hashes.py` reuses `load_source_record`, made public from
`builder.py`, rather than a second path to the same file. `amendment.py` reads schema 1 through the
same
function with `older_majors`, and only that module may pass it.

`duplicate_frames.py` gains `other_schema`. A predecessor's bundle of another major is named per
stream and its other streams are still compared. Only `RECORD_SCHEMA_UNSUPPORTED` becomes a gap: a
damaged bundle still refuses, because that says something about the evidence and not about the tool.

Decisions beyond the task text:

- **The age is `older`, `newer` or `unstated`.** A version that is not a true integer is neither,
  and
  `type(found) is int` is exact because `True` and `1.0` compare equal to 1. The old check accepted
  both.
- **`record` stays `manifest.json`, and `kind` and `path` join it,** because three formats share
  that
  name. Paths are safe here: this is an operator's refusal, never a sealed value.
- **`accepted_schema_versions` replaces `schema_version` in the details,** because an amendment
  accepts
  two majors. Refusal codes are the stable surface, and no reader used that key.
- **An import refuses an older record before decoding.** The check sits after hashing, so an
  hours-long
  decode does not end in a refusal the record alone could give.
- **The two refusals outside the gate carry a remedy too.** `_require_current_facts` reuses
  `schema_details`, and `terms.py` names its stream. `AMEND_COMMAND` moved to `terms.py` for that,
since
  `importer.py` imports `terms.py`.

Bug found and fixed: a record holding `NaN` reached `canonical_json`, whose `ValueError` the CLI
does not
catch, so `corpus verify` ended in a traceback. An over-long integer and very deep nesting did the
same.
All are now `RECORD_TAMPERED`, by catching `ValueError` and `RecursionError` around the parse and
seal.

Reviewing the first draft found a remedy that misled: "not naming this one in `supersedes`" is the
route
`AUD-record-version-refusal-1` warns about, with no warning. The corpus remedy now states that
nothing
checks splits against that version, and tells the operator to keep each source in its split.

Thirteen kept files now sit in `tests/corpus/records/`: one real record of every major of every
format,
plus both shapes of source schema 1 and corpus schema 3. That covers both sides of all five real
bumps,
which `contract-evolution-gate` and `record-read-window` replay. `corpus-schema-3-d6b704d` confirms
the
format that entered schema 3 with no bump. A test fails when a new major has no record. `cli_root`
and
`last_record` moved to `conftest.py` rather than gaining a third copy.

Compatibility: `read_sealed` takes a `RecordFormat` and not a kind string, and `require_schema` is
gone.
Neither is exported from `ss_track.corpus`. `RECORD_SCHEMA_UNSUPPORTED` details gain `path`, `kind`,
`age`,
`remedy` and `accepted_schema_versions` and lose `schema_version`. Two cases change code, as above,
and
`not_compared` gains a reason. Dependencies are unchanged. See
[Reading sealed records](../current/corpus.md#reading-sealed-records).

Limit: acceptance is still exact, so nothing here makes an older record usable. A predecessor
*manifest* of another major stays refused at build and stage: the task covers a predecessor's
frames,
and a catch there would also turn a replaced manifest into a gap instead of `CORPUS_CONFLICT`.

## Acceptance evidence

Real records were written by each commit's own code, exported with `git archive`, from one generated
clip of 24 frames. The baseline comparison ran the real CLI on fresh data roots at `3fe3d8d` and on
this
change. One-off scripts, not kept.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| No sealed read outside the one function | `test_sealed_reads.py`: an AST scan of every module, with `test_the_scan_finds_each_way_around_the_gate` proving it fires on seven forms | pass. A static scan of direct calls: it would not see a loader reached by `getattr` |
| Re-import over an older source names the amendment | `test_a_reimport_over_an_older_source_names_the_amendment_which_then_accepts_it`, on the real `d6b704d` record | pass, with no decode run. Baseline CLI: `IMPORT_CONFLICT`. Now: `RECORD_SCHEMA_UNSUPPORTED`, `older`, found 1 |
| That command still accepts the record | Same test, then `test_a_real_record_without_terms_gains_them_and_the_current_major` | pass: `amended`, written at schema 2 |
| Successor of another major's bundle stages and names it | `test_a_predecessor_holding_another_majors_bundle_is_named_and_fails_nothing`, with a real schema 2 bundle | pass at stage and verify. Baseline: refused `RECORD_SCHEMA_UNSUPPORTED`. Now: `staged`, `not_compared` naming `other_schema` |
| Rest of that predecessor is compared | `test_a_predecessor_with_one_bundle_of_another_major_is_compared_on_the_rest` | pass: a remux of its readable stream is still `SPLIT_LEAKAGE` |
| Older and newer told apart | `test_a_refusal_states_the_record_its_major_its_age_and_the_remedy` (7 cases), `test_a_newer_source_is_told_apart_from_an_older_one` | pass. The newer record is a reseal: no real one can exist |
| Each kept historic record refuses by name, with no traceback | `test_historic_records.py`: corpus 1 and 2 through the real `stage`, `verify` and `hashes` commands, corpus 3 without terms, bundles 1 and 2, and both source shapes at build | pass: exit 1 and one JSON record each. A bundle of an older major is read directly, because no older corpus reaches it through a command |
| One read path checks seal, kind and schema | `test_the_seal_is_checked_before_anything_it_covers_is_believed`, `test_an_intact_record_of_another_kind_is_refused_by_kind` | pass |
| `NaN` regression | `test_damaged_records_are_refused`, 4 new cases | pass. Baseline CLI: traceback, `ValueError`. Now: `RECORD_TAMPERED`, exit 1 |
| Tests notice a reverted gate | One-off: each of 10 parts of the change reverted in a copy of `src/`, and `tests/corpus` run | 10 of 10 caught, each by a named test |
| Whole gate | `make quality` | pass: exit 0, 797 passed, 99% coverage, 0 spec-plan findings, 0 broken links, package built |

## Audit handoff

Reviewed: the whole diff, each sealed read, each refusal that names a schema, and every plan task
that
mentions these reads.

- `AUD-record-read-gate-1`: a predecessor's frames behind `other_schema` are unknown, so a leak
  through
  them is not caught. It is reported, not silent. Owner: `record-read-window`, amended in this
change to
  read those bundles through their projection.
- `AUD-record-read-gate-2`: the corpus remedy warns of a guard it cannot offer. Owner:
  `record-read-window`, amended in this change to rewrite it.
- `AUD-record-read-gate-3`: `older_remedy` is a hand-written string, where section 17.4 takes the
  remedy
  from a change log, and refusals do not yet state a disposition. Owners:
`contract-enforced-readers`
  for the remedy and `record-read-window` for the disposition, both amended here or stating it
already.
- `AUD-record-read-gate-4`: the only remedy for a record of the `0238d55` shape deletes its stored
  source. Owner: `decode-policy-reimport`, amended in this change to replace it.
- `AUD-record-read-gate-5`: `terms.py` still holds a schema check by key, and states no major
  because
  the number cannot tell those records apart. Owner: `contract-enforced-readers`, whose text states
it.
- Dropped: a repeated key in a record's JSON passes the seal, last value winning, so another
  language's
  reader could see a different value. A seal is not a signature, anyone who can edit a record can
  reseal it, and refusing repeats costs a Python call per object on a million-frame index.
- Dropped: `hash-comparison` has no `RecordFormat`, because nothing reads that record. Its contract
  belongs to `corpus-contract-baseline`, which names it.

## Close or resume

Every gate passed under the amended scope line, which the owner has to confirm. Next action: none.
[Corpus](../current/corpus.md) gains its reading section, the specification and data-contracts
design
are updated, and the task is removed from the plan. `contract-enforced-readers` loses the
dependency.
Plan after this change: 133 tasks (111 agent, 22 human). Next agent: `decode-policy-reimport`; next
human: `select-development-workload`. `data-contracts` stays `planned`. Nothing was committed.
