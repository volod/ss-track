# Contract-enforced readers

## Task and scope

- Id / capability: `contract-enforced-readers` / `data-contracts`
- State: accepted.
- Source: plan task; start commit `d43011703ae086608bd1e98d06dfbd26a8ba54a6`; working tree clean.
- Plan counts at start: 131 open tasks (109 agent, 22 human); next agent by priority:
  `decode-policy-reimport (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### contract-enforced-readers

A format stays stated twice, in its contract and in hand-written readers, so the two can disagree.

- Serves: `data-contracts` -- [Enforcement](../design/spec.md#174-enforcement)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A declaration on read and a record before sealing are checked for structure
  by their contract alone, with the same refusal codes, and a refusal of an old record names the
  migration from its change log.
- Scope boundary: Structural rules move out of `Fields`, `read_recipe` and the declaration readers.
  Cross-field and cross-file rules stay in code. A sealed read checks seal, kind and major only. No
  record byte changes.
- Data and artifact paths: `src/ss_track/corpus/`, `src/ss_track/schema/`, `tests/corpus/`,
  `tests/schema/`.
- Execution path: Reuse the strict declaration parser and its duplicate-key refusal, non-finite
  refusal and date normalization, validate each declaration, validate before `seal`, and reduce
  `Fields` to typed access. Remove the key check in `terms.py`, which stands in for a version the
  contract now states.
  Replace `RecordFormat.older_remedy` with the migration text from each change log, so a remedy has
  one source. `SHA256_PATTERN` and `IDENTIFIER_PATTERN` in `fields.py` go with the rules they serve,
  and so do the checks in `tests/schema/test_agreement.py` that hold them equal to `shared/types`.
- Acceptance gates: Every existing refusal code holds across the existing suite. `1.0` as an index, a
  non-finite number, a repeated key and an unquoted date each keep today's result. A writer defect is
  `RECORD_INVALID` before anything is sealed. `corpus verify` on a million-frame index takes no longer
  than before, shown by a benchmark fixture.
- Documentation target: [Current implementation](current.md#areas), pages `current/contracts.md` and
  `current/corpus.md`.
```

- Amendments: none to the task text. One execution step was not taken, for the reason under
  [Implementation](#implementation): the key check in `terms.py` stays, and `record-read-window` now
  owns removing it.

## Implementation

`src/ss_track/schema/enforce.py` is the runtime entry to the installed contracts, read once per
process. `read_declaration` parses YAML with the existing strict parser in `schema/_documents.py`
(repeated keys, non-finite numbers, non-JSON values, date normalization) and validates the whole
document under the newest frozen version of the reader's major. `require_record` validates a record,
in its written JSON form, under the newest frozen version of the major it stamps. `corpus/sealed.py`
`seal` calls it before it hashes anything, with a well-formed stand-in seal, so a writer defect,
including a `NaN`, is `RECORD_INVALID` and nothing is written. `read_sealed` is unchanged: seal, kind
and major only.

`corpus/fields.py` is typed access to a validated mapping. The closed-key check, vocabularies, index,
hash and identifier patterns, the non-finite check and `schema_version` left it, with
`load_yaml_mapping`, `SHA256_PATTERN` and `IDENTIFIER_PATTERN`. `read_recipe` reads a recipe whole,
because each transform's contract branch states its parameters and bounds; `MAX_SEED`, `MAX_SPRITES`,
`MAX_NOISE` and the per-transform reader table are gone. The declaration readers lost `RIGHTS_BASES`,
`SPLITS` and `RANGE_STATUSES`. `SHARING_SCOPES` and `SENSITIVITY_LEVELS` stay, because the rights
checks compare by an order no contract states. Rules in code are the contracts' `x-rules` (range
evidence, self-supersession, a non-empty window, an absent range status meaning `unknown`) and two
text rules no declaration major states: whitespace-only text, and a value YAML read as a date where
text belongs. The second keeps today's result for an unquoted `holder: 2024-01-05`; normalized dates
are `strict_yaml.YamlDate`, a `str` that validates as one, and only `Fields.nullable_date` takes it.

`RecordFormat` holds kind and major. An older record's remedy is the change log's `migration`: the
retired major's entry, else the first major transition after it, else "restore from a trusted copy"
for a major no version wrote. `contracts/meta/registry.json` requires `migration` on each retired
major, and `contracts/registry.yaml` states it for all eight, with the text the code held before.
`contracts list` reports it, so `result/command` 1.2.0 was frozen with `ss-track contracts freeze`
(minor: one optional property). Run and corpus ids from the command line are checked by
`is_shared_type("identifier", ...)`, so `shared/types` is the pattern's one statement, and the
pattern checks in `tests/schema/test_agreement.py` were removed.

The validator now reports a tagged `oneOf` through the branch its tag selects
(`schema/strict.py`), which `branch_tags` and `union_tag` moved down from `schema/dialect.py` to
serve. Without it a wrong `seed` read "not valid under any of the given schemas". `contracts
validate` and runtime share `require_conforming`, which names a wrong `schema_version` first.

The key check in `require_retention` was not removed. It is the only thing that refuses the kept
`corpus-schema-3-d6b704d.json`, a schema-3 corpus manifest sealed before source terms existed. No
major tells it apart, and a sealed read does not walk fields, so removing the check would turn
`RECORD_SCHEMA_UNSUPPORTED` into a `KeyError` and fail the first acceptance gate. Its docstring
now says so, and `record-read-window` owns the route.

