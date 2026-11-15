# Corpus provenance group audit, second pass

## Task and scope

- Id / capability: `corpus-provenance-audit` / `corpus-provenance`
- State: accepted.
- Source: plan task; starting commit `c7bbde8`; working tree clean.
- Plan counts at start: 160 open tasks (132 agent, 28 human). Statuses: BLOCKED BY HUMAN=12,
  CLEAR=124, HUMAN-GATED=16, RUN NEEDED=8. Next agent `corpus-provenance-audit (optional)`; next
  human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-provenance-audit (optional)

The corpus area needs a coherent account of source identity, capture facts, generated cases and
the evidence linking them as implementation evolves.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Corpus evidence has clear, consistent contracts, lineage and governance,
  with an implementation that supports effective future work.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. Improve implementation and contracts when
  doing so advances clarity, lineage, governance or future effectiveness; historical formats and
  their bytes need not be preserved. Retain the integrity of current evidence, or regenerate it.
- Data and artifact paths: `src/ss_track/core/`, `src/ss_track/corpus/`, `tests/core/`,
  `tests/corpus/`, `contracts/`, and affected corpus evidence under `$DATA_DIR`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Trace source
  identity, sealing, capture facts, generated cases and downstream consumers. Simplify obsolete
  compatibility paths and update affected contracts, fixtures and documentation; regenerate affected
  corpus evidence when needed.
- Acceptance gates: Current contracts and evidence agree, import and verification protect source
  integrity, lineage and governance are clear, and generated cases reproduce on rerun. Every finding
  is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding nothing
  is a valid result when the record states what was reviewed.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none. The user asked to improve the implementation and to update documentation and
  the README where needed.

## Implementation

Scope: what the group built since its first audit (record 0049). Reviewed together were records
0081 and 0084 to 0090 with their audit handoffs; specification sections 2 and 4.1 with the capture
vocabulary and image-sequence text, and section 4.3's scale reduction; the corpus and contracts
current pages; `core/evidence/`, `core/clean*.py` and `core/scratch.py`; every module those tasks
added or changed under `corpus/declarations/`, `corpus/decoding/`, `corpus/sources/`,
`corpus/versions/`, `corpus/cases/` and `corpus/records/`; their consumers in bundles, near-duplicate
sampling, discovery and link review; and the tests and contracts they added. Findings by question,
each fixed in this change unless it says otherwise:

**Integrity.**

- Bug: `corpus inspect-source` of any current (major 3) source record wrote a result that
  `result/command` 1.27.0 and 1.28.0 refuse, because their `source_inspection.capture` was written
  for historical records and lacks `observer_platform`. No test inspected a current record, so the
  suite-wide output check never saw one. Frozen `result/command` 1.29.0 states the field, and
  `test_a_current_record_needs_no_migration` fails without it.
- A preview of a scale-reduction case whose bundle was larger than its parent refused as
  `RECORD_INVALID` with empty details, although the refusal table gives a case of the wrong frame
  shape to `CASE_INVALID`. Preview now computes the size the transform gives (`reduced_size`, the
  one rule the transform uses too) and refuses any other size as `CASE_INVALID` with the case
  named. Only a reseal by hand makes such a bundle; `test_scale_reduction.py` covers it.
- The refusal for a successor still short of the current major told the operator to supply all
  three import operations, even when all three had been given. Every operation an older record
  needs is named before any runs, so a successor still short lacks a fact no operation supplies; it
  now says so, with its own remedy and a test.
- Docstrings of `replacement.py`, `redecode.py`, `amendment.py`, `decode.py` and `source_file.py`
  predated `--amend-capture` or image sequences and said what the code no longer does. The corpus
  page said `modality` is `camera` because import accepts only video. Each now states the current
  behavior. `amend_source_terms` also records capture judgments, so it is now `amend_source`.
- Every handoff of records 0081 to 0090 reached an owner whose text states it:
  `plugin-evaluator-core` (missing sequence timing), `generated-case-labels` (scale labels),
  `robustness-severity-sweep` (graded factors), and the scenario-pack and score tasks (platform
  strata). The record lines over the Markdown limit in 0086 and 0087 failed `make quality`; they are
  rewrapped with no word changed, a chore.

**Repetition.**

- The two capture judgments were named in four modules and their vocabularies lived in the build
  counts. `corpus/declarations/capture.py` now states both vocabularies once and reads the capture
  section; declaration parsing, amendment, fact comparison, inspection and the build counts use it.
- A declared rate's time base was formatted in two modules; `decoding/image_sequence.time_base` is
  the one rule.
- `require_migration_operations` held the rule for which operations an older record needs, inline.
  It is `replacement.migration_operations`, which the refusal and source inspection share.
- `copy_declared_source` and `declared_content_hash` each had a second copy of the file path for
  sequences; each is one path now.

