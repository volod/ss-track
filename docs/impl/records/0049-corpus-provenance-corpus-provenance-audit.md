# Corpus provenance group audit

## Task and scope

- Id / capability: `corpus-provenance-audit` / `corpus-provenance`
- State: accepted.
- Source: plan task; starting commit `1d4848b`; working tree clean.
- Plan counts at start: 129 open tasks (106 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=101, HUMAN-GATED=13, RUN NEEDED=5. Next agent `corpus-provenance-audit (optional)`; next
  human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-provenance-audit (optional)

The corpus pipeline grew one task at a time, so one rule can live in two places and no check reads
import, build, stage and verify as one path.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Import, build, stage and verify read as one pipeline with one route for each
  rule, and every record they wrote stays valid.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`,
  `$DATA_DIR/import/<source-sha256>/`, `$DATA_DIR/corpus/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  is already known to repeat: the `flock` routines and their scratch clearing in `staging.py`,
  `amendment.py` and `descriptor_publish.py`, the `.incoming-` literal in `importer.py` beside
  `SCRATCH_PREFIX`, the two `PermissionError` handlers for one source read, and the `_rights` test
  helpers beside `_record` in `tests/test_cli.py`. Then compare the refusal table with the codes
  raised.
- Acceptance gates: Each named repetition is merged or kept for a stated reason. The fixed corpus
  keeps its `bundle_sha256` and `frame_set_sha256`, and every refusal code keeps its meaning. Every
  finding is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding
  nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

Reviewed together: records 0001 to 0014 and 0031 to 0048 of this group with their audit handoffs,
specification sections 4.1 and 4.3, the corpus and contracts current pages, every module under
`src/ss_track/corpus/` and the commands that call them, and `tests/corpus/` with `tests/test_cli.py`.
Findings by question, each fixed in this change:

**Integrity.**

- `corpus/records/kinds.py` said it states each format's one major, but the majors sat beside six
  writers, and `near_duplicate_scan.py` reached the corpus format and directory through lazy
  imports of the builder to dodge an import cycle. Every `RecordFormat` is now in `kinds.py`.
- Two refusals were raised outside their table meaning. A sealed record whose declared color matrix
  no conversion applies was `RECORD_INVALID`, which states a writer defect, and a bundle record
  stating a pixel format other than `rgb24` was `SOURCE_FORMAT_CHANGED` at preview, which states a
  decode. Both contracts forbid those values, so only a reseal by hand makes them, and both are now
  `RECORD_TAMPERED`, each with a test. The table now also states what the code already raised: a bad
  `--run-id` under `MANIFEST_INVALID`, a reuse hash defect and a preview layout defect under
  `RECORD_INVALID`, and a preview of an undeclared stream under `BUNDLE_NOT_STAGED`. Every other
  raise site matches its row.
- An amendment or a redecode of a record read through a view major kept the in-memory view as the
  replaced record, under the old seal, so the kept record no longer matched its seal. No installed
  contract declares a view yet, so no run reached it. The record as written is kept now, and
  `tests/corpus/sources/test_replacement.py` fails on the old behavior.
- No handoff of records 0031 to 0048 named this audit, and every owner they name still exists.
  `docs/design/spec.md` said an import's scratch stays for the operator; it now states the sweep
  below.

**Repetition.**

- Locking and scratch: three `flock` routines (staging, amendment, descriptor publication) and three
  scratch sweeps become `exclusive_lock(..., clear=..., busy=...)` and `clear_scratch` in the new
  `corpus/storage/scratch.py`. The `.incoming-` literal in `importer.py` was `SCRATCH_PREFIX`'s value;
  import, bundle publication and descriptor publication now share `scratch_directory`, and
  `write_sealed` and the preview PNG share `write_atomically`.
- The data-root layout was composed in seven modules, and bundles imported the import command for a
  file name. `corpus/storage/layout.py` states every path.
- The declared source file: two `PermissionError` handlers and two identical declared-hash checks
  become `corpus/sources/source_file.py`. Import and redecode built a record's `sequence` and policy
  fields twice; `source_record.decoded_sequence` and `DecodePolicy.record_fields()` serve both and the
  builder. Amendment and redecode repeated the whole successor routine; `corpus/sources/replacement.py`
  holds it once. The omitted-index rule is `identity.addressed_identity`.
- `decode_policy_sha256(policy.as_record())`, defined in the import command, was called six times;
  it is `DecodePolicy.sha256()`, with `require_policy` beside it. The converter for a recorded
  matrix, the media open with its refusal, the "no sequence section" refusal, and the bounded list of
  damaged frames each had two or three copies and have one.
- The unlinked listing, the amendment impact and the outside-chain near-duplicate scan each walked
  every version with their own unreadable handling; `corpus/versions/scan.py` is that walk.
- Tests: `tests/test_cli.py` kept its own `_record`, corpus declaration and recording fixture beside
  `tests/corpus/conftest.py`; the corpus commands moved to `tests/corpus/test_commands.py` on the
  shared fixtures. Six files parsed the last log line by hand and now call `last_record`; bundle
  reseals share `reseal_bundle`, and import-directory listings share `imported_names`.

**Explicit patterns.** One lock, scratch and rename pattern for every writer, as above. A case read
its parent's record with `read_sealed`, skipping the check that the bundle hash covers the index;
it now reads it with `read_bundle_record`. The builder read a source record's sequence without the
`incomplete_record` guard, so a missing key was a traceback; it is now `RECORD_TAMPERED`.

**Naming.** `AmendmentResult` also reports a redecode and is now `ReplacementResult`. The
`frames_root as bundles_root` alias is gone, and the sealed-reads scan names the successor writer
rather than the amendment.

**Algorithms.** Measured with scripts that were not kept, each on this host with HEAD and this change
alternating. On one 20,000-frame stream with eight cases, verify opened the parent bundle once per
case and every stream twice, and both commands hashed each hard link of one inode again. Verify
now opens each bundle record once, stage opens a parent once per run of its cases, and both hash a
shared inode once per command: `corpus verify` took 4.46 s to 4.62 s before and 3.58 s to 3.74 s
after, and a repeated `corpus stage` 4.39 s to 4.41 s before and 3.63 s to 3.66 s after.
Near-duplicate sampling hashed each stored source twice; `load_verified_source` now returns the
stored path it checked, and sampling a 6 MB source took 18 ms before and 13.8 ms after.

**Gaps.** An import killed inside the decoder left its scratch copy under `import/` for the operator.
Imports now hold `import/.import.lock` shared while their scratch exists, and an import that finds
no other holder first removes what a killed import left; `test_importer.py` covers both sides. The
storage primitives had no direct tests; `tests/corpus/storage/test_scratch.py` covers the locks, the
sweep and atomic replacement. Preview tests reached private helpers and now go through the command.

**Ideas.** The import sweep above is the operator-facing one; nothing else needed scheduling.

**Code organization.** At the user's request the code was reorganized into smaller logical
modules for readability, with no behavior change beyond the fixes above. The data-root layout,
locks and scratch now live in the `corpus/storage/` subpackage, and stage and verify, building and
reading a corpus version, and decoding and its completeness checks each sit in their own module.

Compatibility: no sealed byte, hash or seal moved, and no dependency changed. `ss_track.corpus`
exports `ReplacementResult` instead of `AmendmentResult`. Two refusal codes changed where the record
can only have been resealed by hand, as above. Imports create `import/.import.lock`. Current pages:
[corpus](../current/corpus.md) and [contracts](../current/contracts.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Each named repetition merged or kept for a reason | Repetition findings above | pass: every named repetition is merged; none kept |
| Fixed corpus keeps `bundle_sha256` and `frame_set_sha256` | `stage_sources` of `tests/corpus/hosts/_fixed_corpus.py` on one set of written sources, run by the starting commit and by this change (script not kept) | pass: frame set `051c14ac...` both times, and the staged-hashes record of 84 bundles and 951 frames byte-identical |
| No record or result byte moves | One CLI scenario run by the starting commit and by this change on the same sources: every import, build, stage, verify, hashes, compare, describe in both visibilities, preview, amend, redecode of a stale-policy record, a linked version that reuses frames and an unlinked one with near-duplicates (script not kept) | pass: 97 command results equal, and 2545 files equal in bytes, mode and hard-link structure; one new file, `import/.import.lock` |
| Every refusal code keeps its meaning | Refusal table against every raise site; `test_declared_color.py`, `test_preview_limits.py` | pass after the two corrections above |
| Findings fixed, routed or dropped | Audit handoff below | pass |
| `make quality` | `make quality`, then `make ci-checks lint-md build` after Markdown-only fixes | pass: 1930 tests, coverage 97.2%, format, lint, typing, complexity, shell, links, spec-plan, contracts, Markdown and the package build |

## Audit handoff

Every finding was fixed in this change, and no plan task was added. Dropped, needing no work:

- `lineage.py` and `near_duplicates.py` stay whole. Each is one rule with its report, and no seam
  splits either more cleanly than it keeps it.
- A line of record 0037 broke the Markdown line-length rule, which failed `make quality`. A chore:
  it is rewrapped with no word changed.
- `schema/compatibility/publishing.py` locks its own way, on the contract directory with no lock file.
  It is the data-contracts group's code and writes into the repository, not the data root.

## Close or resume

Every gate passed. The task left the plan. The `corpus-provenance` capability stays `planned`,
because its human task `define-locked-test-policy (optional)` is still open; its Agent-lane heading
left with its last task. The corpus and contracts pages, specification section 4.1 and the
`telemetry-bundle-store` execution path describe the result. Plan counts after: 128 open tasks
(105 agent, 23 human); next agent `corpus-sibling-integration-study`, next human
`define-locked-test-policy (optional)`.