Rejected: validating a sealed record on read, which the specification forbids and the benchmark gate
would catch; normalizing dates only at `format: date` positions, which needs a schema walk per value
where a marker type needs none; keeping a hand-written message per keyword, which would state each
rule twice again.

Tests: `tests/_sealing.py` seals a fixture without its contract, because production `seal` now
refuses the damaged records read tests need. Message expectations that quoted hand-written wording
now quote the contract violation or its JSON pointer; every refusal code is unchanged.
`tests/corpus/test_read_cost.py` is the benchmark fixture, `tests/schema/test_enforce.py` covers the
entry points, and new cases in `test_sealed.py`, `test_declaration.py` and `test_strict.py` cover
writer defects, the parser's results and tagged-union reports. Current state:
[contracts](../current/contracts.md#runtime-enforcement) and
[corpus](../current/corpus.md#reading-sealed-records).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Every existing refusal code holds across the existing suite | `.venv/bin/python -m pytest` | pass: 1398 passed. Assertions on refusal codes unchanged; message expectations that quoted removed wording now quote the contract violation |
| `1.0` as an index keeps today's result | `test_declaration.py::test_an_index_must_be_a_true_integer` (`1.0`, `1e0`, `true`) | pass: `MANIFEST_INVALID` |
| A non-finite number keeps today's result | `test_declaration.py::test_bad_additions_are_refused[nan,infinity]` | pass: `MANIFEST_INVALID`, message names "finite" |
| A repeated key keeps today's result | `test_declaration.py::test_bad_additions_are_refused[duplicate-key]` | pass: `MANIFEST_INVALID` |
| An unquoted date keeps today's result | `test_an_unquoted_date_keeps_today_s_result_where_a_date_belongs`, `..._refusal_elsewhere`, `test_an_unquoted_date_is_not_a_corpus_name` | pass: accepted as ISO text in `retain_until`; refused as `holder` or `corpus_id`; impossible dates and timestamps refused |
| A writer defect is `RECORD_INVALID` before anything is sealed | `test_sealed.py::test_a_writer_defect_is_refused_before_anything_is_sealed`, `test_a_number_no_json_holds_is_refused_before_a_seal_is_computed` | pass: contract break, unannounced key, float or unfrozen major, unregistered kind, tuple shape and `NaN` |
| No record byte changes | `test_sealed.py::test_seal_keeps_the_seal_of_a_kept_record`, `tests/schema/test_hash_stability.py`, `test_historic_records.py` | pass: the kept frame set reseals to its own bytes, the real frame-set producer replays to retained bytes and seal, and every kept record reads as before |
| `corpus verify` on a million-frame index takes no longer | `tests/corpus/test_read_cost.py`; scratch timing of `open_frame_bundle` on the kept bundle grown to 1,000,000 frames, best of three | pass: 2.70 s at `d430117`; 2.70 s and 2.76 s in two runs after, with the read path's code unchanged, so run-to-run noise. The test fails if a sealed read reaches the validator. Frame hashing is unchanged I/O and was not timed |
| `make ci` | Each target's command run directly, because `make` is not installed on this host: `ruff format --check`, `ruff check`, `mypy`, radon, complexipy, `bash -n`, shellcheck, `doc_links`, `plan_integrity`, `schema.history --base-ref origin/main`, pytest | pass |
| `make quality` additions | pytest with coverage; `pymarkdown scan`; `uv build` | pass: 97.86% (floor 90%); 0 Markdown findings; wheel holds `schema/enforce.py` and `result/command/1.2.0.json` |

## Audit handoff

Reviewed: every changed module and test, the registry and meta-schema change, the freeze output and
the read path. The audit found that `seal` hashed before it validated, so a `NaN` ended in a
`ValueError`; it was fixed in this change, and a test holds it.

- `AUD-contract-enforced-readers-1`, nonblocking: the source-terms key check in `corpus/terms.py`
  remains as the only refusal of a schema-3 corpus manifest sealed without terms. Owner:
  `record-read-window`, whose execution path now states it.
- `AUD-contract-enforced-readers-2`, nonblocking: `Fields.text` refuses whitespace-only text and a
  value YAML read as a date, which `declaration/recording` 2.0.0 and `declaration/corpus` 3.0.0 do not
  state, so `contracts validate` accepts what a reader refuses. Owner: `data-contracts-audit`, whose
  execution path now states it.
- `AUD-contract-enforced-readers-3`, dropped: validating a million-frame bundle before sealing takes
  about 32 s, measured with `require_record` on the grown kept bundle. Staging decodes and writes each
  of those frames, and `corpus hashes` reads each, so the cost changes no result and no run's order of
  magnitude.
- `AUD-contract-enforced-readers-4`, dropped: declaration refusal messages now use the validator's
  wording ("Additional properties are not allowed") instead of hand-written text. Codes are
  unchanged, each message names the JSON pointer, and details list up to 20 violations; wording is
  not part of the result contract.

## Close or resume

Every gate passed. A chore was done in the same change: one line in
`docs/guide/authoring-contracts.md` over the Markdown length limit before this task was wrapped, so
`make quality` passes. The task left the plan; `record-read-window`, `dataset-descriptor` and
`telemetry-bundle-store` dropped it as a dependency, and the specification states the retired-major
migration and the two reader text rules. Plan counts after: 130 open tasks (108 agent, 22 human);
next agent `decode-policy-reimport (optional)`, next human `select-development-workload`.
`data-contracts` stays `planned`, with open work.
