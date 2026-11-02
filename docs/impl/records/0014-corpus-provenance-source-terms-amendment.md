# Source terms amendment

## Task and scope

- Id / capability: `source-terms-amendment` / `corpus-provenance`
- State: accepted
- Source: plan task, owner request at `d7a91a6`, clean tree.
- Plan counts at start: 110 tasks (88 agent, 22 human). Next agent: `source-terms-amendment`; next
  human: `select-development-workload`.
- Accepted task:

```markdown
#### source-terms-amendment (optional)

Changed terms cannot be recorded: `import` refuses them as `IMPORT_CONFLICT` and the corpus keeps
verifying, until an operator deletes a sealed record by hand, and the stored source with it.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track import --amend-terms` records new rights and sensitivity for an
  imported source, and every corpus version pinning the old record then refuses. A plain import of
  changed terms names the terms that differ and this command.
- Scope boundary: Rights and sensitivity of one imported source, for the same bytes and decoder,
  including a record of a `facts` major that lacks required terms. Stored bytes stay untouched and
  nothing is decoded. The replaced record is kept beside the new one. Frames stay on disk.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`,
  `$DATA_DIR/import/<source-sha256>/`.
- Execution path: Add the flag to `import`, re-seal the existing record with the declared terms under
  one atomic replace, and keep the replaced record under its own seal.
- Acceptance gates: A source amended to `restricted` makes `corpus verify` refuse with
  `SOURCE_RECORD_CHANGED`, with its stored source byte-identical. A declaration that changes the file,
  capture facts or decoder stays `IMPORT_CONFLICT`. A repeat reports `unchanged`, an interrupted
  amendment leaves one whole record, and a replaced record stays readable.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: one, made during implementation under the AGENTS.md rule that a wrong boundary is
  amended in the same change. It reverses a stated gate, so the owner has it to confirm. Reason: read
  literally, "same decoder" compares the record with the installed decoder. Every real schema 1
  record predates policy revision 3, so that check refuses all of them, which contradicts the scope
  line naming those records. `--redecode` cannot go first, because it carries terms over and those
  records have none, so the only exit left would delete the stored bytes, which is what
  `AUD-record-version-refusal-4` routed here. It would also make a withdrawal after any decoder
  upgrade wait for a full decode of the material being withdrawn. Revised lines:

```markdown
- Scope boundary: Rights and sensitivity of one imported source, including a record of a `facts`
  major that lacks required terms. Stored bytes stay untouched and nothing is decoded. The record
  keeps the decode policy it states, and the installed decoder is not consulted. The replaced record
  is kept beside the new one. Frames stay on disk.
- Acceptance gates: A source amended to `restricted` makes `corpus verify` refuse with
  `SOURCE_RECORD_CHANGED`, with its stored source byte-identical. A declaration that changes the file
  or capture facts stays `IMPORT_CONFLICT`, and no amendment changes a record's decoder. A repeat
  reports `unchanged`, an interrupted amendment leaves one whole record, and a replaced record stays
  readable.