**Explicit patterns.** Image-sequence import added six function-level imports, and one of them
made `corpus/decoding` read the source inventory, inverting the layering every other decoding
module keeps. `inspect_media` also dispatched on a directory. Decoding now decodes only what it is
given. `corpus/sources/stored_media.inspect_stored` is the one place that tells a stored file from
a stored sequence. Import, redecode, staging and near-duplicate sampling call it, and no
function-level import remains in those modules. The sequence decoder bound its default clock when
the module loaded, unlike `inspect_media`. It now resolves the clock at call time and gives the
same clock to each image's decode. The image-sequence record format now has a named kind constant
like the others.

**Naming.** `amend_source_terms` is `amend_source`, as above. The preview's shape check is
`_require_case_shape`, because a case's expected shape is no longer always its parent's.

**Algorithms.** Measured with a script that was not kept: the area-average kernel on one 1080p RGB
frame took 56.6, 31.6 and 17.0 ms for factors 2, 3 and 7 with 64-bit sums. 32-bit sums took 53.7,
29.6 and 12.2 ms, but they overflow once a factor passes about 4,100. 64-bit sums without the
full-frame copy took 55.5, 33.3 and 16.4 ms. Neither gain justified a bound on the factor, so the
kernel keeps 64-bit sums, and its module docstring says why. A `min` that never changed the block
size is removed, and the block geometry is computed once per case instead of once per frame.

**Gaps.** Interactive link review handed a sequence directory to `ffplay` and described it as
"video stream 0", so playback of every sequence source failed. `stored_media.player_input` now
opens a sequence through FFmpeg's image demuxer at its declared rate, and `describe_stored` names it
as an image sequence; `test_interactive.py` covers both forms. The `tool-caches` clean kind removes
developer caches, not corpus artifacts. It was registered by the corpus area and now lives in
`core/clean_kinds.py`.

**Ideas.** An operator migrating a historical source learned the needed operations one refusal at a
time. `corpus inspect-source` now reports `migration_operations`, from the same rule the refusal
uses, under frozen `result/command` 1.29.0, and specification section 4.1 states it. No other idea
needed scheduling.

Compatibility: no sealed byte, hash, seal, staged frame or hard link moved, and no dependency
changed. `result/command` 1.29.0 adds an optional result field. `ss_track.corpus` exports
`amend_source` instead of `amend_source_terms`; `decoding.decode.ignore_frame` is now public, and
`decoding.image_sequence.inspect_stored_sequence` is replaced by `sources.stored_media`. One
refusal code changed where only a reseal by hand reaches it, as above. Current pages:
[corpus](../current/corpus.md) and [contracts](../current/contracts.md); the README layout now
lists what `core/` and `corpus/` hold.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Current contracts and evidence agree | `tests/corpus/records/test_source_inspection.py::test_a_current_record_needs_no_migration` under the suite-wide output check; `make lint-contracts` | pass after the 1.29.0 fix above; failed before it |
| Import and verification protect source integrity; no byte moves | One CLI scenario run by the starting commit and by this change on the same written sources: every fixed-corpus source, two PNG sequences with and without a rate, a changed-image refusal, build twice, stage, verify, hashes, preview of a scale case and of a sequence, inspection, capture amendment twice, a refused stale verify, a successor build, stage and verify, redecode, `data clean` and restage, and a metadata-only amendment after the images were removed (script not kept) | pass: 95 command results equal except the new `migration_operations` field of the two inspections, and 2562 files equal in bytes and mode, with the same 807 hard-link groups |
| Generated cases reproduce on rerun | The scenario's repeated build, restage after `data clean` and `staged-hashes.json` of `arch-fixed-v1`; `test_scale_reduction.py` | pass: identical bundles and staged hashes |
| Lineage and governance are clear | Integrity and repetition findings above; the successor build in the scenario | pass |
| Timing | The scenario alternated HEAD, change, HEAD, change on this host | 5.69, 5.77, 5.62 and 5.68 s: no measurable change |
| Findings fixed, routed or dropped | Audit handoff below | pass |
| `make quality` | `make quality` | pass: 2565 tests, coverage 92.96%, format, lint, typing, complexity, shell, links, spec-plan, contracts, Markdown and the package build |

## Audit handoff

Every finding was fixed in this change, and no plan task was added. Dropped, needing no work:

- The area-average kernel keeps 64-bit sums: the measured gain of narrower sums was too small for
  the bound on the factor it needs.
- `schema/compatibility/dispositions.py` names the two judgment properties on its own. It is the
  data-contracts group's statement of which contract properties a view may not derive, keyed by
  contract property name, not the corpus vocabulary, and `test_dispositions.py` holds it.
- The long record lines in 0086 and 0087 were a formatting chore, rewrapped as stated above.

## Close or resume

Every gate passed. The task left the plan, with the Agent-lane heading of its group. The
`corpus-provenance` capability stays `planned`, because its human task
`define-locked-test-policy (optional)` is still open. The corpus and contracts pages, specification
section 4.1 and the README layout describe the result. Plan counts after: 159 open tasks (131
agent, 28 human); next agent `scenario-pack-contract`, next human
`define-locked-test-policy (optional)`.
