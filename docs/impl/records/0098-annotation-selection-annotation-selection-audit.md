# Annotation and selection audit

## Task and scope

- Id / capability: `annotation-selection-audit` / `annotation-selection`
- State: accepted
- Source: plan task at `6efc93abb81efdf6d3a9f2ed462b2ccc8225db97`; the tree was clean.
- Plan counts at start: 155 open tasks (126 agent, 29 human). Next agent
  `annotation-selection-audit (optional)`. Next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### annotation-selection-audit (optional)

Label validation, review, generated labels and image-sequence sources each touch identity and the
frozen mask, and a difference between them would change what a score means.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: One set of rules decides what a label is, what can freeze and what stays
  unverifiable.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`,
  `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from the
  rules that validation, review tools, generated labels and image-sequence sources each apply, and
  from how a label joins a staged frame, a generated case and an image sequence.
- Acceptance gates: Seed replay stays identical, an unresolved case never freezes, and an
  unverifiable label never scores as zero. Every finding is fixed, routed to a task or dropped with
  its reason, and `make quality` passes. Finding nothing is a valid result when the record states
  what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

Scope: everything the group built. Reviewed together were records 0092 to 0094, 0096 and 0097
with their audit handoffs, the seam record 0095, specification sections 4.2 and 4.3 and the
section 6 lines that read labels, the corpus, contracts and product-core pages, every module
under `src/ss_track/annotate/`, `commands/annotate.py`, their tests and the seven annotation
contracts. The neighbouring code each one rests on was read too: source identity and stream
selection, retained sequences, stored-media decoding, track-following case recipes, the corpus
manifest and the label layout. A CLI scenario exercised every annotate command on a video file,
a rotated video, a two-camera file and a retained image sequence, with refusals, freeze, derive
on two corpus versions, `data clean` and restaging (script not kept). Findings by question, each
fixed in this change unless it says otherwise:

**Integrity.**

- Bug: `annotate derive` read a parent's frozen labels and checked them only against their own
  header. Labels frozen against another source, or another decode of this one, were derived into
  every case of the stream. The probe filed a rotated clip's revision under a stream of a
  different clip and derive sealed all ten cases. Derive now joins the labels to the corpus
  stream: `source_sha256`, `width`, `height` and `frame_count` must equal the stream's, and a
  mismatch is `MANIFEST_INVALID` before any case is written. `test_derive_stream.py` fails
  without it.
- Bug: freeze could not place a revision safely. It rewrote an existing frozen revision with
  another settlement's, and an output path that was an input replaced the annotator's document;
  the probe overwrote `left.yaml` with the frozen labels. A revision is now written once: the same
  freeze again changes nothing, other bytes at either path are `CORPUS_CONFLICT` with neither file
  written, and an output that is any input is `MANIFEST_INVALID`. `test_frozen_outputs.py` covers
  both. The one existing test that refroze different content over the same paths now freezes to
  its own folder.
- Bug: `annotate validate` reported `version` `1.0.0` for labels and seeds, while every document
  was validated under the newest frozen version of major 1. The version now comes from the
  registry, and `test_annotate_command.py` compares it with the newest.
- Bug: the `plate_frame` check refused a plate only when a target lay wholly inside a painted
  region. The plate's pixels are copied into the region, so a target that only crossed it, or a
  slowly moving target used as its own plate, painted target pixels onto frames the case labels
  `absent`. A plate with any part of a scoring target inside a region is refused, and so is one
  whose target has no known location. Section 4.2 now states this. `test_derive_plate.py` covers
  overlap, a moving target, an unknown location, the withheld visibilities that pass, and a
  distractor that is not a target.
- Gap: the freeze paths that adopt a right-side point, omit a one-sided frame or event, or keep an
  unknown one-sided frame had no test that checked their values. `test_frozen_sides.py` states
  each by hand; all three passed unchanged.
- Bug: a derived case changed an event's visibility without marking its selection `uncertain`,
  which the freeze does for the same change, so one event was `reviewed` after a derivation and
  `uncertain` after a freeze. `labels/events.follow_frame` is now the one rule, and both apply it.
- Bug: `out_of_view` cases recorded re-entry on every later frame that kept a box, giving one
  return several re-entry events. Re-entry is recorded once, on the first frame the target is
  back, and section 4.3 says so. `test_derive_track.py` covers it.
- Gap: labels on the second camera of a two-camera file could not be validated, compared or
  frozen. `read_frame_space` decoded only a file's first stream and named it by the file hash.
  `--video-stream-index` now selects the stream, and a later stream is named by its stream
  identity, the value `import` reports. `declaration/annotation-label`,
  `declaration/annotation-seed` and `record/annotation-revision` 1.0.2 correct the
  `source_sha256` description. `test_video_stream.py` covers the identities, the refusals and the
  three commands.
- Gap: the suite-wide output check intercepted `write_sealed` only in `ss_track.corpus.*`, so no
  annotation revision or derived label written in a test was checked against its contract. The
  hook now covers every `ss_track` module.
- The corpus page said annotation did not exist, and the README listed corpus import only. Both
  now state what the four commands do.
- Every handoff of records 0092 to 0097 reached an owner whose text states it. The `x-rules`
  sentences that still say "video" stay, for the reason record 0097 gave.

