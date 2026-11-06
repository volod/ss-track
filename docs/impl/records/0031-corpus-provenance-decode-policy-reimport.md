# Decode policy reimport

## Task and scope

- Id / capability: `decode-policy-reimport` / `corpus-provenance`
- State: accepted
- Source: plan task, owner request at `110cfe5`, clean tree.
- Plan counts at start: 133 tasks (111 agent, 22 human). Next agent:
  `decode-policy-reimport (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### decode-policy-reimport (optional)

A new decode policy strands every import: `corpus build` refuses the old record with
`DECODE_POLICY_MISMATCH`, `import` refuses a new one with `IMPORT_CONFLICT`, and the only route deletes
the stored source.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track import --redecode` records an imported source under the installed
  decode policy from its stored bytes, and every corpus version pinning the old record then refuses.
  A record with no terms to carry is refused and names `--amend-terms`.
- Scope boundary: One imported source. Its stored bytes, rights, sensitivity and capture facts carry
  over unchanged, and the replaced record is kept beside the new one. Corpus versions are not rebuilt,
  and frames stay on disk. Terms are never invented: `--redecode` carries them, and only a record too
  old for `--amend-terms` alone takes them from a declaration, through both flags together.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`,
  `$DATA_DIR/import/<source-sha256>/`.
- Execution path: Decode the stored copy under the installed policy and re-seal the record under one
  atomic replace, reusing the lock and `replaced_record_path` in `amendment.py`. Replace
  `_DECODE_AGAIN_REMEDY` in that file, which still tells an operator to delete the stored source, with
  the two flags together.
- Acceptance gates: A record of an older policy gains the installed one with its stored source
  byte-identical, and `corpus build` of a new version accepts it. A corpus version pinning the old
  record refuses with `SOURCE_RECORD_CHANGED`. A stored source that no longer matches its hash is
  refused, a repeat reports `unchanged`, and an interrupted run leaves one whole record. The real
  `tests/corpus/kept_records/` schema 1 record of `d6b704d`, amended and then re-decoded, builds,
  and the one of `0238d55` builds through both flags together with no term invented.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

Added `src/ss_track/corpus/sources/redecode.py`, with `redecode_source(declaration_path, data_root,
*, amend_terms=False)`. It reads the existing record through `read_stated` (so a `facts`-disposition
major-1 record is readable), verifies the stored copy's hash against the directory's own
content-address (not the record's own, possibly stale, `source.sha256` claim), decodes it again
under `current_decode_policy()`, and builds a successor that carries `capture`, `source` and every
other section forward unchanged. `sequence` and `decode_policy` come entirely from the fresh decode.
Terms come from the declaration when `amend_terms` is true, exactly as `--amend-terms` already takes
them, and are otherwise carried from the existing record unchanged, so nothing is invented either
way. The successor is sealed and, under a `facts` disposition, checked against the current major
with `require_current_facts` before writing, under one atomic replace that reuses
`exclusive_source_lock` and `keep_replaced` from `amendment.py`.

`amendment.py`'s `_exclusive_amendment`, `_keep_replaced`, `_named_source`, `_require_current_facts`
and `_require_unchanged_facts` are now public (`exclusive_source_lock`, `keep_replaced`,
`named_source`, `require_current_facts`, `require_unchanged_facts`), reused unchanged by
`redecode.py` rather than duplicated. `_DECODE_AGAIN_REMEDY`, which told an operator to delete the
import directory and reimport, is now the public `REDECODE_REMEDY` in `amendment.py`, read by both
modules: "supply them together with ss-track import --redecode --amend-terms". It now fires from two
routes that share one check: a `facts` record still short a decoded fact after `--amend-terms` alone
(unchanged behavior, existing test updated for the new wording), and a `facts` record whose carried
terms fall short of the current major because `--redecode` alone never takes terms from a
declaration (new).

`ss-track import` gained `--redecode`, dispatched in `src/ss_track/commands/corpus.py` ahead of the
existing `--amend-terms` branch so both flags combine into one call with `amend_terms=args.amend_terms`.
`redecode_source` is exported from `ss_track.corpus`.

The command result's `status` enum (`contracts/result/command/`) gained `redecoded` as a new minor
version, `1.5.0`, frozen with `ss-track contracts freeze` (`make lint-contracts` passes); no earlier
version changed.

Compatibility: no public API removed; `AmendmentResult` is reused unchanged for a redecode's result,
with `decode_policy_current` always `True` on a `redecoded` or `unchanged` outcome, since a redecode
decodes under the policy it then reports installed. No `pyproject.toml` or `uv.lock` change; no new
dependency. Current-state page: `docs/impl/current/corpus.md`, new `## Redecoding under a new
policy` section.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Older policy replaced; stored bytes byte-identical | `tests/corpus/sources/test_redecode.py::test_an_older_policy_is_replaced_and_a_new_build_accepts_it` | pass |
| New corpus build accepts the redecoded record | same test, `build_corpus` of `pilot-v2` | pass |
| Corpus version pinning the old record refuses `SOURCE_RECORD_CHANGED` | same test, `verify_corpus_frames(CORPUS, ...)` | pass |
| Stored source no longer matching its hash is refused | `test_a_stored_source_that_no_longer_matches_its_hash_is_refused` | pass, `SOURCE_HASH_MISMATCH` |
| A repeat reports `unchanged` | `test_a_repeat_reports_unchanged` | pass |
| Interrupted run leaves one whole record, at each write | `test_a_killed_redecode_leaves_one_whole_record_and_a_rerun_finishes_it[keeping-the-old-record]` and `[writing-the-new-one]` | pass |
| Record with no terms to carry is refused, names `--amend-terms` | `test_a_record_with_no_terms_to_carry_is_refused_and_names_amend_terms` | pass |
| Real `d6b704d` (schema 1): amended, then redecoded, builds | `test_an_older_record_is_amended_and_then_redecoded_and_builds` | pass |
| Real `0238d55` (schema 1): builds only through both flags together, no term invented | `test_a_record_too_old_for_amend_terms_alone_builds_through_both_flags_together` | pass |
| CLI reports one record per call; flags parse independently | `test_the_command_reports_one_record_and_its_refusal_exits_one`, `test_the_flags_are_off_unless_given` | pass |
| `_DECODE_AGAIN_REMEDY` wording update does not regress the amend-alone refusal | `tests/corpus/sources/test_amend_records.py::test_a_real_record_short_of_the_current_major_is_refused_by_name` (updated) | pass |
| Static scan allows `read_stated` in `redecode.py` too | `tests/corpus/records/test_sealed_reads.py` (updated allowlist) | pass |
| `make ci` | format, lint, typecheck, complexity, shell-lint, doc-links, spec-plan, contracts, full test suite | pass, 1654 passed, 1 skipped |
| `make lint-md` | Markdown lint and link check | pass |

## Audit handoff

`none identified` with the reviewed scope: `redecode.py`, its shared helpers in `amendment.py`, the
CLI dispatch, the `result/command` contract, and the documentation it changed.

## Close or resume

All gates passed. Current page `docs/impl/current/corpus.md` updated with a `## Redecoding under a
new policy` section, the `Declaration or record | Result` table row, the `read_stated` usage row,
two refusal-code descriptions, and the test-coverage paragraph; linked from this record.
`docs/design/spec.md` section 4.1's closing sentence, which stated the gap this task closed, is
rewritten to name the real command. The plan task is removed from `docs/impl/plan.md`; no task
depended on it. Plan counts after: 132 tasks (110 agent, 22 human). Capability `corpus-provenance`
stays `planned`: several other tasks in its group remain open, including its required group audit.