```

## Implementation

`src/ss_track/corpus/amendment.py` is new and holds `amend_source_terms` and `AmendmentResult`.
`ss-track import --amend-terms` selects it in `cli.py`. `importer.py` gains `declared_terms`,
`changed_facts`, `SEQUENCE_KEYS` and a conflict that names the terms and the command.

The new record is the old one with `rights`, `sensitivity` and `schema_version` replaced. The old
record is written to `replaced/<seal>.json` first and the manifest is then replaced by rename, so a
run killed at any point leaves one whole record and a rerun finishes the work. An exclusive `flock` on
`import/.amendment.lock` serializes amendments, because two at once could otherwise lose a record
neither had kept. It blocks rather than refuses, as an amendment takes milliseconds. A killed run's
scratch files are cleared under that lock.

Decisions beyond the task text:

- **No link field and no clock in the record.** A `replaces` field would give an amended record an
  identity no import can reach. Without it an amended record equals a fresh import of the same
  declaration, and restoring old terms restores the old seal and with it the pin.
- **Stored bytes are not read.** `corpus verify` already works without them, and a withdrawal may
  follow their removal. Refusing there would leave the corpus verifying on withdrawn rights.
  `corpus build` hashes them again regardless.
- **A declared hash can name the source.** The original may be gone, which is common after a
  withdrawal. With the file present its bytes must match. `sha256_declared` is carried over: it
  states what was declared at import.
- **A file with no record is `IMPORT_CONFLICT`,** as the gate states, and never an import.
  `SOURCE_NOT_IMPORTED` was considered and fits equally well, but the gate names the code.
- **`decode_policy_current` in the result** tells the operator that a record stays out of `corpus
  build` until re-decoded.
- **Older majors are accepted by one constant.** Schema 1 is amendable when it holds every decoded
  fact of the current major. Real records show two shapes under that number, so `SEQUENCE_KEYS` and
  the `DecodePolicy` fields decide, and a record short of them is refused by name. Stamping it schema
  2 would make a false claim that a contract would later reject at write time.

`changed_terms` treated an absent key and an explicit `null` as equal, so a `retain_until: null`
gained from an older record went unnamed. It now tells them apart, and
`test_a_real_record_without_terms_gains_them_and_the_current_major` covers it.

Two real records enter `tests/corpus/records/`, written by the code of `0238d55` and `d6b704d`.
`record-read-gate` adds the other majors there. `test_verify_rights.py` now amends terms through the
real command and keeps the delete and re-import route only for a change the command refuses.

Compatibility: `--amend-terms` is a new flag and `amend_source_terms` a new public function. A plain
import's result is unchanged. `IMPORT_CONFLICT` gains `changed_terms` in its details, and its message
changes when the terms alone differ. Dependencies are unchanged. See
[Withdrawing rights](../current/corpus.md#withdrawing-rights).

## Acceptance evidence

Real-record evidence came from one-off runs: each commit was exported with `git archive` and its own
code imported one generated Matroska clip, and the current code then amended the result.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Amended to `restricted` refuses, bytes identical | `test_an_amendment_to_restricted_refuses_the_pinning_corpus_and_keeps_the_bytes`, plus the CLI flow: import, build, stage, verify, amend, verify | pass: `SOURCE_RECORD_CHANGED` naming `rights.sharing` and `sensitivity.level`, exit 1. Stored hash `21e4e48e3f...` equal before and after, 24 frames left on disk |
| Nothing is decoded | Same test, with `inspect_media` raising | pass |
| Changed file stays `IMPORT_CONFLICT` | `test_an_amendment_cannot_change_or_import_a_file` | pass: no import, evidence unchanged. A file contradicting its own declared hash stays `SOURCE_HASH_MISMATCH`, as in a plain import |
| Changed capture facts stay `IMPORT_CONFLICT` | `test_an_amendment_that_changes_capture_facts_records_nothing` | pass, for `capture` and for clock evidence |
| Decoder (amended gate) | `test_an_installed_decoder_change_neither_blocks_nor_enters_an_amendment` | pass: policy and sequence carried verbatim, `decode_policy_current: false` |
| Repeat reports `unchanged` | `test_a_repeat_reports_unchanged_and_keeps_one_replaced_record`, and the CLI flow | pass |
| Interrupted amendment leaves one whole record | `test_a_killed_amendment_leaves_one_whole_record_and_a_rerun_finishes_it` | pass: a subprocess killed by `os._exit` at each of the two writes. Process death only: power loss was not tested |
| Replaced record stays readable | `test_a_replaced_record_stays_readable_under_its_own_seal`, `test_restoring_the_old_terms_restores_the_pin_and_keeps_both_records` | pass: byte-identical to the old manifest, read through its seal |
| Plain import names the terms and the command | `test_a_plain_import_of_changed_terms_names_them_and_the_command` | pass. Not offered for a change it cannot record |
| A record of a `facts` major | Real schema 1 record of `d6b704d`, amended, compared by `cmp` with the record `129a350` writes from the same declaration | pass: byte-identical, so the amended record is exactly a real schema 2 record of policy revision 2. `corpus build` then refuses it with `DECODE_POLICY_MISMATCH`, as that policy requires |
| Earliest schema 1 shape | Real record of `0238d55`, in `test_a_real_record_short_of_the_current_major_is_refused_by_name` | pass: `RECORD_SCHEMA_UNSUPPORTED` naming four missing facts, record untouched |
| Amended record equals a fresh import | `test_an_amended_record_is_the_one_a_fresh_import_would_write` | pass: byte-identical across two data roots |
| Concurrent amendments lose nothing | `test_concurrent_amendments_lose_no_record` | pass with 8 threads. Each thread opens its own lock description, so `flock` excludes them as it does processes |
| Whole gate | `make quality` | pass: exit 0, 689 passed, 0 spec-plan findings, 0 broken links, package built |

## Audit handoff

- `AUD-source-terms-amendment-1`: `--redecode` must not assume a record has terms to carry, and a
  record of the `0238d55` shape can use neither command alone. Owner: `decode-policy-reimport`,
  amended in this change.
- `AUD-source-terms-amendment-2`: `amendment.py` holds in one constant the older major it accepts,
  which the registry will own, and the read gate must let it read that major. Owners:
  `record-read-gate` and `record-read-window`, amended in this change. `AUD-record-version-refusal-4`
  closes here for every record that holds the current decoded facts.
- `AUD-source-terms-amendment-3`: after an amendment nothing lists the corpus versions that pin the
  old record, so one nobody verifies goes unnoticed. Owner: `amendment-impact-report`, added in this
  change with the specification amended.
- Dropped: the replaced records carry no order or date. A clock in a sealed record would break
  repeatable imports, and each corpus manifest already pins the seal and copies the terms it rested
  on, so what a corpus relied on stays answerable. File times remain.
- Dropped: `write_sealed` does not sync the directory after a rename, so power loss could lose a kept
  copy while the new manifest survives. The current record stays whole either way, and this applies to
  every sealed record, so it needs no work specific to this task.
- Dropped: an amendment reaches one data root. Another host keeps its record, and `corpus compare`
  already reports a source record that differs. The limit is stated in the current page.

## Close or resume

Every gate passed under the amended task text, which the owner has to confirm. Next action: none.
[Corpus](../current/corpus.md) is updated, and the task is removed from the plan. Plan after this
change: 110 tasks (88 agent, 22 human), one removed and `amendment-impact-report` added.
Next agent: `decode-policy-reimport`; next human: `select-development-workload`.
`corpus-provenance` stays `planned`. Nothing was committed.