**Repetition.** The visible-status set was stated three times, a duplicate finder twice, the
declared space reader twice, the label contract check and the label writer twice each, and every
reader repeated its contract name and major. `declarations/contracts.py` names the contracts and
reads a declaration with its hash, `labels/document.py` writes and checks a built document, and
`sources/declared_space.py` holds the space reader, the source join and the stream join. Class
lookup, the review place names and the derivation field readers are each one function. Write-once
publishing was a private helper of `discover export`; `write_once` and `holds_payload` in
`core/scratch.py` are the shared rule that freeze, export, inventory, acquisition and pool use.

**Explicit patterns.** Freeze wrote both files through the sealed writer, and derive and freeze
used one canonical writer for label documents; that is kept. Freeze takes a `ReviewInputs` value
instead of eight positional paths. The command layer only parses.

**Naming.** The flat package of thirty-odd modules is grouped into `declarations`, `sources`,
`packs`, `labels`, `validation`, `review` and `derivation`, imported in that order, with tests
mirroring it. `tests/annotate/test_layering.py` holds the order. `read_validated_labels` is
`read_label_file`.

**Algorithms.** Measured with a benchmark script that was not kept, on one instance of 6,000
frames with a box disagreement on every frame. Building the frozen document took 1.07 s, because
each frame scanned every row. Deriving a `scale`, `translate` or `region_status` case took about
1.65 s, because each frame copied the whole track. Indexing the unknown rows once and mapping
frames in one pass give 0.03 s and 0.01 to 0.05 s, with byte-identical documents and labels.
30,000 frames take 0.2 s.

**Gaps.** Freezing named three paths that had to agree with a corpus stream by convention.
`annotate freeze --corpus <id> --stream <id>` reads the stream's stored source at its recorded
video stream, writes where derive reads, and refuses a decode whose frame shape is not the one
the corpus pinned. `test_stream_freeze.py` covers it. No command stores or derives a mask, and
nothing yet pins a derived revision, which derive rewrites when a rule changes: both are routed
below.

**Ideas.** Stream-addressed freezing, above, is the one that serves an operator directly.

Compatibility: the refactor moved no byte. The behavior fixes move what they must: derived label
documents and seals change where an event's selection quality or a re-entry changed, freeze
refuses what it used to overwrite, plates that used to pass are refused, and validate reports the
version it validated under. No dependency, environment variable or clean kind changed. Current
pages: [corpus](../current/corpus.md#annotation-contract), [contracts](../current/contracts.md)
and [product core](../current/product-core.md); specification sections 4.2 and 4.3, the test
plan and the README layout describe the result.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Seed replay stays identical | `tests/annotate/validation/test_annotation_seeds.py`, the scenario's two seed validations of one file | pass: one replay hash on both trees |
| An unresolved case never freezes | `test_annotation_freeze_refusal.py`, `test_frozen_outputs.py`, the scenario's two unresolved freezes | pass: refused, nothing written |
| An unverifiable label never scores as zero | `test_disposition.py`, the no-parent derive in `test_derive_command.py` | pass: `unscorable` rows and cases, no `score` key anywhere |
| No byte moves in the refactor | The CLI scenario run from a worktree at `6efc93a` and from the tree after the move and after the consolidation, on media written once | pass: 61 command results and 465 files equal in bytes and mode, 50 hard-link groups equal |
| Fixes move only what they state | The same comparison after the fixes | 31 differences: the reported `version`, five derived documents with their seals and the records naming them; the diff is an event marked `uncertain` or two re-entry events removed |
| Timing | Scenario alternated HEAD, tree, HEAD, tree | 4.29, 4.28, 4.30 and 4.31 s: no change; the long-track gains are above |
| Findings fixed, routed or dropped | Audit handoff below | pass |
| `make quality` | `make quality`, then `make lint-md`, `make build` and `make ci-checks` after the record and one test file were completed | pass: 2819 tests, coverage 90.91%, every static gate; the first run stopped only at the unfinished record's Markdown |

## Audit handoff

- AUD-annotation-selection-audit-1, nonblocking: no command stores a frozen mask under the corpus
  or derives one for a generated case, and nothing pins a derived revision, which `annotate
  derive` rewrites when a derivation rule changes. A scenario could score against a mask of other
  labels, or against a revision that moved. Owner: `scenario-contract`, amended in this change to
  pin each label seal and mask, refuse a pin that no longer matches, and refuse a named stream or
  case with no mask rather than score it.
- AUD-annotation-selection-audit-2, nonblocking: a derived case now marks an event `uncertain`
  when its frame changed. Owner: `motion-suite`, amended to report events of each selection
  quality with their counts.
- AUD-annotation-selection-audit-3, nonblocking: the pilot labelling must file its revisions where
  derive reads them. Owner: `label-pilot-encounters`, amended to freeze by stream.
- Partly fixed here: source import took the write-once helper from review export. It now uses
  `core/scratch.py`; the declaration-byte helper remains. Owner: `discovery-package-split`,
  amended to state what is left.
- Dropped, no work needed: a seed may leave `pts` null on a timed source. The contract states that
  null means the operator stated no time, and the frame index still names the frame.
- Dropped, no work needed: derived labels are sealed evidence that a scenario will pin, not a
  cache, so they are not a data-clean kind.
- Dropped, no work needed: the `x-rules` sentences that say "video", for the reason in record
  0097.

## Close or resume

Every gate passed. The task left the plan with the Agent-lane heading of its group. The
`annotation-selection` capability stays `planned`, because its human tasks remain open. The
corpus, contracts and product-core pages, specification sections 4.2 and 4.3, the test plan and
the README describe the result, and the records index lists this record. Plan counts after: 154
open tasks (125 agent, 29 human); next agent `scenario-contract`, next human
`define-locked-test-policy (optional)`.
