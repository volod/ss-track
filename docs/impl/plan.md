# ss-track Implementation Plan

Forward-only: this file contains software implementation and the human evidence work needed for
correct benchmarks and a reference sensor mesh tracker. Available behavior belongs in
[current-state documentation](current.md); scope and evaluation belong in the
[specification](../design/spec.md).

The Agent lane builds deterministic software and fixtures. The Human-Assisted lane supplies
authorized data, reviewed labels, stand requirements, calibrated measurements and documented hardware
selection. Hardware choices must name the software need, measured alternatives and unresolved limits.
Commercial strategy, staffing, public entry policy, publication operations and launch work are kept
in an owner-managed organizational to-do outside this repository's Git control. They do not gate
software acceptance.

Groups follow the [capability registry](../design/spec.md#capability-registry). Follow explicit
dependencies across both lanes; group priority does not imply a predecessor is complete. Required
work takes priority over optional refinements. `make plan-status` reports counts and the first task
by priority in each lane; dependency readiness must currently be checked from the task fields. Every
Agent group ends with its [group audit](../guide/planning-workflow.md#group-audits), whose
`(optional)` marker sets its order and does not make it skippable.

See the [planning workflow](../guide/planning-workflow.md),
[engine milestone map](../design/perception-bench-engine.md#milestone-map),
[test plan](../design/perception-bench-test-plan.md)
and [test-stand requirements](../design/test-stands.md). M1 is the small G0a pipeline, M2 supplies
measurement and host selection, and M3 delivers the reference mesh. M4, M5 and M6 are optional
extensions; none blocks M3. Fixture implementation proceeds without physical hardware or private data.

## Agent Implementation Tasks

### Corpus provenance -- `corpus-provenance`

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
  `tests/corpus/records/` schema 1 record of `d6b704d`, amended and then re-decoded, builds, and the
  one of `0238d55` builds through both flags together with no term invented.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### group-repeated-frames (optional)

A remux of one recording held twice inside one group counts each frame twice, in anything aggregated
by encounter, and only a frame in two streams of one source is refused today.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` and `corpus verify` refuse a run of identical frames in two
  streams of one group of one version with `STREAM_OVERLAP`, naming both streams and the first shared
  frame.
- Scope boundary: The run definition that `shared_runs.py` already applies, in one version. A copy
  replacing its original across linked versions stays accepted, because no version counts a frame
  twice.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Report same-group pairs from `find_shared_runs` for streams of one version, and
  raise them in `require_unshared_runs` beside the cross-group refusal.
- Acceptance gates: A remux in two encounters of one group and in one encounter are each
  `STREAM_OVERLAP`. A cross-group pair stays `SPLIT_LEAKAGE`, a copy replacing its original in a linked
  version stages normally, and adjacent windows of one recording still share nothing.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### unlinked-version-report (optional)

A version that names no predecessor, or branches from one, can place an evaluated source in another
split, and its build says only that it has no lineage.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus build` lists every other built version on its data root that places
  one of its sources in another group or split, for an operator's decision.
- Scope boundary: A report that refuses nothing, because independent work may reuse a recording.
  Source hashes on one data root only. Versions in the declared chain stay with the refusal.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/`.
- Execution path: Scan `$DATA_DIR/corpus/*/manifest.json` and reuse the placement comparison in
  `lineage.py`, reading every major through `read_comparable` and its projection, and naming a
  manifest it cannot read, or one whose major keeps no projection, rather than skipping it.
- Acceptance gates: A source placed in `locked` by an unlinked version and by a sibling branch are
  each listed with both versions, and both builds succeed. One state gives one listing in one order,
  and a version in the declared chain is never listed.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### amendment-impact-report (optional)

After `--amend-terms` an operator learns which corpus versions hold the affected frames only by running
`corpus verify` on each, and a version nobody verifies stays unnoticed with its frames on disk.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track import --amend-terms` lists every corpus version on its data root
  that pins the replaced record, with its frames directory, for an operator's decision.
- Scope boundary: A report on one data root that refuses nothing and removes nothing, and never fails
  an amendment that is already recorded. Other hosts stay out of reach.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/`.
- Execution path: Scan `$DATA_DIR/corpus/*/manifest.json` for streams pinning the replaced seal, sharing
  the scan with `unlinked-version-report` when that exists. A corpus projection holds no pin, so add
  `source_manifest_sha256` to each major's projection in `corpus/projections.py`, read every major
  through `read_comparable`, and name a manifest it cannot read rather than skipping it.
- Acceptance gates: A source pinned by two versions lists both, a version pinning another record is
  not listed, an unreadable manifest is named and the amendment still records, and a repeat reporting
  `unchanged` lists nothing. One state gives one listing in one order.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### case-preview (optional)

A declared region is a claim that an operator can only check by eye, and no tool shows it.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track corpus preview` writes a sheet of a parent frame beside its
  generated cases, with each region outlined.
- Scope boundary: One frame of staged bundles, read-only, as a PNG. No labelling interface.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add the command with the pinned encoder and a hand-checked outline position.
- Acceptance gates: One input gives identical PNG bytes. The outline lies on the declared pixels,
  and a frame a case removed is marked, not skipped.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### staging-single-pass (optional)

A long recording cut into many streams is decoded in full once per stream.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` decodes each source once, however many streams it feeds.
- Scope boundary: Fan-out of one strict decode. Seeking is out of scope, because the whole decode
  proves a source still matches its import.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Group pending streams by source and let one `inspect_media` consumer write several
  bundles.
- Acceptance gates: Bundle hashes match per-stream staging exactly, a failure leaves no partial
  bundle, and decode count equals source count on a multi-encounter fixture.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### bundle-frame-sharing (optional)

A generated case stores a full raw copy of every frame, even frames identical to its parent.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Frames a case leaves untouched take no extra disk space.
- Scope boundary: Hard links within one corpus version, falling back to a copy across filesystems.
  Hashes, records and read paths are unchanged.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Link in `store_frame` when a frame hash equals its parent's, with a
  scratch-to-bundle fixture.
- Acceptance gates: Bundle hashes match unlinked staging. Disk use on a short-window case falls by
  the untouched share, as measured, and `corpus verify` still names a damaged frame.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### import-stream-selection (optional)

A container with two video streams imports only the first, and a dual-camera file loses a sensor
unnoticed.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A recording names the video stream it means, and an ambiguous container is
  refused.
- Scope boundary: One video stream per recording, with a stream index that the decode policy honors.
  Audio and sidecars belong to G2 bundles.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add an index to the recording declaration, required when `video_stream_count`
  exceeds one, with a two-stream fixture.
- Acceptance gates: A two-stream file with no index is refused with both streams listed, and each
  index imports its own frames.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### declared-color-tags (optional)

A source with no color matrix tag converts as BT.601, which misreads BT.709 content.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator can declare a missing color tag, recorded as declared and used
  in conversion.
- Scope boundary: Absent tags only. A declared value never overrides a stored tag, and nothing is
  guessed from resolution.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add an optional `color` declaration, record its origin, and pass it to
  `PixelConverter`.
- Acceptance gates: A declared BT.709 source converts pure red within two levels of its true value.
  A declaration that disagrees with a stored tag is refused, and an undeclared source behaves as
  before.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### decode-interruption-safety (optional)

Ctrl-C ends a long run with a traceback, and a pathological file can decode with no limit.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An interrupted or over-limit import or stage ends with a structured refusal
  and leaves nothing partial.
- Scope boundary: SIGINT and a declared decode time limit. A hung native call stays a known limit if
  it never returns to Python.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Report `KeyboardInterrupt` through the command path and check a deadline in the
  decode loop, with an injected clock.
- Acceptance gates: SIGINT exits 1 with one JSON record and no traceback, leaving no scratch behind.
  A fixture past its limit is refused with the elapsed time.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### compression-and-timing-cases (optional)

Field video also fails through heavy compression and uneven frame timing, which no generated case
covers.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Recipes generate compression artifacts and variable frame timing from a
  parent and seed.
- Scope boundary: The spec section 4.3 further cases that need no labels. Sensor loss belongs to
  `fusion-generated-fixtures`.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add versioned transforms, pinning the encoder in the compression revision, and
  declare what a timing change does to `timestamp_quality`.
- Acceptance gates: A rerun with one seed is byte-identical, golden hashes pin each revision, and a
  changed PTS never stays `measured`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### label-driven-cases (optional)

One static rectangle cannot follow a moving target, and an occluder that appears in one frame is
unlike a real crossing.

- Serves: `corpus-provenance` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: generated-case-labels.
- User-visible outcome: Recipes take a target's frozen track to generate a crossing occluder, a
  moving removal, a similar distractor and out-of-view and re-entry intervals.
- Scope boundary: Per-frame boxes from one frozen label revision, in a new transform revision. No
  realism claim.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add a track input to the region transforms and derive labels through
  `generated-case-labels`.
- Acceptance gates: A rerun with one seed is byte-identical, and the case's bundle hash covers the
  label revision. A hand-audited occluder covers the target exactly in its declared frames, and a
  frame with no scorable box stays `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### near-duplicate-detection (optional)

A re-encoded copy of a recording shares no bytes or frame hashes, so it can still cross a split.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: RUN NEEDED
- Research: yes
- Milestone: M2
- Dependencies: none.
- User-visible outcome: A corpus build reports likely near-duplicates across groups for an
  operator's decision.
- Scope boundary: A perceptual comparison at a measured threshold. It reports and does not refuse
  until its false-match rate is known.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Compare a small perceptual fingerprint on re-encoded fixtures across codecs and
  bitrates, in a declared run over the development corpus.
- Acceptance gates: The threshold states measured recall and false-match rate. If no threshold
  separates copies from independent clips, that negative result is recorded and grouping stays
  manual.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### bundle-reuse-across-versions (optional)

A new corpus version that keeps a source decodes and stores identical frames again, though its
`bundle_sha256` is unchanged, so any new version costs hours and terabytes.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `corpus stage` reuses a linked version's frames by hard link when the bundle
  hash matches, and reports which streams it reused.
- Scope boundary: Bundles of the same hash on one data root, inside a declared chain. The new version
  still writes its own bundle record and frame set. A host that cannot link decodes, and nothing is
  shared across decode policies.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Predict the bundle hash from the sealed index and the source and policy hashes before
  decoding, verify every frame hash of the candidate, then link and write the record.
- Acceptance gates: A kept source gives the same `bundle_sha256` and identical bytes as a fresh stage,
  with no decode and no added frame storage. A damaged candidate is refused by name and never linked.
  A stream with another window or policy decodes. Removing one version leaves the other readable.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

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
  is already known to repeat: the two `flock` routines and their scratch clearing in `staging.py`
  and `amendment.py`, the `.incoming-` literal in `importer.py` beside `SCRATCH_PREFIX`, the two
  `PermissionError` handlers for one source read, and the `_rights` test helpers beside `_record` in
  `tests/test_cli.py`. Then compare the refusal table with the codes raised.
- Acceptance gates: Each named repetition is merged or kept for a stated reason. The fixed corpus
  keeps its `bundle_sha256` and `frame_set_sha256`, and every refusal code keeps its meaning. Every
  finding is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding
  nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Data contracts -- `data-contracts`

#### contract-oracle-coverage (optional)

An independent structural oracle must distinguish real compatibility breaks from gaps in its own
reasoning, without overriding the repository's semantic rules.

- Serves: `data-contracts` -- [Compatibility rules](../design/spec.md#173-compatibility-rules)
- Agent status: CLEAR
- Milestone: M1
- Research: yes
- Dependencies: none.
- User-visible outcome: Provable pattern relaxations and open-object constraints receive reliable
  independent compatibility checks, with disagreements still failing CI.
- Scope boundary: Improve or replace the development oracle and extend local pattern proofs where
  justified. No runtime oracle dependency and no automatic override of a semantic major.
- Data and artifact paths: `tests/schema/`, `src/ss_track/schema/`, `pyproject.toml`, `uv.lock`.
- Execution path: Exercise pattern widening from `^[ab]+$` to `^[abc]+$`, an optional string
  constraint added inside open command-result `details`, and recursive references. Investigate a
  corrected pinned oracle or an independently verified alternative; preserve concrete witnesses.
- Acceptance gates: The oracle accepts the proven relaxation, refuses the open-object constraint
  with its numeric counterexample, terminates on recursive references and agrees on the existing
  structural table. All actual frozen transitions remain checked. A valid negative result retains
  fail-closed behavior and explicitly states the unsupported relationships; `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.

#### contract-reference-docs (optional)

A reader of a contract should not need to read JSON Schema to learn what a field means, or how
records link.

- Serves: `data-contracts` -- [Identity and versions](../design/spec.md#172-identity-and-versions)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts docs --out <dir>` writes a data dictionary per contract,
  the first version of each field, and a lineage graph from `x-references`.
- Scope boundary: Generated Markdown only. No site or hosting. The change log stays the authored
  text.
- Data and artifact paths: `src/ss_track/schema/`, `tests/schema/`.
- Execution path: Render from frozen contracts and add dangling-reference detection to the check.
- Acceptance gates: Output is deterministic and lists every property and enum value. A dangling
  `x-references` target fails `make lint-contracts`.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.

#### dataset-descriptor (optional)

A future consumer cannot find, judge or load a corpus version without this repository.

- Serves: `data-contracts` -- [Dataset
  descriptors](../design/spec.md#175-dataset-descriptors-and-self-service)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track corpus describe` writes a Croissant 1.1 document, a dataset card and
  the contract versions used.
- Scope boundary: Inputs are sealed records, frozen contracts and one `declaration/dataset` supplying
  title, description, license, citation, address and publication date, which no sealed record holds.
  Default visibility is restricted. Raw frames are indexed with their layout. No upload, hosting or
  publication decision.
- Data and artifact paths: `src/ss_track/corpus/`, `contracts/declaration/`, `tests/corpus/`.
- Execution path: Generate from the corpus manifest, frame set and source manifests. Validate with
  `mlcroissant` in a separate locked extra and CI job, outside the runtime closure.
- Acceptance gates: A descriptor validates with zero errors and its streams, bundles and per-frame
  index load as records. Two runs give identical bytes. A public request on a restricted corpus
  refuses without printing a value, and so does one with no license. A public descriptor holds no
  value marked `restricted` or `sensitive` and gives `locked` as counts. Generated cases stay a
  labelled slice.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### odcs-contract-export (optional)

A data catalog may expect ODCS, and a generated view costs little once contracts exist.

- Serves: `data-contracts` -- [Dataset
  descriptors](../design/spec.md#175-dataset-descriptors-and-self-service)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts export --format odcs` writes one ODCS document per
  contract.
- Scope boundary: A generated view, never authored or read back. A tagged union is listed as the
  union of its branches, and what ODCS cannot state is named in `customProperties`.
- Data and artifact paths: `src/ss_track/schema/`, `tests/schema/`.
- Execution path: Project each contract and validate against the official ODCS JSON Schema, pinned by
  hash.
- Acceptance gates: Every document validates, with id and version matching its contract. Every
  property appears, and each construct lost in projection is listed.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.

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

### Annotation and selection -- `annotation-selection`

#### annotation-contract

Labels need stable identity and a frozen mask before scores can mean anything.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator validates visibility status, geometry, instance identity, motion
  events, operator seeds and masks against a versioned contract.
- Scope boundary: Label, seed and mask contracts, validation and frozen seed replay, in the stored
  orientation modules receive. Class names stay data in a scenario pack, so a label contract states
  the shape of a class ID and the pinned pack states its values. Labelling itself is human work.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add `ss-track annotate validate` with positive and malformed fixtures, including a
  source with display rotation.
- Acceptance gates: Identical seeds replay identically, and invalid labels are rejected with a reason.
  An unverifiable label stays unscorable and is never scored as zero. A label in any orientation other
  than the stored one is refused.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### annotation-review-tools

Two reviewers must be able to compare labels and settle disagreement.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: annotation-contract.
- User-visible outcome: Reviewers see disagreements and freeze one hashed label revision, with a
  sensitivity band retained for scoring.
- Scope boundary: Comparison, a recorded rationale, freezing, and a declared review sample for larger
  corpora. A labelling interface is out of scope.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add agreement reports over two label sets with fixtures.
- Acceptance gates: Hand-built disagreements are reported exactly. An unresolved disagreement blocks
  the freeze or stays `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### generated-case-labels

A generated case cannot be scored until its labels follow its pixels, and a wrong region must not
create a false negative.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: annotation-review-tools.
- User-visible outcome: `ss-track annotate derive` gives each generated case a hashed label revision
  from its parent's frozen labels and stored label transform.
- Scope boundary: Every stored label transform: region status, translation with clipping and
  `out_of_view`, and frame maps. Derived labels are never edited by hand.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`,
  `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Apply each label-transform kind to hand-built parent labels, then check plates and
  regions against those labels.
- Acceptance gates: Hand-computed labels match for all seven transforms. A plate showing a target
  inside its region is refused, and a target the region does not fully cover stays `unknown`. A
  parent with no frozen labels leaves its cases unscorable, never scored as zero.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### annotation-selection-audit (optional)

Label validation, review and generated labels each touch identity and the frozen mask, and a
difference between them would change what a score means.

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
  rules that validation, review tools and generated labels each apply, and from how a label joins a
  staged frame and a generated case.
- Acceptance gates: Seed replay stays identical, an unresolved case never freezes, and an
  unverifiable label never scores as zero. Every finding is fixed, routed to a task or dropped with
  its reason, and `make quality` passes. Finding nothing is a valid result when the record states
  what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Module contract and runner -- `module-contract-runner`

#### event-schema-contract

Python and later C++ modules need one versioned meaning for every event.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Modules and tools share a validated event schema with golden fixtures, and a
  breaking change fails CI.
- Scope boundary: The G0 and G1 record families. G2 fusion records are out of scope.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Define `.proto` files and protobuf-JSON JSON Lines validation. Add a Make target
  that regenerates bindings and a CI drift check, keep generated files out of the size and lint
  gates, and add the smallest justified dependency to `uv.lock`. Register each package under
  `contracts/event/`, pin `buf-bin` in the dev extra, and gate on `buf breaking` with the `WIRE_JSON`
  category against the frozen descriptor set, because G0 events travel as JSON. The registry,
  `make lint-contracts` and the contract `$id` pattern hold JSON Schema files only, so this task
  teaches them the `event` family.
- Acceptance gates: Golden fixtures cover absent and unknown fields, malformed payloads, coordinates,
  timestamps and power units. A malformed event is rejected with a reason. A renamed field, a reused
  field number and a changed `json_name` each fail the gate. `FrameRef` round-trips every
  field the staged bundle reports, including `transform` and `content_frame_index`, with those meanings.
- Documentation target: [Current implementation](current.md#areas), new page `current/runner.md`.

#### scenario-contract

A comparison must pin everything that can change its result.

- Serves: `module-contract-runner` -- [Run artifacts](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: event-schema-contract, annotation-contract.
- User-visible outcome: A scenario file pins corpus, frame set, labels, selection, replay mode, metric
  suite, seed and deadlines, and yields one cohort key.
- Scope boundary: The scenario schema, one cohort-key function, and one type that owns windows and
  runs. G2 boundaries are out of scope.
- Data and artifact paths: `src/ss_track/contract/`, `scenarios/`, `tests/contract/`.
- Execution path: Add the scenario as a `declaration` contract with example scenarios, and
  table-driven cohort-key fixtures.
- Acceptance gates: Changing any key field changes the cohort key. A scenario with a missing hash
  refuses to run, as does one whose corpus fails `corpus verify` or whose pinned frame-set hash differs
  from the `frame_set_sha256` that command reports. The pin is the only check that sees a frame set
  rewritten on disk. A source with empty `completeness_checks` is reported, never assumed complete.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### run-bundle-store

Every score must be recomputable from immutable evidence.

- Serves: `module-contract-runner` -- [Run artifacts](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: scenario-contract.
- User-visible outcome: A run leaves a complete read-only bundle, or one marked incomplete.
- Scope boundary: The spec section 10 artifact set, write-then-rename finalize, idempotent IDs, and a
  visibility field that defaults to restricted. `loc-lm-bench` is a pattern to check, not an import.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Add bundle reader and writer with crash and retry fixtures. The run manifest and
  bundle are `record` contracts, and the manifest lists the contract set in force.
- Acceptance gates: A crash fixture leaves no complete-looking bundle, a retried ID stays idempotent,
  and each manifest records its re-run command. A bundle with no visibility value reads as restricted.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### lockstep-runner

G0 needs a runner that accounts for every frame.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: run-bundle-store.
- User-visible outcome: `ss-track run` replays a scenario and reports exact frame accounting.
- Scope boundary: Lockstep execution and fault semantics. Paced timing is a later task.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add the runner with oracle, null, dropper, crash, schema and class-identity
  fixture modules. The null module becomes a reusable module, not only a test double.
- Acceptance gates: The G0a anti-gaming and null rows of the acceptance matrix pass. A crash is
  `MODULE_FAULT` with remaining scorable input missed, and a wrong source hash is `RUNNER_INVALID`, as
  are `FRAME_CORRUPTED`, `RECORD_TAMPERED`, `BUNDLE_NOT_STAGED`, `BUNDLE_CONFLICT`,
  `FRAME_SET_NOT_STAGED` and `FRAME_SET_MISMATCH`. `open_frame_bundle` reads any bundle directory, so
  the runner opens only bundles its pinned frame set names, and a module given another is
  `RUNNER_INVALID`. A frame a generated case removed is unscheduled and reported as undelivered, while
  a module drop stays a miss.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### paced-frame-release

A module must not see a frame before its time, or paced results are false.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: lockstep-runner.
- User-visible outcome: Paced runs score late and dropped frames as misses, and a read-ahead attempt
  fails conformance.
- Scope boundary: Fixed schedule, per-frame deadline, one-frame release channel, lifecycle messages,
  a pacing jitter log, and frame hashing before release or reported as runner time. Real-time
  scheduling claims are out of scope.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add runner-controlled release with an injected clock, so tests stay deterministic,
  plus lookahead and slow-module fixtures.
- Acceptance gates: The lookahead fixture cannot read a future frame. The slow fixture records exact
  late and miss counts with no wall-clock dependence. Frame hashing never counts as module latency.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### container-module-sandbox

Third-party code must not reach labels, the network or restricted data.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: RUN NEEDED
- Milestone: M2
- Dependencies: paced-frame-release.
- User-visible outcome: A reference, null or candidate module runs in a pinned container with
  limits applied.
- Scope boundary: No network, no label path, no mount of future frames, resource limits and a fresh
  container per run. Runtime choice happens here; the selected-host proof is part of
  `calibrate-bench-instruments`.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`, `modules/null/`.
- Execution path: Add the launcher, a hostile fixture module and a separate Make target for the
  container check, so `make ci` stays network-free. Declared run: that target on a host with the
  chosen runtime.
- Acceptance gates: The hostile fixture fails to open a socket, a label path or a future frame. If no
  runtime suits the host, the task records the blocker and does not weaken isolation.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### module-image-recipes

Anyone re-running a row needs the exact module that was measured.

- Serves: `module-contract-runner` -- [Module reproducibility](../design/spec.md#163-module-reproducibility)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: container-module-sandbox, reference-sot-tracker.
- User-visible outcome: Reference and null modules have reproducible recipes, pinned image digests and
  license notices; candidate adapters follow the same contract.
- Scope boundary: Recipes, digests and license notices, including the FFmpeg, libx264 and libx265
  notices of any image that carries PyAV wheels. Tracker tuning and registry hosting are out of scope.
- Data and artifact paths: `modules/<name>/`.
- Execution path: Record recipes and digests in the manifest. Keep third-party dependencies outside the
  core lock; add a recipe when an adapter is introduced.
- Acceptance gates: The declared image digest can be obtained or rebuilt with any difference explained.
  Missing image access is reported as unavailable; no different image silently substitutes for it.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### locked-split-guard (optional)

`locked` records membership only, so a development run can read held-out material with nothing
noticing.

- Serves: `module-contract-runner` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: lockstep-runner.
- User-visible outcome: A development scenario that names a locked stream is refused, and an
  approved locked evaluation leaves an append-only access record.
- Scope boundary: Runner enforcement and audit records. This is no access control against a person
  with disk access, and it creates no locked test.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Check split membership when a run starts, and add refused, approved and re-scored
  fixtures.
- Acceptance gates: A locked stream in a development scenario is `RUNNER_INVALID`. Each approved
  read and re-score leaves one record, and output never calls a stream held-out without a declared
  custodian policy. A corpus version with no declared predecessor is reported as having no lineage,
  and one whose `corpus verify` names a predecessor under `shared_frames.not_compared` is reported
  with each one named, so nothing calls its locked material unseen.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### tracker-compatibility-preflight (optional)

External tracker adapters need conformance evidence on the selected host.

- Serves: `module-contract-runner` -- [Module reproducibility](../design/spec.md#163-module-reproducibility)
- Agent status: RUN NEEDED
- Milestone: M4
- Dependencies: module-image-recipes, select-reference-host.
- User-visible outcome: Declared trackers have pass/fail compatibility records on the reference host.
- Scope boundary: Synthetic-frame schema, isolation and schedule checks with upstream defaults.
  Benchmark scores, entry policy and a mandatory number of projects are out of scope.
- Data and artifact paths: `modules/<tracker>/`, `$DATA_DIR/preflight/<run-id>/`.
- Execution path: Choose adapters needed for the comparison and record their license and configuration.
  Keep recipes under `modules/`. Declared run: each container on the selected reference host.
- Acceptance gates: Each adapter has an explicit supported or unsupported result and timing evidence.
  Zero compatible candidates is valid and does not block the reference implementation.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

#### module-contract-runner-audit (optional)

Contracts, the store, the runner and the sandbox were written against each other in stages, so a
frame or a boundary can be accounted for in one place and assumed in another.

- Serves: `module-contract-runner` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every frame has one account from release to stored result, and no path leads
  from a module to labels, the network or restricted data.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`, `scenarios/`,
  `$DATA_DIR/run/<run-id>/`, `src/ss_track/runner/`, `tests/runner/`, `modules/null/`,
  `modules/<name>/`, `modules/<tracker>/`, `$DATA_DIR/preflight/<run-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  frame accounting across the lockstep and paced paths, how the run store and `corpus` share
  sealed-record code, and every route out of the sandbox.
- Acceptance gates: Oracle, null, dropper, crash, schema and class-identity fixtures keep their
  exact accounting, a partial bundle never reads as complete, and a test covers each sandbox
  boundary. Every finding is fixed, routed to a task or dropped with its reason, and `make quality`
  passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/runner.md`.

### Motion and tracking evaluation -- `motion-sot-evaluation`

#### plugin-evaluator-core

Every suite needs one way to score saved evidence.

- Serves: `motion-sot-evaluation` -- [Metric-suite validity](../design/spec.md#6-metric-suite-validity-and-primary-g0-metrics)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: run-bundle-store.
- User-visible outcome: Suites score a saved bundle, and a second process recomputes identical bytes.
- Scope boundary: The TrackEval plugin shape over read-only bundles, with
  `aggregate(level, children)` for episode, encounter, run and block. TrackEval itself is out of
  scope here.
- Data and artifact paths: `src/ss_track/evaluator/`, `tests/evaluator/`.
- Execution path: Add suite and dataset interfaces, the evaluator loop, and one fixture suite that
  exercises the run and block levels.
- Acceptance gates: Recomputing a fixture bundle in a second process is byte-identical. A suite that
  reads outside its bundle fails.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/evaluation.md`.

#### sot-suite

Operators need tracking scores that cannot be gamed by omission.

- Serves: `motion-sot-evaluation` -- [Tracking suite](../design/spec.md#61-operator-selected-tracking-sot-v2-dev)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: plugin-evaluator-core, annotation-contract.
- User-visible outcome: Reports show lock coverage, horizon retention and exposure with denominators.
- Scope boundary: `sot-v2-dev`, and `sot-paced-v1` scoring of late and missing results. Absence and
  re-entry diagnostics are included. Later suites are out of scope.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add hand-computed fixtures for every metric, in table-driven tests.
- Acceptance gates: Hand-computed metrics, denominators and time weights match, and a late result
  counts as a miss in `sot-paced-v1`. An episode with no scorable frame is `NOT_SCOREABLE`. A stream
  with `missing` timestamp quality reports time-based scores as unavailable, with its cause, on a real
  AVI fixture.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### motion-suite

Motion proposals need their own event scores.

- Serves: `motion-sot-evaluation` -- [Motion proposals](../design/spec.md#62-motion-proposals-motion-v1-dev)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: plugin-evaluator-core, annotation-contract.
- User-visible outcome: Reports show event recall, detection delay and operator-burden proposals.
- Scope boundary: `motion-v1-dev` only. It is no general detection claim.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add matching-order fixtures and hand-computed recall.
- Acceptance gates: Oracle fixtures reach recall 1 with zero burden proposals. A null module scores a
  `VALID` zero and never `NOT_SCOREABLE`.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### development-decision-status

Maintainers need a rule for saying whether a version improved.

- Serves: `motion-sot-evaluation` -- [Comparisons](../design/spec.md#63-comparisons-and-decision-status)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: sot-suite.
- User-visible outcome: Paired comparisons report improved, regressed, `inconclusive` or
  `insufficient_data` per metric, and a noise floor.
- Scope boundary: Noise floor, seeded encounter-cluster bootstrap and status rules. Public ranks are
  out of scope.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add statistics with deterministic seeded fixtures.
- Acceptance gates: Fixtures reproduce each status. Fewer than 10 encounter groups yields
  `insufficient_data`, and a rerun with one seed is byte-identical.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### motion-sot-evaluation-audit (optional)

Each suite scores saved evidence through a shared core, and a denominator or time weight defined
twice would make two suites disagree on one run.

- Serves: `motion-sot-evaluation` -- [Metric-suite validity](../design/spec.md#6-metric-suite-validity-and-primary-g0-metrics)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every suite scores through one core, with each denominator and time weight
  defined once.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/evaluator/`, `tests/evaluator/`, `src/ss_track/suites/`,
  `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from the
  denominators, time weights and exclusions each suite applies, and from what
  `development-decision-status` reads from them.
- Acceptance gates: Hand-computed fixture metrics stay exact, and each suite's exclusions appear in
  its output. Every finding is fixed, routed to a task or dropped with its reason, and `make
  quality` passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Reference tracker -- `reference-tracker`

#### reference-sot-tracker

The benchmark needs a simple, inspectable baseline.

- Serves: `reference-tracker` -- [Reference tracker](../design/spec.md#78-tdd-reference-tracker-and-stagewise-development)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: lockstep-runner, sot-suite.
- User-visible outcome: A deterministic seeded tracker and its motion proposal front end run through
  the contract in two declared versions, so G0a has a real comparison.
- Scope boundary: The single-camera path. The staged multi-source tracker belongs to M3.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference/`.
- Execution path: Add a bounded motion proposal, a constant-velocity Kalman model, geometry gates and
  tentative, confirmed, lost and reacquired states.
- Acceptance gates: The G0a reference tracker row of the acceptance matrix passes on rerun with one
  seed. A predicted stale box cannot pass as a measured detection.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/reference-tracker.md`.

#### load-calibrated-baseline (optional)

A light tracker has spare time, so it cannot show whether heat costs quality.

- Serves: `reference-tracker` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: reference-sot-tracker.
- User-visible outcome: The reference tracker gains a declared load setting that places its cool-run
  compute near the frame deadline.
- Scope boundary: One documented load setting recorded in the manifest. It is an unranked mechanism
  baseline and never a tracking result.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`.
- Execution path: Add the setting and a fixture that shows it changes compute time only.
- Acceptance gates: The output with load matches the output without load on a lockstep fixture. A
  setting that leaves no deadline margin in a cool run is refused.
- Documentation target: [Current implementation](current.md#areas), page
  `current/reference-tracker.md`.

#### reference-tracker-audit (optional)

A baseline only helps if it stays simple and deterministic, and a load setting added later can bend
it.

- Serves: `reference-tracker` -- [Reference tracker](../design/spec.md#78-tdd-reference-tracker-and-stagewise-development)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: The reference tracker stays small enough to inspect, with one deterministic
  path under every setting.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  the load setting touches, every source of randomness or wall-clock time, and what can be shared
  with `mesh-reference-tracker`.
- Acceptance gates: Seeded runs stay identical, the load setting preserves lockstep outputs, and
  continuity, lost and re-entry, identity and deadline fixtures pass. Every finding is fixed, routed
  to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result
  when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page
  `current/reference-tracker.md`.

### Comparison report -- `comparison-report`

#### local-comparison-report

Maintainers need to inspect two versions and see every exclusion.

- Serves: `comparison-report` -- [Comparison dashboard](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: development-decision-status.
- User-visible outcome: `ss-track compare` writes a local HTML and JSON report, or refuses with a
  reason.
- Scope boundary: Local report with visibility retained. Shareable export uses `visibility-gate`.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Build the report from saved metrics with compatible and incompatible fixtures,
  including frame-linked failure references.
- Acceptance gates: An incompatible cohort is refused with its reason, and the report never edits or
  recomputes source metrics. Generated cases appear in their own slice by transform, never in a field
  aggregate or an encounter count, and undelivered frames and unverified completeness are shown.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### g0a-pipeline-run

The whole offline path must work on real labelled video.

- Serves: `comparison-report` -- [Delivery gates](../design/spec.md#3-scope-and-delivery-gates)
- Agent status: RUN NEEDED
- Milestone: M1
- Dependencies: local-comparison-report, reference-sot-tracker, motion-suite,
  label-pilot-encounters, generated-case-labels.
- User-visible outcome: Two reference versions produce an inspectable G0a report on one positive and
  one negative encounter.
- Scope boundary: G0a pipeline validity. No improvement, real-time or energy claim.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Declared run of the G0a scenario through `ss-track run` and `ss-track compare`.
- Acceptance gates: Every G0a row of the acceptance matrix passes. A failed row is reported with its
  cause, and M1 stays open until it is resolved.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### visibility-gate

Restricted data must be unable to reach public output.

- Serves: `comparison-report` -- [Comparison artifacts](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: run-bundle-store.
- User-visible outcome: An explicitly requested shareable export refuses any bundle not marked public.
- Scope boundary: One gate for shareable exports. Local restricted analysis remains available; publishing
  artifacts or operating a public site is outside the repository workflow.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Add the gate as the only public read path, with an import-boundary test.
- Acceptance gates: A restricted or unmarked bundle passed to the builder fails, and no restricted
  value reaches output.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### g0b-decision-run (optional)

Maintainers may want a real development decision before any bench exists.

- Serves: `comparison-report` -- [Comparisons](../design/spec.md#63-comparisons-and-decision-status)
- Agent status: RUN NEEDED
- Milestone: M1
- Dependencies: g0a-pipeline-run, label-development-corpus.
- User-visible outcome: Two versions get a within-corpus decision status on 10 encounter groups.
- Scope boundary: A development-corpus decision. G0a and mesh implementation proceed independently.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Declared run of three same-version repeats plus the paired comparison.
- Acceptance gates: The G0b row of the acceptance matrix passes. An overlapping interval reports
  `inconclusive`.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### robustness-severity-sweep (optional)

A pass or fail on one generated case does not show where a module starts to degrade.

- Serves: `comparison-report` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: local-comparison-report, generated-case-labels.
- User-visible outcome: A recipe declares graded levels of one parameter, and the local report shows
  each module's quality against that severity.
- Scope boundary: One parameter, one encounter set and one saved metric per curve. No composite
  score or field claim.
- Data and artifact paths: `src/ss_track/corpus/`, `src/ss_track/report/`, `tests/corpus/`,
  `tests/report/`.
- Execution path: Expand a `levels` list into ordinary cases at build, then plot saved metrics
  without recomputing them.
- Acceptance gates: A sweep expands to the same bundles as hand-declared cases. A hand-built curve
  matches its source metrics exactly, and a run that faulted at one level stays visible at that
  level.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### comparison-report-audit (optional)

A report joins runs, cohorts, exclusions and visibility, and the join is where an exclusion
disappears or restricted data reaches public output.

- Serves: `comparison-report` -- [Comparison dashboard](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: A report shows every exclusion and every limit it rests on, and nothing
  restricted can reach public output by any route.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<run-id>/`,
  `$DATA_DIR/run/<run-id>/`, `src/ss_track/contract/`, `tests/contract/`, `src/ss_track/corpus/`,
  `tests/corpus/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  value a report shows and the sealed record it comes from, every route to public output, and the
  cohort refusal reasons.
- Acceptance gates: An incompatible cohort is refused with its reason, each displayed value traces
  to a sealed record, and a restricted fixture reaches no public output. Every finding is fixed,
  routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid
  result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Hardware probe -- `hardware-probe-adaptive-launch`

#### host-capability-probe

A trial must start from what the host really supports.

- Serves: `hardware-probe-adaptive-launch` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: event-schema-contract.
- User-visible outcome: `ss-track hardware-probe` writes a host profile with explicit support status.
- Scope boundary: CPU, memory, storage, scheduler, governor, frequency and throttle evidence, and
  whether frequency can be capped. Sensors belong to `joint-mode-probe`; accelerators stay in
  spec section 12.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`, `$DATA_DIR/probe/<host-id>/`.
- Execution path: Add the host profile as a `record` contract. Read system facts behind a replaceable
  source that `board-telemetry-sources` can share, with recorded fixture hosts,
  including Raspberry Pi `vcgencmd` evidence.
- Acceptance gates: Recorded hosts produce expected profiles. An unavailable feature yields
  `UNSUPPORTED` or `MEASURE_REQUIRED`.
- Documentation target: [Current implementation](current.md#areas), new page `current/bench.md`.

#### hardware-probe-adaptive-launch-audit (optional)

A probe that fills a value it could not read makes every later trial start from a guess.

- Serves: `hardware-probe-adaptive-launch` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Recorded and live probes share one path, and a fact a host could not show
  stays unknown.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`, `$DATA_DIR/probe/<host-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  field a probe reports, what happens when its source is absent, and what the joint-mode probe will
  reuse.
- Acceptance gates: Recorded and live fixtures agree, an unreadable fact stays unknown, and
  `UNSUPPORTED` and `MEASURE_REQUIRED` stay distinct. Every finding is fixed, routed to a task or
  dropped with its reason, and `make quality` passes. Finding nothing is a valid result when the
  record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Controlled bench, timing and energy -- `controlled-bench-timing-energy`

#### power-trace-ingest

Energy claims need raw traces and honest integration.

- Serves: `controlled-bench-timing-energy` -- [Electrical power](../design/spec.md#794-electrical-power-thermal-state-and-motion)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: run-bundle-store.
- User-visible outcome: A meter trace becomes joules over an exact marked interval, with uncertainty.
- Scope boundary: File-based trace ingest through a declared `power-trace` contract, trapezoid
  integration, gaps, saturation and marker-based
  clock alignment. Live meter control is out of scope, so any meter can feed it.
- Data and artifact paths: `src/ss_track/energy/`, `tests/energy/`.
- Execution path: Add constant-power, pulsed-power, sample-gap, saturation and clock-drift fixtures.
- Acceptance gates: Hand-calculated joules match. A gap, clipped sample or failed alignment in the
  interval yields `NOT_MEASURABLE` with the raw trace kept.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### energy-metric-suite

The ranked energy number must come from a scored suite, not an ad-hoc calculation.

- Serves: `controlled-bench-timing-energy` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: power-trace-ingest, plugin-evaluator-core.
- User-visible outcome: A run reports joules per scheduled frame, mean and sampled peak watts, and
  scheduled and emitted counts, each with uncertainty.
- Scope boundary: Run-level energy and the energy interval. Idle subtraction stays secondary, and
  ranking is a later task.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite against recorded traces and a declared uncertainty budget.
- Acceptance gates: Hand-calculated values and intervals match. A module that emits few results gains
  no energy advantage from a changed denominator.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### hardware-trial-protocol

Hardware results need a versioned protocol declared before acquisition.

- Serves: `controlled-bench-timing-energy` -- [Hardware metrology](../design/spec.md#79-hardware-metrology-and-measurement-algorithms)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: energy-metric-suite, host-capability-probe.
- User-visible outcome: `ss-track hardware-measure` runs a declared protocol into a `HardwareTrial`
  bundle.
- Scope boundary: Versioned protocol, preflight checks, order, instrument records, timing/resource
  estimates and validity. Camera optics and vibration are in `camera-trial-suite`.
  Optional ranking replacement rules apply only when that protocol is selected.
- Data and artifact paths: `src/ss_track/energy/`, `tests/energy/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Add the protocol and `HardwareTrial` as contracts, and fixtures that replay recorded
  traces.
- Acceptance gates: Fixtures reproduce timing, resource and energy estimates with explicit units and
  uncertainty. Missing instruments invalidate only affected claims. Every invalid attempt remains
  in the bundle; ranking-specific repetition rules never gate a basic bench measurement.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### controlled-bench-timing-energy-audit (optional)

Trace ingest, the energy suite and the trial protocol must agree on units, clocks and validity, or
an energy number outlives the evidence behind it.

- Serves: `controlled-bench-timing-energy` -- [Electrical power](../design/spec.md#794-electrical-power-thermal-state-and-motion)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every energy and timing estimate traces to hashed raw evidence through one
  integration path, with its uncertainty and validity.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/energy/`, `tests/energy/`, `src/ss_track/suites/`,
  `tests/suites/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  units and clock handling across ingest and suite, how validity travels from trial to result, and
  any energy calculation outside the suite.
- Acceptance gates: Fixture estimates recompute exactly from retained raw traces, and an invalid
  trial cannot yield a valid estimate. Every finding is fixed, routed to a task or dropped with its
  reason, and `make quality` passes. Finding nothing is a valid result when the record states what
  was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Hardware selection -- `hardware-selection`

#### hardware-selection-report

Hardware choices need a repeatable comparison that keeps its evidence.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: CLEAR
- Milestone: M2
- Dependencies: hardware-trial-protocol.
- User-visible outcome: `ss-track hardware-select` compares measured candidates against a stand's
  requirements and budget, and writes a selection record with an energy ledger.
- Scope boundary: Measured configurations only. Datasheet options stay labelled unmeasured, and no
  simulation, prediction or public ranking is included.
- Data and artifact paths: `src/ss_track/selection/`, `tests/selection/`, `scenarios/stands/`,
  `$DATA_DIR/selection/<selection-id>/`.
- Execution path: Add versioned stand requirement files with quality, coverage, timing, interface, storage,
  power and thermal limits and their software consumers. Compare only like-for-like declared trials;
  ledgers keep shared rails shared. Use table-driven fixtures for uncertainty and missing evidence.
- Acceptance gates: A datasheet option is never chosen as measured. Missing required evidence, uncertainty
  across a limit or incompatible workloads cannot produce a qualified choice. No qualifying
  configuration is a valid result; an inaccessible boundary is `NOT_MEASURABLE`.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/hardware-selection.md`.

#### hardware-selection-audit (optional)

A selection record is read long after it is made, so anything it leaves unstated becomes an
unsupported claim.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: CLEAR
- Milestone: M2
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: A selection states what was measured, rejected and left unmeasured, from
  retained evidence alone.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/selection/`, `tests/selection/`, `scenarios/stands/`,
  `$DATA_DIR/selection/<selection-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from how
  a record reaches its choice, and from every input that is not a retained measurement.
- Acceptance gates: Only measured configurations are chosen, and a selection with none qualifying
  says so. Every finding is fixed, routed to a task or dropped with its reason, and `make quality`
  passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

### Sensor joint-mode probe -- `sensor-joint-mode-probe`

#### joint-mode-probe

A mesh needs sensors that work together, and separate passes do not prove that.

- Serves: `sensor-joint-mode-probe` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: host-capability-probe, hardware-trial-protocol.
- User-visible outcome: `ss-track hardware-probe` tests declared sensors together and reports a
  supported profile or an explicit reason.
- Scope boundary: Installed sensors, simultaneous modes, sustained loss, timestamp quality and bus
  contention. Accelerator graphs stay in spec section 12.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`.
- Execution path: Add a sensor source interface and recorded fixture sets.
- Acceptance gates: A pair that passes alone and fails together reports `UNSUPPORTED` as a pair.
  Discovery alone never yields `SUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), new page `current/sensor-mesh.md`.

#### sensor-joint-mode-probe-audit (optional)

A joint probe repeats much of the host probe, and separate passes can still be mistaken for joint
evidence.

- Serves: `sensor-joint-mode-probe` -- [Probe and launch](../design/spec.md#71-probe-and-adaptive-launch)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Joint-mode evidence shares the probe's path and cannot be mistaken for
  separate passes.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/probe/`, `tests/probe/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from code
  shared with `host-capability-probe`, and from how sustained load is shown in the result.
- Acceptance gates: Every installed sensor yields a supported profile or an explicit fallback, and a
  separate pass never reports as joint. Every finding is fixed, routed to a task or dropped with its
  reason, and `make quality` passes. Finding nothing is a valid result when the record states what
  was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Camera bench characterization -- `camera-bench-characterization`

#### camera-trial-suite

Requested camera settings are not measured performance.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: hardware-trial-protocol, plugin-evaluator-core.
- User-visible outcome: A trial reports measured rate, drops, object extent, sharpness and clock
  alignment, each with uncertainty.
- Scope boundary: Capture, optics and vibration metrics from recorded evidence. Stereo range stays in
  spec section 12.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite against recorded traces with known answers.
- Acceptance gates: Hand-computed values match. Missing source frame IDs report
  `upstream_drop_unknown`, and requested rate never replaces measured rate.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### camera-bench-characterization-audit (optional)

A camera setting that was requested can read as one that was measured unless the suite keeps them
apart.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Requested settings and measured performance never share a field.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  reported value and its raw evidence, and from what the suite repeats from the shared evaluator.
- Acceptance gates: Raw evidence is retained for every estimate, each estimate carries its
  uncertainty and validity, and no requested value reports as measured. Every finding is fixed,
  routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid
  result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Sensor adapters and front ends -- `sensor-adapter-frontends`

#### sensor-observation-contract

Every sensor needs one way to say what it saw, and what it could not see.

- Serves: `sensor-adapter-frontends` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-schema-contract, scenario-contract.
- User-visible outcome: Typed observations carry modality, evidence role, timing, geometry, coverage
  and provenance.
- Scope boundary: G2 record families for observations and epochs. Sensor drivers are later tasks.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`.
- Execution path: Extend the schema as an additive event contract version, without changing G0
  `FrameResult` meaning, with golden fixtures.
- Acceptance gates: `no_detection`, `out_of_view`, `disabled_by_policy`, `missing`, `stale` and
  `invalid` stay distinct. An untyped confidence field is rejected.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### g2-scenario-observation-bundles

The G0 scenario excludes G2 boundaries, so component comparisons need an explicit input contract.

- Serves: `sensor-adapter-frontends` -- [Specification](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: sensor-observation-contract, run-bundle-store, annotation-review-tools.
- User-visible outcome: Four boundary-specific scenarios freeze raw/observation inputs, producers,
  clocks, calibration, opportunity labels and epoch schedules into hashed bundles.
- Scope boundary: Extend the existing scenario and bundle code, including mixed-modality raw attachments,
  stream clock, calibration and raw-format fields, and permitted modalities in scenario rights. No
  second cohort-key implementation or live capture driver.
- Data and artifact paths: `src/ss_track/contract/`, `src/ss_track/corpus/`, `tests/contract/`, `tests/corpus/`.
- Execution path: Reuse the bundle store and split rules. Extend annotation validation and review for
  modality-specific truth and opportunity masks. Add immutable observation staging and per-boundary
  read permissions with golden mixed-stream fixtures.
- Acceptance gates: Changing calibration, producer, input bytes or schedule changes the cohort. A forbidden
  raw read or cross-split stream fails conformance; unknown clocks never imply synchronization.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### camera-front-end

The mesh needs cameras as typed sources.

- Serves: `sensor-adapter-frontends` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: sensor-observation-contract, reference-sot-tracker.
- User-visible outcome: A recorded camera stream becomes typed observations with coverage and failure
  events.
- Scope boundary: Visible cameras, using the reference proposal. Stereo range is out of scope.
- Data and artifact paths: `src/ss_track/frontends/`, `tests/frontends/`.
- Execution path: Add the adapter with recorded inputs and calibration fixtures.
- Acceptance gates: Conformance fixtures pass, and a stale calibration is reported, never used
  silently. Frames convert like staged bundles, so a left-sited H.264 or HEVC source matches its bundle
  within a measured tolerance; a system `ffmpeg` conversion that misplaces chroma is not accepted.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### non-camera-front-end

The third source must follow the hardware evidence, not a guess.

- Serves: `sensor-adapter-frontends` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: sensor-observation-contract, select-mesh-sensors.
- User-visible outcome: The selected non-camera source emits typed observations with its evidence
  role.
- Scope boundary: The one selected source, which may arrive through an `ss-sens` adapter. Only its
  supported measurement is emitted, with no implied range or class.
- Data and artifact paths: `src/ss_track/frontends/`, `tests/frontends/`.
- Execution path: Add the adapter with raw-format provenance and recorded fixtures.
- Acceptance gates: Conformance fixtures pass, and a single sensor with no justified bearing or range
  emits neither.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### synchronized-sensor-capture

Recorded front ends alone cannot run the installed reference mesh or collect its evidence.

- Serves: `sensor-adapter-frontends` -- [Specification](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: g2-scenario-observation-bundles, camera-front-end, non-camera-front-end, joint-mode-probe.
- User-visible outcome: Sensors capture raw streams and feed typed front ends with clock evidence,
  bounded queues, explicit outages and shutdown handling.
- Scope boundary: Selected hardware drivers and live-to-bundle path. No field deployment, actuation or
  assumption that a receive timestamp is capture time.
- Data and artifact paths: `src/ss_track/capture/`, `tests/capture/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Extend `ss-track run` for live-capture scenarios through replaceable drivers.
  Use fake clocks for start, skew, overflow, disconnect and recovery fixtures. Live acceptance
  belongs to `record-mesh-encounters`.
- Acceptance gates: Every scheduled opportunity is accounted for after loss or recovery. Unsynchronized
  inputs cannot yield a calibrated latency; interruption preserves raw evidence and releases devices.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### sensor-adapter-frontends-audit (optional)

Front ends, capture and fake drivers each implement one observation contract, and a fault handled in
only one of them hides until a live run.

- Serves: `sensor-adapter-frontends` -- [Module contract](../design/spec.md#5-module-contract-execution-and-fault-semantics)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every source reaches the mesh through one observation type, with faults
  handled the same way on fake and live paths.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/contract/`, `tests/contract/`, `src/ss_track/corpus/`,
  `tests/corpus/`, `src/ss_track/frontends/`, `tests/frontends/`, `src/ss_track/capture/`,
  `tests/capture/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  camera and non-camera front ends repeat, and from how skew, overflow, outage and recovery are
  handled on each path.
- Acceptance gates: Mixed-modality bundles and the four scenario boundaries pass conformance, and
  fake-driver capture covers each fault named by the capability. Every finding is fixed, routed to a
  task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result when
  the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Fusion analysis -- `fusion-analysis`

#### event-time-replay

Fusion must only see what would have arrived by then.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: g2-scenario-observation-bundles, paced-frame-release, container-module-sandbox.
- User-visible outcome: Replay releases each event at its availability time under a declared clock
  and queue model.
- Scope boundary: Bounded reordering, epochs, availability cutoff and enforcement of each boundary
  through the existing container input channel. Live capture is a separate task.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`.
- Execution path: Add the replay path with late, reordered and skewed event fixtures.
- Acceptance gates: A causal test changes future events and holds past decisions unchanged. An event
  past its cutoff never enters a result.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fusion-generated-fixtures

Fusion needs repeatable failures across streams, and no generated case acts on a whole encounter.

- Serves: `fusion-analysis` -- [Deterministic
  cases](../design/spec.md#43-deterministic-cases-and-negative-evidence)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay.
- User-visible outcome: Recipes perturb a whole encounter with skew, jitter, late and reordered
  packets, modality loss, degraded measurements, calibration errors, shared artifacts, duplicates,
  contradictions and health misreports.
- Scope boundary: The fusion fixtures of spec section 4.3, including sensor loss. Each declares
  whether its independent reference stays valid. Live capture faults belong to
  `synchronized-sensor-capture`.
- Data and artifact paths: `src/ss_track/fusion/`, `src/ss_track/corpus/`, `tests/fusion/`.
- Execution path: Extend recipes and transform revisions to observation bundles, reusing seeded
  draws and case membership.
- Acceptance gates: A rerun with one seed is byte-identical. A case stays in its encounter and
  split, and an altered geometry or time relation updates its reference or makes that metric
  `NOT_SCOREABLE`. Real and simulated failures stay separate report slices.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fusion-calibration-suite

The fusion contract requires calibrated evidence, but raw detector scores cannot supply it.

- Serves: `fusion-analysis` -- [Specification](../design/spec.md#65-fusion-probability-and-resource-policy-evaluation)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay, plugin-evaluator-core.
- User-visible outcome: Per-sensor detection/false-alarm and existence/class calibration models are
  fitted on disjoint data and evaluated with proper scores, reliability and coverage.
- Scope boundary: Calibration populations and conservative dependence assumptions. Geometry or
  class quantities without independent labels remain unavailable; no learned fusion architecture.
- Data and artifact paths: `src/ss_track/fusion/`, `src/ss_track/suites/`, `tests/fusion/`, `tests/suites/`.
- Execution path: Implement the calibration contract and a simple deterministic baseline. Add hand-computed
  Brier/reliability fixtures and correlated-source, absent-outcome and split-leakage cases.
- Acceptance gates: Known outcomes reproduce expected scores; leakage is refused. Insufficient calibration
  evidence prevents a calibrated claim and reports coverage instead of fabricating a probability.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### late-fusion-baseline

The reference needs a transparent fusion rule that shows each source's contribution.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay, fusion-calibration-suite.
- User-visible outcome: Observations become fused, ambiguous or empty results with exact source
  lineage.
- Scope boundary: The deterministic late-fusion baseline. Learned and filter-based variants are out of
  scope.
- Data and artifact paths: `src/ss_track/fusion/`, `tests/fusion/`.
- Execution path: Add gated association and deduplication, with hand-audited fixtures.
- Acceptance gates: Correlated evidence is not counted twice, and `missing` or `out_of_view` adds no
  negative evidence. An ambiguous match stays `unassociated`.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fusion-suite

A fusion change must be judged on identical inputs.

- Serves: `fusion-analysis` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: late-fusion-baseline, plugin-evaluator-core, fusion-generated-fixtures.
- User-visible outcome: The `FIXED_OBSERVATION_FUSION` boundary reports association, false merges,
  deduplication and abstention.
- Scope boundary: Fixed hashed bundles, existence/class calibration where independently labelled, and
  stage timing. Unsupported quantities remain explicitly unscorable with coverage shown.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with byte-identical bundle fixtures.
- Acceptance gates: A changed front end forces a new cohort, and raw data access fails conformance.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fusion-analysis-audit (optional)

Fusion can look better by seeing what had not yet arrived, and each of its tasks can let that in
differently.

- Serves: `fusion-analysis` -- [Multi-sensor fusion](../design/spec.md#76-multi-sensor-fusion-and-uncertainty)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Fusion sees only what had arrived by event time, on every path, and its
  calibrated evidence has one source.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/runner/`, `tests/runner/`, `src/ss_track/fusion/`,
  `src/ss_track/corpus/`, `tests/fusion/`, `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every read of an observation and the clock it uses, what the fixtures and the baseline repeat, and
  where a raw score could bypass calibration.
- Acceptance gates: Fixed hashed bundles keep their results, a late observation cannot affect an
  earlier decision, and abstention and degraded-source fixtures pass. Every finding is fixed, routed
  to a task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result
  when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Fixed-input tracker evaluation -- `fixed-input-tracker-evaluation`

#### tracker-epoch-suite

Tracker changes must be judged apart from what feeds them.

- Serves: `fixed-input-tracker-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: event-time-replay, sot-suite.
- User-visible outcome: The `FIXED_OBSERVATION_TRACKER` boundary reports identity, re-entry,
  prediction and deadline behavior.
- Scope boundary: Fixed observation streams and epoch schedules.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add crossing, miss, occlusion, re-entry and prediction-only fixtures.
- Acceptance gates: Every scheduled epoch is acknowledged, and a tracker that reads raw pixels fails
  this boundary.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### fixed-input-tracker-evaluation-audit (optional)

A tracker result only isolates the tracker while its inputs stay fixed and its cost stays separate.

- Serves: `fixed-input-tracker-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Tracker scores and costs rest on fixed hashed inputs alone.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  every input the suite reads and how tracker-stage cost is separated from what feeds it.
- Acceptance gates: A changed input is refused rather than scored, and SOT and MOT identity,
  re-entry and prediction fixtures pass. Every finding is fixed, routed to a task or dropped with
  its reason, and `make quality` passes. Finding nothing is a valid result when the record states
  what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Reference sensor mesh tracker -- `multi-source-reference-tracker`

#### mesh-reference-tracker

This is the project's reference implementation.

- Serves: `multi-source-reference-tracker` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: late-fusion-baseline, tracker-epoch-suite, reference-sot-tracker.
- User-visible outcome: Front ends, fusion and track maintenance run as one replaceable mesh tracker
  on frozen observations.
- Scope boundary: Image-plane state until a calibrated common state exists. Filters beyond the
  reference, and learned variants, are out of scope.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference-mesh/`.
- Execution path: Add track maintenance over fused and single-source observations, and work through
  the spec section 7.8 fixture list.
- Acceptance gates: Hand-audited lineage, identity and deadline fixtures pass. A prediction-only
  update is marked as such, and uninstalled sensors supply no evidence.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### multi-source-reference-tracker-audit (optional)

This is the project's reference implementation, and it will have grown from the single-camera
baseline.

- Serves: `multi-source-reference-tracker` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: The mesh tracker stays a readable reference, with provenance kept from every
  observation to every output.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/reference/`, `tests/reference/`, `modules/reference-mesh/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  it repeats from `reference-sot-tracker`, every output with no recorded origin, and each deadline
  path.
- Acceptance gates: Hand-audited provenance, identity and deadline fixtures pass on frozen
  observation bundles. Every finding is fixed, routed to a task or dropped with its reason, and
  `make quality` passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Sensor-set evaluation -- `g2-sensor-set-evaluation`

#### sensor-set-suite

The mesh should keep only the sensors that earn their place.

- Serves: `g2-sensor-set-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: late-fusion-baseline, camera-front-end, non-camera-front-end.
- User-visible outcome: The `SENSOR_SET_FRONT_END` boundary shows what each sensor adds under one
  frozen fusion rule.
- Scope boundary: Feasible single, paired, all-installed and leave-one-out sets.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with per-sensor and leave-one-out fixtures.
- Acceptance gates: The oracle union is shown only as a ceiling. A sensor that adds nothing is
  reported as such.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### g2-sensor-set-evaluation-audit (optional)

Comparing sensor sets means little unless one frozen fusion rule runs every set and the achieved
result stays apart from the ceiling.

- Serves: `g2-sensor-set-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every sensor set runs through one frozen rule, with achieved quality and the
  observability ceiling kept apart.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from how
  a set is enumerated and what differs between runs of two sets.
- Acceptance gates: Single, paired, all-installed and leave-one-out sets run through one rule, and
  the two quality values never merge. Every finding is fixed, routed to a task or dropped with its
  reason, and `make quality` passes. Finding nothing is a valid result when the record states what
  was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Installed-system evaluation -- `installed-system-evaluation`

#### installed-system-suite

The whole mesh must be judged as installed, not only by parts.

- Serves: `installed-system-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: energy-metric-suite, mesh-reference-tracker.
- User-visible outcome: The `FULL_INSTALLED_SYSTEM` boundary reports quality, availability, deadlines
  and full-system energy from one trial.
- Scope boundary: The installed mesh. No component attribution from this score alone.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add the suite with recorded traces, including a sensor outage.
- Acceptance gates: Quality and energy come from the same trial, and an outage stays in the
  denominator.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### g2-boundary-report

The local G0 report does not yet expose the four separate mesh evaluation boundaries.

- Serves: `installed-system-evaluation` -- [Specification](../design/spec.md#10-run-artifacts-and-comparison-dashboard)
- Agent status: CLEAR
- Milestone: M3
- Dependencies: local-comparison-report, sensor-set-suite, fusion-suite, tracker-epoch-suite, installed-system-suite.
- User-visible outcome: One report shows front-end/sensor-set, fusion, tracking and full-system panels,
  comparable inputs, exposure, uncertainty, timing and energy evidence.
- Scope boundary: Extend the existing HTML/JSON report. No new dashboard service or component attribution
  from whole-system scores.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Render stored metrics from all four suites, with incompatible, missing-calibration,
  sensor-outage and unmeasured-energy fixtures.
- Acceptance gates: Each panel names its boundary and refuses incompatible comparisons. A missing quantity
  is explicit, and no component score is presented as whole-system quality.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

#### installed-system-evaluation-audit (optional)

A whole-system result sits beside component results, and a panel that blends them would claim what
no trial measured.

- Serves: `installed-system-evaluation` -- [Evaluation boundaries](../design/spec.md#66-four-independent-g2-evaluation-boundaries)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Component and whole-system results stay separate in every panel, each from
  one trial.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `src/ss_track/report/`,
  `tests/report/`, `$DATA_DIR/report/<run-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from how
  same-trial evidence is joined, and from what `g2-boundary-report` shares with the local report.
- Acceptance gates: Four local panels keep their boundaries, and quality, timing and energy of one
  row come from one trial. Every finding is fixed, routed to a task or dropped with its reason, and
  `make quality` passes. Finding nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### MOT and TrackEval -- `mot-trackeval`

#### trackeval-adapter

Genuine multi-object scenarios need a pinned evaluator on a supported Python.

- Serves: `mot-trackeval` -- [TrackEval adapter](../design/spec.md#8-trackeval-adapter-and-upgrade-policy)
- Agent status: CLEAR
- Milestone: M3
- Research: yes
- Dependencies: plugin-evaluator-core.
- User-visible outcome: A pinned TrackEval suite scores hand-audited MOT fixtures on Python 3.12.
- Scope boundary: Choose a patched fork, vendored copy or alternative evaluator, and replace the
  removed NumPy aliases. Energy stays outside it. A real MOT corpus is out of scope.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add byte-exact per-class export fixtures and the spec section 8 audit cases.
- Acceptance gates: Hand-audited perfect, miss, false positive, ID switch and ignore fixtures pass. A
  scenario the adapter cannot represent reports `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### mot-trackeval-audit (optional)

An adapter is only trusted while TrackEval computes the metrics and the adapter computes none.

- Serves: `mot-trackeval` -- [TrackEval adapter](../design/spec.md#8-trackeval-adapter-and-upgrade-policy)
- Agent status: CLEAR
- Milestone: M3
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: TrackEval alone computes MOT metrics, from a byte-exact export in a pinned
  environment.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  anything the adapter calculates itself, and from how the pin is enforced.
- Acceptance gates: Byte-exact per-class export fixtures and hand-audited MOT results hold. Every
  finding is fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding
  nothing is a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Paced thermal trial -- `paced-thermal-trial`

#### thermal-rig-controller (optional)

The rig needs software that holds chip temperature and proves it held.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: host-capability-probe.
- User-visible outcome: An off-host control loop holds a set-point, and a low-rate host log records
  temperature, frequency and throttle flags.
- Scope boundary: Software against a replaceable sensor and actuator interface. The physical rig is a
  human task.
- Data and artifact paths: `src/ss_track/thermal/`, `tests/thermal/`.
- Execution path: Add the loop with a simulated plant and recorded logs.
- Acceptance gates: Simulated runs settle inside the band under a load step. A temperature excursion
  during a scored segment marks the run invalid.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### temperature-run-orchestration (optional)

Heat must be the only difference between cool and hot runs.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: thermal-rig-controller, container-module-sandbox, hardware-trial-protocol.
- User-visible outcome: Blocks run identical frames at two set-points from clean state, plus an
  optional frequency-capped cool run.
- Scope boundary: Fresh container, dropped file cache, runner frame warm-up before timing, randomized
  order within blocks, a frequency cap, and setup energy reported apart.
- Data and artifact paths: `src/ss_track/thermal/`, `tests/thermal/`.
- Execution path: Add the block scheduler with a seeded order fixture and a marker for the timed
  interval.
- Acceptance gates: Fixtures prove module state does not carry between runs and order is balanced.
  Setup energy never enters ranked energy.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### thermal-effect-evaluation (optional)

A causal thermal claim needs a test separating frequency throttling from temperature.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: temperature-run-orchestration, development-decision-status.
- User-visible outcome: A suite reports the cool-to-hot change for any row, and all four bet
  conditions for a baseline.
- Scope boundary: Fixture evaluation. The live result is a human-lane task.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`.
- Execution path: Add hand-audited cool, hot and capped fixtures.
- Acceptance gates: An improvement, or a loss the capped arm does not reproduce, does not support the
  bet. A hot run with no throttling evidence reports `not_tested`.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### paced-thermal-trial-audit (optional)

A thermal claim needs heat to be the only difference, and a negative result must survive every
refactor.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Heat is the only difference between compared runs, and a negative outcome
  stays reported.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/thermal/`, `tests/thermal/`, `src/ss_track/suites/`,
  `tests/suites/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  difference between cool, hot and capped runs, and from how throttling is told from temperature.
- Acceptance gates: Hand-audited fixtures hold on identical frames, a hot run with no throttling
  stays `not_tested`, and a failed bet stays in the report. Every finding is fixed, routed to a task
  or dropped with its reason, and `make quality` passes. Finding nothing is a valid result when the
  record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Cohort ranking -- `benchmark-ranking`

#### rank-engine (optional)

Readers need one defensible rule for order.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: sot-suite, energy-metric-suite, hardware-trial-protocol, development-decision-status.
- User-visible outcome: A cohort yields ranks, tiers and unranked groups from saved scores and a
  versioned rules file.
- Scope boundary: Median-run choice, every-run floor, false-continuation cap, exposure minimum,
  anchored tiers, fault penalty, null row, independent-algorithm minimum and diagnostic column.
  Candidate IDs and versions are inputs; public eligibility policy is out of scope.
- Data and artifact paths: `src/ss_track/ranking/`, `tests/ranking/`, `scenarios/`.
- Execution path: Add table-driven fixtures from the
  [test plan](../design/perception-bench-test-plan.md). The rules file carries floors, margin, seed
  and resample count.
- Acceptance gates: Every ranking case in the test plan passes, including a penalty on the last tier,
  A-B-C overlap and an even valid-run count. Under the minimum, every row shows and no rank exists.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### benchmark-report-snapshot (optional)

A benchmark comparison needs an immutable, reproducible local report.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M4
- Dependencies: rank-engine, visibility-gate, thermal-effect-evaluation.
- User-visible outcome: One command builds a local HTML/JSON snapshot from frozen comparison bundles.
- Scope boundary: Reuse the local report renderer for ranked and unranked cohorts, thermal diagnostics
  and limits. Hosting, public branding and submissions are outside the project.
- Data and artifact paths: `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<snapshot-id>/`.
- Execution path: Add the builder with a sample cohort. The snapshot date is an input, so the build
  stays reproducible.
- Acceptance gates: A rebuild is byte-identical and older snapshots stay readable. An empty cohort shows
  the protocol and missing evidence; restricted input is refused for a shareable export.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### benchmark-ranking-audit (optional)

A rank is the most quoted output of the project, so every route around its minimum requirements must
be closed.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: CLEAR
- Milestone: M4
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: One rule produces every rank, and a row below the minimum stays unranked.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/ranking/`, `tests/ranking/`, `scenarios/`,
  `src/ss_track/report/`, `tests/report/`, `$DATA_DIR/report/<snapshot-id>/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from each
  route from a score to an order, and from what the snapshot shares with the local report.
- Acceptance gates: Scores recompute exactly, an inconclusive or refused cohort yields no rank, and
  a snapshot re-run gives the same bytes. Every finding is fixed, routed to a task or dropped with
  its reason, and `make quality` passes. Finding nothing is a valid result when the record states
  what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Device bench evaluation -- `device-bench-evaluation`

#### device-suite-and-adapter (optional)

Finished devices need a suite that works without an operator seed.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: CLEAR
- Milestone: M5
- Dependencies: installed-system-suite, event-schema-contract.
- User-visible outcome: A vendor adapter's events score detection delay, lock coverage and false
  alarms.
- Scope boundary: The suite, adapter contract and same-stimulus cohort key. A device that exposes
  telemetry rather than events uses a `telemetry-ingest` profile. Bench hardware is a human
  task.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `modules/`.
- Execution path: Add fixture events from two simulated devices.
- Acceptance gates: A device with no output path is `UNSUPPORTED`. Only same-stimulus, same-class,
  same-boundary cases are compared; incompatible or missing references are refused. Results
  are unranked and never pooled into a hardware-agnostic ranking.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/bench.md`.

#### device-bench-evaluation-audit (optional)

Device cases sit near ranked results, and must not gain a rank by sharing their code.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: CLEAR
- Milestone: M5
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Device results stay unranked, and missing device output stays `UNSUPPORTED`.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/suites/`, `tests/suites/`, `modules/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  the suite shares with ranked paths, and from each case with no operator seed.
- Acceptance gates: Same-stimulus fixtures stay valid, incompatible references are refused, and no
  device result reaches a rank. Every finding is fixed, routed to a task or dropped with its reason,
  and `make quality` passes. Finding nothing is a valid result when the record states what was
  reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Telemetry ingest -- `telemetry-ingest`

#### telemetry-bundle-store (optional)

Telemetry has nowhere to live as evidence, because import takes only video.

- Serves: `telemetry-ingest` -- [Telemetry bundles](../design/spec.md#182-telemetry-bundles)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: none.
- User-visible outcome: `ss-track telemetry import`, `stage` and `verify` turn a declared source into
  a sealed bundle of raw typed columns.
- Scope boundary: Contracts for the source declaration and the source and bundle records, the column
  store, and a declared CSV reader as the first format. No profiles, analysis or live capture.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/`,
  `$DATA_DIR/import/<source-sha256>/`, `$DATA_DIR/telemetry/<bundle-sha256>/`.
- Execution path: Reuse `sealed.py`, publish-by-rename and the source-terms checks by generalizing
  them, with no parallel copy. Store one little-endian file per field under a sealed index.
- Acceptance gates: Two stagings across data roots, and on x86-64 and arm64, give one hash. A float
  column round-trips bit-exact, including NaN payloads. A flipped column byte fails `verify` by name.
  Rights and retention refuse as they do for a recording.
- Documentation target: [Current implementation](current.md#areas), new page `current/telemetry.md`.

#### telemetry-profiles (optional)

A field name means nothing across firmware, so a value needs a canonical channel, unit and clock.

- Serves: `telemetry-ingest` -- [Profiles](../design/spec.md#183-profiles-and-canonical-channels)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-bundle-store.
- User-visible outcome: A versioned profile maps source fields to canonical channels at read, and
  `telemetry report` lists unmapped, absent and drifted fields.
- Scope boundary: Channel catalog and profile contracts, the observed-schema hash and the comparison.
  No format reader. A profile changes no bundle.
- Data and artifact paths: `contracts/telemetry/`, `src/ss_track/telemetry/`, `tests/telemetry/`.
- Execution path: Add the catalog and one profile over the CSV reader, with fixtures for each outcome
  of spec section 18.4.
- Acceptance gates: An unmapped field stays listed. An absent mapped field makes its channels
  `NOT_MEASURABLE`. A changed type or declared unit is `TELEMETRY_SCHEMA_DRIFT`. A new profile version
  fixing a unit changes no bundle hash, and a result names the profile version. A software-reported
  rail cannot become a calibrated `PowerSample`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### flight-log-readers (optional)

PX4 and ArduPilot logs carry their own schema, so one reader each covers every firmware.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: ULog and DataFlash logs stage into bundles, with dropouts, parameters and
  logged text retained.
- Scope boundary: Readers written from the format definitions with the standard library and NumPy.
  Example profiles for battery, attitude and position channels. No vehicle-health verdict.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `pyproject.toml`.
- Execution path: Walk framing once, then decode each message type as one array in bounded chunks.
  Generate logs in tests, and keep `pyulog` in the dev extra as an oracle.
- Acceptance gates: Values match the oracle and hand tables, across nested formats, multi-instance
  topics, absent trailing padding, `FMT`, `UNIT`, `MULT` and `FMTU`. An unknown incompatible flag
  refuses, an unknown message is skipped and counted, and a log cut mid-message loses only that
  message. The measured decode rate on each CI architecture is recorded.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### board-telemetry-sources (optional)

A board's counters explain timing and throttling, and each vendor exposes them differently.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles, host-capability-probe.
- User-visible outcome: A recorded or sampled hwmon, thermal, cpufreq, devfreq and powercap tree,
  `vcgencmd` output and `tegrastats` lines become bundles, with profiles for Raspberry Pi 5, Jetson
  and a generic x86 host.
- Scope boundary: Unprivileged reads through a replaceable root, sharing one source with
  `host-capability-probe`. Accelerator vendor tools stay out until a selected host needs one.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/telemetry/`.
- Execution path: Add recorded-tree fixtures, select chips by `name` and channels by label, and keep
  raw ABI integers in columns with their units in the profile.
- Acceptance gates: Hand-computed values match, including `get_throttled` bits and an `energy_uj`
  wrap. Renumbered hwmon directories change nothing. `tegrastats` lines with absent engines parse with
  those channels absent. A value re-read within `update_interval` is not a new sample. A root-only
  source is `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### mavlink-log-reader (optional)

A ground station's telemetry log needs an external dictionary, and its time is arrival time.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A `.tlog` stages into a bundle under a pinned MAVLink XML dialect.
- Scope boundary: Reading MAVLink 1 and 2 frames only. Nothing is ever sent, so signing verification
  is out of scope.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/external/`.
- Execution path: Compile a dialect to record layouts, applying wire order and `CRC_EXTRA`, then reuse
  the array decode path.
- Acceptance gates: Hand vectors cover field reordering, truncated trailing zeros, extension fields
  and a signed frame. A `CRC_EXTRA` mismatch is named as a dictionary mismatch. An unknown message id
  and an unknown incompatible flag are counted. Log times are recorded as arrival times.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### blackbox-log-reader (optional)

Blackbox logs hold high-rate flight data with no checksum, so damage must stay visible.

- Serves: `telemetry-ingest` -- [Drift, loss and gaps](../design/spec.md#184-drift-loss-and-gaps)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A Betaflight Blackbox file stages each session into a bundle.
- Scope boundary: The documented encodings and predictors, written from the public description. iNav
  differences are out of scope until a sample exists.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`.
- Execution path: Parse `H` field lines into a per-frame schema, then reverse each encoding and
  predictor, and add hand-encoded fixtures.
- Acceptance gates: Every encoding and predictor matches a hand-computed frame. A dropped byte rejects
  that frame and following `P` frames until the next `I`, with the counts recorded. Sessions in one
  file stay separate, and rejected frames are never interpolated.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### mcap-log-reader (optional)

ROS 2 bags and other robotics logs use MCAP, which carries each channel's schema in the file.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: An MCAP file stages into a bundle, with one observed schema per channel.
- Scope boundary: Channels with `protobuf` or `jsonschema` schemas, and a `cdr` subset for fixed
  layouts. Zstd and LZ4 sit in an optional extra. Image and point-cloud payloads stay opaque blobs
  with their hashes.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `pyproject.toml`.
- Execution path: Read opcode-framed records, with the summary section when present and a scan when
  not. Keep `mcap` in the dev extra as an oracle.
- Acceptance gates: Chunked and unchunked files match the oracle. A CRC mismatch refuses, an unknown
  record is skipped and counted, `log_time` and `publish_time` stay separate, and a file with no
  summary reads by scanning.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### declared-binary-layouts (optional)

A simple sensor should need a declaration, not a new reader.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A profile declares a fixed record or TLV layout, or reads an IIO
  `scan_elements` tree, and the source stages with no new code.
- Scope boundary: Fixed records, tagged length-value frames, a magic word, and bit fields with a
  shift. A format needing more is refused with a reason and gets a reader.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/telemetry/`.
- Execution path: Compile a layout to a NumPy dtype, parse the IIO `type` grammar, and add one radar
  TLV profile pinned to its SDK version.
- Acceptance gates: Hand cases cover `le:s12/16>>4`, big-endian, repeats and channel order. A TLV
  fixture passes with no code beyond the profile. An unknown TLV type is skipped and counted. A
  declared size that disagrees with a frame refuses.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### camera-telemetry-readers (optional)

A camera's motion and exposure metadata can explain blur and loss, and it arrives beside the video.

- Serves: `telemetry-ingest` -- [Source classes](../design/spec.md#181-source-classes-and-readers)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles.
- User-visible outcome: A GoPro GPMF track and a libcamera per-frame metadata sidecar stage into
  bundles linked to their video source.
- Scope boundary: Reading only. Tying samples to frames follows section 5 clock rules. Other camera
  vendors wait for a sample.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`.
- Execution path: Read the `gpmd` track, parse KLV with `SCAL`, `SIUN`, `TYPE` and `TSMP`, and keep
  `py-gpmf-parser` in the dev extra as an oracle.
- Acceptance gates: Hand KLV fixtures cover nesting, scale, complex types and alignment. Payload time
  never assumes a uniform rate inside a payload. GNSS channels are `sensitive`. A `SensorTimestamp`
  from a pipeline that fills it from DMA time is not labelled as exposure time.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### live-telemetry-capture (optional)

Real-time streams must lose data visibly, and must never slow what they observe.

- Serves: `telemetry-ingest` -- [Live streams](../design/spec.md#185-live-streams)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: board-telemetry-sources, declared-binary-layouts, mavlink-log-reader.
- User-visible outcome: `ss-track telemetry record` writes sealed segments from a sysfs poll, IIO
  buffer, serial link or UDP mirror, with loss accounting.
- Scope boundary: Passive sources through bounded queues. Sending anything to a source is out of
  scope. Synchronized multi-sensor capture stays with `synchronized-sensor-capture`.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`,
  `$DATA_DIR/telemetry/<bundle-sha256>/`.
- Execution path: Use replaceable sources and fake clocks, add a declared capture contract, and
  measure the sustainable rate per host.
- Acceptance gates: Overflow, disconnect and recovery fixtures account for all loss with time ranges.
  A killed process leaves only complete segments. A fixture source shows nothing was written to it. A
  declared rate above the measured one is `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### telemetry-analysis-report (optional)

Stored columns help nobody until they answer what ran, what was lost and what changed.

- Serves: `telemetry-ingest` -- [Drift, loss and gaps](../design/spec.md#184-drift-loss-and-gaps)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: flight-log-readers.
- User-visible outcome: `ss-track telemetry report` gives per-channel rates, gaps, dropouts, ranges
  and throttle and thermal timelines, and compares the schema and rates of two bundles.
  `telemetry export` writes Parquet, Arrow or CSV.
- Scope boundary: Local HTML and JSON, descriptive statistics only. No safety, airworthiness or
  health verdict. `pyarrow` is an optional extra, and an export is never evidence.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: Compute from columns through a named profile, and add two fixture firmware versions
  of one log.
- Acceptance gates: Hand-computed rates and gap lists match. Two firmware fixtures show their schema
  difference exactly. A restricted bundle refuses a shareable export without leaking a value, and a
  shareable export holds no `sensitive` channel uncoarsened. Exported values equal the columns.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### telemetry-corpus-streams (optional)

Platform telemetry beside a video encounter must obey the same split and rights rules.

- Serves: `telemetry-ingest` -- [Boundary](../design/spec.md#186-boundary)
- Agent status: CLEAR
- Milestone: M6
- Dependencies: telemetry-profiles, g2-scenario-observation-bundles.
- User-visible outcome: A telemetry bundle joins an encounter as a platform-state stream, and replay
  releases it at its availability time.
- Scope boundary: Split, rights and clock rules for one more stream kind. A platform-state sample
  stays context and is never an object detection.
- Data and artifact paths: `src/ss_track/corpus/`, `src/ss_track/telemetry/`, `tests/corpus/`.
- Execution path: Extend the corpus declaration by an optional field under a minor contract version,
  and extend the frame set to name telemetry bundles.
- Acceptance gates: A corpus using no telemetry keeps every hash. A telemetry stream inherits its
  encounter's split, and a source crossing splits is `SPLIT_LEAKAGE`. With no declared clock relation,
  alignment with video is `NOT_MEASURABLE`.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

#### telemetry-ingest-audit (optional)

Readers, stores and reports arrive one format at a time, which is where a reader-specific rule and
a filled gap are most likely to appear.

- Serves: `telemetry-ingest` -- [Telemetry bundles](../design/spec.md#182-telemetry-bundles)
- Agent status: CLEAR
- Milestone: M6
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Every reader follows one interface and one rule for time, loss and drift,
  and nothing fills a gap.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/telemetry/`, `tests/telemetry/`, `contracts/`,
  `$DATA_DIR/import/<source-sha256>/`, `$DATA_DIR/telemetry/<bundle-sha256>/`,
  `contracts/telemetry/`, `pyproject.toml`, `contracts/external/`, `$DATA_DIR/run/<run-id>/`,
  `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from what
  the readers repeat, which reader could become a declared layout, and how each one reports loss and
  clock source.
- Acceptance gates: Readers match an independent reader on generated logs, bundles hash identically
  across hosts, and drift, loss and truncation are reported and never filled. Every finding is
  fixed, routed to a task or dropped with its reason, and `make quality` passes. Finding nothing is
  a valid result when the record states what was reviewed.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.

### Documentation integrity -- `documentation-integrity`

#### plan-dependency-integrity (optional)

Structural checks pass even when a task depends on nothing real, so gating can drift unnoticed.

- Serves: `documentation-integrity` -- [Planning integrity](../design/spec.md#documentation-and-planning-integrity)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `make lint-spec-plan` rejects unknown dependencies and cycles across both lanes,
  including dependencies hidden in wrapped fields; plan status distinguishes priority from readiness.
- Scope boundary: Dependency parsing and graph checks only. Registry order remains capability priority;
  later groups can supply earlier groups through explicit task dependencies. Milestones form
  the DAG in the engine design, not a numeric barrier. Semantic review remains necessary.
- Data and artifact paths: `src/ss_track/quality/plan_model.py`,
  `src/ss_track/quality/plan_integrity.py`, `tests/quality/`.
- Execution path: Parse wrapped fields, then add the checks with failing fixtures. Read an audit's
  `every other agent task in this group` as a dependency on each of them.
- Acceptance gates: Fixtures reject unknown IDs, cycles and required tasks that depend on optional work,
  and accept valid cross-lane dependencies. A blocked earlier task is never reported as ready, and an
  audit is not ready while another agent task of its group is open.
- Documentation target: [Governance](current/governance.md).

#### documentation-integrity-audit (optional)

A rule stated in prose can drift from the checker, and a rule nobody can check is one nobody keeps.

- Serves: `documentation-integrity` -- [Planning integrity](../design/spec.md#documentation-and-planning-integrity)
- Agent status: CLEAR
- Milestone: M1
- Effort: high
- Dependencies: every other agent task in this group.
- User-visible outcome: Each rule in `AGENTS.md` that a machine can check is checked, and each check
  has a failing fixture.
- Scope boundary: What this group built, with its seams to neighboring groups, under the [group
  audit](../guide/planning-workflow.md#group-audits) rules. A refactor moves no sealed byte, hash,
  score or refusal code.
- Data and artifact paths: `src/ss_track/quality/plan_model.py`,
  `src/ss_track/quality/plan_integrity.py`, `tests/quality/`.
- Execution path: Run the [group audit](../guide/planning-workflow.md#group-audits). Start from
  `AGENTS.md`, the planning workflow and the planning integrity section of the specification
  against `plan_integrity.py`, `plan_model.py`, `plan_summary.py` and `doc_links.py`.
- Acceptance gates: Every checked rule has a failing fixture, every stated rule is checked or named
  as human judgment, and the checker is tightened or unchanged. Every finding is fixed, routed to a
  task or dropped with its reason, and `make quality` passes. Finding nothing is a valid result when
  the record states what was reviewed.
- Documentation target: [Governance](current/governance.md).

## Human-Assisted Tasks

Follow the [hardware support flow](../design/test-stands.md#selection-flow).
Acquisition and physical operation require the responsible person; agent tooling
prepares protocols, analyzes evidence and produces reviewable selection records.

### Corpus provenance -- `corpus-provenance`

#### select-development-workload

Software development needs authorized footage with a declared task and useful negative cases.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: none.
- User-visible outcome: One candidate workload has recorded terms, and the owner knows how close it
  is to the small-target stress case.
- Scope boundary: Authorized private or public development sources, benchmarking rights, retention and
  access restrictions. Public redistribution is a separate permission, never a G0a prerequisite.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/`, with source terms and hashes.
- Execution path: The owner checks source terms and selects positive/negative encounters; original
  controlled recordings are an alternative when no existing source fits.
- Acceptance gates: Every source has recorded rights, a retention date, a derived-frame permission and
  task suitability. With no authorized source,
  real-data claims remain unavailable while fixture implementation continues.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### define-locked-test-policy (optional)

A locked test needs a named custodian and access rules that no software can supply.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: select-development-workload.
- User-visible outcome: A named custodian holds a written access policy, so a locked split can
  support a held-out claim.
- Scope boundary: The spec section 15 custodian and access inputs. Runner enforcement belongs to
  `locked-split-guard`.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/`, with the policy hash.
- Execution path: The owner names a custodian and records who may read, tune against or re-score
  locked material.
- Acceptance gates: A hashed policy exists before any locked evaluation. With no custodian, a
  `locked` split stays membership only and no held-out claim is made.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Annotation and selection -- `annotation-selection`

#### label-pilot-encounters

G0a needs only one positive and one negative encounter, so it should not wait for the whole corpus.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: select-development-workload, annotation-review-tools.
- User-visible outcome: Two encounters have frozen labels, selections and masks.
- Scope boundary: The pilot encounters, including motion events. The pass also measures labelling
  time per encounter.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Two reviewers label and settle disagreements under a named authority.
- Acceptance gates: Validation passes and the revision is frozen and hashed. Unresolved labels remain
  unknown; time spent labelling is recorded as planning evidence.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

#### label-development-corpus (optional)

Within-corpus comparisons need reviewed labels across independent encounters.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: label-pilot-encounters.
- User-visible outcome: At least 10 independent encounter groups have frozen labels.
- Scope boundary: Labelling and review. The sample-size pilot may add groups, and larger corpora may
  use a declared review sample plus all difficult cases.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: Two reviewers label and settle disagreements under a named authority.
- Acceptance gates: Validation passes, groups are independent by the spec section 4.1 rule, and the
  revision is frozen. Unlabelable objects stay `unknown`.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.

### Controlled bench, timing and energy -- `controlled-bench-timing-energy`

#### acquire-bootstrap-bench

The measuring tools need hardware to run on, so the first meter and host are a declared bootstrap.

- Serves: `controlled-bench-timing-energy` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: HUMAN-GATED
- Milestone: M2
- Dependencies: none.
- User-visible outcome: One bootstrap host with fast storage and a logging meter are on the bench,
  with the reason for each choice recorded.
- Scope boundary: Stand A requirements A1 to A7 in the [test stands](../design/test-stands.md). An
  onboard PMIC reading does not qualify as the meter. The bootstrap host can still lose
  `select-reference-host`.
- Data and artifact paths: `scenarios/stands/`, `$DATA_DIR/selection/<selection-id>/`,
  `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: Before acquisition, freeze Stand A requirements and candidate budgets from the declared
  software workload: schedule, latency/loss tolerance, storage, interfaces, average/peak power,
  energy per task and thermal limit. Record measurement precision, meter rate, maximum gap,
  alignment method and acceptance tolerances, then compare available or borrowed instruments.
- Acceptance gates: The meter meets the declared rate, gap and alignment, has a calibration record,
  and passes a known-load check. If none fits, energy stays `NOT_MEASURABLE` and requirements return
  to the spec.
- Documentation target: [Current implementation](current.md#areas), new page
  `current/hardware-selection.md`.

#### calibrate-bench-instruments

Bench evidence needs checked instruments and a measured harness cost.

- Serves: `controlled-bench-timing-energy` -- [Hardware metrology](../design/spec.md#79-hardware-metrology-and-measurement-algorithms)
- Agent status: BLOCKED BY HUMAN
- Milestone: M2
- Dependencies: acquire-bootstrap-bench, hardware-trial-protocol, paced-frame-release,
  module-image-recipes.
- User-visible outcome: A checked bench reports known-load results, pacing jitter, NVMe staging
  throughput and null-module energy.
- Scope boundary: Preflight, marker alignment and harness cost. Module results are out of scope.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person connects the instruments, and an agent runs the protocol with the null
  module in its container at the declared schedule.
- Acceptance gates: Known-load and marker checks pass, raw traces are retained, the selected-host hostile
  container fixture passes, and the harness sustains the declared schedule. A failed check blocks
  only affected claims and states its cause.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Hardware selection -- `hardware-selection`

#### select-reference-host

Benchmark and reference-tracker measurements need a host chosen from evidence.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: BLOCKED BY HUMAN
- Milestone: M2
- Dependencies: hardware-selection-report, calibrate-bench-instruments, reference-sot-tracker.
- User-visible outcome: A selection record names the reference host, with measured evidence for each
  candidate.
- Scope boundary: At least two available candidates against Stand A, including the bootstrap host.
  Optional thermal-rig compatibility is recorded separately from core benchmark suitability.
- Data and artifact paths: `$DATA_DIR/selection/<selection-id>/`, `$DATA_DIR/run/<run-id>/`,
  `scenarios/stands/`.
- Execution path: A person obtains approved candidates; an agent runs probe, null-module and
  reference-tracker trials on each under the same declared workload and limits, then stages the fixed
  corpus on each from sources carried from x86-64 and compares them with `ss-track corpus compare`.
- Acceptance gates: Each measured candidate has traceable evidence, rejection reasons and a staged-hash
  comparison on the candidate itself. A comparison of `different` names each source and narrows that
  host's claim to the sources it does not name. A single available candidate is a provisional choice,
  not a comparative selection. No qualifying host is valid; revise the requirement before claiming
  support.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

#### shortlist-mesh-sensors

A characterization stand needs candidate interfaces before any final sensor choice exists.

- Serves: `hardware-selection` -- [Specification](../design/spec.md#164-hardware-selection)
- Agent status: HUMAN-GATED
- Milestone: M3
- Dependencies: select-reference-host.
- User-visible outcome: A provisional inventory and versioned Stand B/C requirements are ready
  for trials.
- Scope boundary: Candidate availability, evidence roles, task coverage, geometry/clock tolerances, sustained
  modes and resource budgets. No candidate is yet selected as measured.
- Data and artifact paths: `scenarios/stands/`, `$DATA_DIR/selection/<selection-id>/`.
- Execution path: A person obtains approved candidates and documents raw formats, drivers, access conditions,
  independent reference needs and a minimum test for each required quantity.
- Acceptance gates: Every candidate has an executable measurement plan and a supported software need.
  Missing references or unaffordable candidates remain unmeasured with the limitation recorded.
- Documentation target: [Current implementation](current.md#areas), page `current/hardware-selection.md`.

#### select-mesh-sensors

The reference mesh needs a sensor set chosen on evidence.

- Serves: `hardware-selection` -- [Hardware selection](../design/spec.md#164-hardware-selection)
- Agent status: HUMAN-GATED
- Milestone: M3
- Dependencies: hardware-selection-report, joint-mode-probe, run-camera-characterization,
  shortlist-mesh-sensors.
- User-visible outcome: A selection record names two visible cameras, one non-camera source and the
  compute host for Stand C.
- Scope boundary: Candidates from the spec section 7.6 registry, each with a declared evidence role.
  Audio and active emitters need their spec section 11 rules first.
- Data and artifact paths: `$DATA_DIR/selection/<selection-id>/`, `scenarios/stands/`.
- Execution path: Measure candidate non-camera task observability and timing against the independent
  reference, then joint-mode and installed-boundary energy trials. Use generic raw logging before
  the production front end exists. Compare all required evidence through `ss-track hardware-select`.
- Acceptance gates: The chosen set satisfies frozen quality, coverage, timing and resource limits with
  uncertainty; each rejected or unmeasured option is recorded. A transport-only pass is insufficient.
  No qualifying set returns to the requirements without inventing a selection.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

### Camera bench characterization -- `camera-bench-characterization`

#### build-sensor-test-stand

Sensors can only be judged against a reference they do not control.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: HUMAN-GATED
- Milestone: M3
- Dependencies: shortlist-mesh-sensors, calibrate-bench-instruments.
- User-visible outcome: Stand B and Stand C exist, with a controlled target, an independent reference
  and a time marker.
- Scope boundary: Stand B and C requirements and the provisional candidate interfaces. Construction
  precedes final sensor selection; field sites are out of scope.
- Data and artifact paths: `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: A person builds the stands, and an agent checks them with marker fixtures.
- Acceptance gates: The reference trace is independent of every tested sensor. Any requirement the
  stand cannot meet is recorded, and its claim stays closed.
- Documentation target: [Current implementation](current.md#areas), page
  `current/hardware-selection.md`.

#### run-camera-characterization

Fusion needs calibrated sensors with known limits.

- Serves: `camera-bench-characterization` -- [Capture and optics](../design/spec.md#792-capture-optics-and-geometric-sensing)
- Agent status: BLOCKED BY HUMAN
- Milestone: M3
- Dependencies: build-sensor-test-stand, camera-trial-suite.
- User-visible outcome: Each camera has measured capture, optics and timing results.
- Scope boundary: Shortlisted camera candidates on the stand before final selection. No field-range claim.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person operates the stand, and an agent runs the protocol.
- Acceptance gates: Raw evidence reproduces each estimate. A mode that fails stays `UNSUPPORTED`.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Sensor adapters and front ends -- `sensor-adapter-frontends`

#### record-mesh-encounters

Fusion evaluation needs synchronized recordings with independent truth.

- Serves: `sensor-adapter-frontends` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: BLOCKED BY HUMAN
- Milestone: M3
- Dependencies: synchronized-sensor-capture, run-camera-characterization, annotation-review-tools.
- User-visible outcome: Authorized bench encounters exist with per-sensor opportunity labels and a
  disjoint calibration split.
- Scope boundary: Bench recordings. New public-space capture needs its spec section 11 approvals.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: A person records and reviews, and an agent imports the streams.
- Acceptance gates: Every stream shares its encounter and split; hashes, clock markers, calibration and
  opportunity masks are frozen. Independent reviewers settle cross-sensor identity and negative
  cases. Calibration and evaluation encounters are disjoint; unsupported truth stays unknown.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Installed-system evaluation -- `installed-system-evaluation`

#### run-mesh-trials

The project's second goal needs a measured result.

- Serves: `installed-system-evaluation` -- [Reference sensor mesh](../design/spec.md#165-reference-sensor-mesh)
- Agent status: BLOCKED BY HUMAN
- Milestone: M3
- Dependencies: record-mesh-encounters, g2-boundary-report, build-sensor-test-stand.
- User-visible outcome: The reference mesh has results at all four boundaries, including what each
  sensor adds.
- Scope boundary: The selected sensor set on Stand C. No field-range or safety claim.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person operates the stand, and an agent runs each boundary's scenario.
- Acceptance gates: All four boundaries report through the local report, with faults and exposure shown.
  Recompute matches stored results. A sensor that adds nothing is documented; its selection record
  is revised from evidence and a reduced configuration starts a new cohort.
- Documentation target: [Current implementation](current.md#areas), page `current/sensor-mesh.md`.

### Paced thermal trial -- `paced-thermal-trial`

#### build-thermal-rig (optional)

The thermal claim needs physical control of chip temperature.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: select-reference-host, thermal-rig-controller.
- User-visible outcome: A rig holds the chip at declared set-points with its power outside the
  boundary, and the host's throttle onset is measured.
- Scope boundary: Stand A requirements A8 to A12 in the [test stands](../design/test-stands.md). The
  board's own fan header stays unused.
- Data and artifact paths: `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: A person builds the rig, and an agent tunes the controller and measures throttle
  onset from frequency evidence.
- Acceptance gates: The chip stays in band through a full segment under load at a hot set-point at or
  above onset. If it cannot, the owner chooses another thermal method and the spec changes first.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### run-thermal-experiment (optional)

The thermal mechanism needs a measured result, including a valid negative outcome.

- Serves: `paced-thermal-trial` -- [Paced thermal trial](../design/spec.md#162-paced-thermal-trial)
- Agent status: BLOCKED BY HUMAN
- Milestone: M4
- Dependencies: build-thermal-rig, calibrate-bench-instruments, thermal-effect-evaluation,
  load-calibrated-baseline, label-development-corpus.
- User-visible outcome: The owner knows whether heat costs tracking quality on the reference host.
- Scope boundary: Reference baselines, including the load-calibrated one. The result tests the
  mechanism and does not establish the behavior of other trackers.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person supervises the bench, and an agent runs cool, hot and capped runs under
  the declared protocol.
- Acceptance gates: All four conditions are evaluated and traces retained. No effect above noise or a
  non-reproducing capped arm is a valid negative result. No throttling reports `not_tested`
  without blocking the core benchmark or mesh.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Cohort ranking -- `benchmark-ranking`

#### run-sample-size-pilot (optional)

The comparison precision and tier margin should come from measurement.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: BLOCKED BY HUMAN
- Milestone: M4
- Dependencies: run-thermal-experiment.
- User-visible outcome: The owner sees floor-interval widths, energy rerun noise, and any extra
  labels needed.
- Scope boundary: Baseline-only interval width and rerun noise. Record a target precision and expansion
  limit before the pilot; baseline precision does not guarantee candidate precision.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Measure interval width and rerun noise on baselines over the labelled corpus. Any
  added groups return to `label-development-corpus`.
- Acceptance gates: Width and noise are recorded per baseline. If the precision target cannot be met,
  report insufficient evidence and revise the protocol before candidate comparisons.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### freeze-benchmark-protocol (optional)

Rules must be fixed before anyone's result is known.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: run-sample-size-pilot, tracker-compatibility-preflight.
- User-visible outcome: A versioned protocol pins workload, floors, margin, set-points, schedule, deadline,
  repetitions, bootstrap seed, resample count and maximum half-width before comparison runs.
- Scope boundary: Measurement parameters and a stated basis for each. Public eligibility, commercial
  terms, disputes and publication decisions are outside this task.
- Data and artifact paths: `scenarios/benchmark/rules-v1.yaml`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A human reviewer accepts the evidence-based protocol; an agent records values and hashes.
- Acceptance gates: Every rule has a value and a basis before comparison runs, and the rules hash
  enters the cohort key. A rule with no defensible value returns to the spec.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### run-benchmark-comparison (optional)

The comparison software needs end-to-end evidence on reference and candidate modules.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: BLOCKED BY HUMAN
- Milestone: M4
- Dependencies: freeze-benchmark-protocol, benchmark-report-snapshot, module-image-recipes.
- User-visible outcome: Candidates, baselines and the null module have full blocks under a
  frozen protocol.
- Scope boundary: Declared module versions only, under the frozen protocol. Public entry operations
  and publication are outside the task.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`, `$DATA_DIR/trial/<trial-id>/`.
- Execution path: A person supervises the bench; an agent runs each module's blocks with balanced order.
- Acceptance gates: Every run is kept with its status. Below the minimum, every row is shown and no
  rank is published.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

#### independent-rerun-check (optional)

Reproducibility needs a second person to follow the software instructions.

- Serves: `benchmark-ranking` -- [Cohort ranking](../design/spec.md#161-cohort-ranking)
- Agent status: HUMAN-GATED
- Milestone: M4
- Dependencies: run-benchmark-comparison.
- User-visible outcome: A second person recomputes every row and re-runs one available open module
  or reference baseline, even when no row qualifies for ranking.
- Scope boundary: Recompute and Re-run levels. Re-measure is not required.
- Data and artifact paths: `$DATA_DIR/run/<run-id>/`.
- Execution path: A second person follows only the documented commands and recorded image references.
- Acceptance gates: Scores match exactly at Recompute and within the declared tolerance at Re-run. A
  failure limits the reproducibility claim and its cause is recorded for repair.
- Documentation target: [Current implementation](current.md#areas), page `current/evaluation.md`.

### Device bench evaluation -- `device-bench-evaluation`

#### build-device-bench-scene (optional)

Finished devices need one shared physical stimulus, as Stand D requires.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: HUMAN-GATED
- Milestone: M5
- Dependencies: device-suite-and-adapter.
- User-visible outcome: A controlled object and independent reference exercise each device equally.
- Scope boundary: One device class. Field trials and range claims are out of scope.
- Data and artifact paths: `$DATA_DIR/instruments/<instrument-id>/`.
- Execution path: A person builds the scene, and an agent validates it with fixtures.
- Acceptance gates: The reference trace is independent of the tested camera. If two devices cannot
  face the same stimulus, the class stays unranked.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

#### run-device-trials (optional)

The device suite needs measured conformance and validity evidence.

- Serves: `device-bench-evaluation` -- [Device bench evaluation](../design/spec.md#166-device-bench-evaluation)
- Agent status: BLOCKED BY HUMAN
- Milestone: M5
- Dependencies: build-device-bench-scene, device-suite-and-adapter, hardware-trial-protocol.
- User-visible outcome: Available devices have unranked measured cases under a predeclared protocol.
- Scope boundary: One device class with a complete boundary and two units or a single-unit label.
  Vendor enrollment, public naming, release policy and publication are outside the task.
- Data and artifact paths: `$DATA_DIR/trial/<trial-id>/`.
- Execution path: Freeze stimulus, reference, windows and measurement limits before acquisition.
  A person operates the stand; an agent records events and scores the retained bundles.
- Acceptance gates: All attempts and limits remain visible. No available device is a valid negative result,
  and one device can yield an individual case without a comparative claim.
- Documentation target: [Current implementation](current.md#areas), page `current/bench.md`.

### Telemetry ingest -- `telemetry-ingest`

#### collect-telemetry-samples (optional)

Generated logs prove a reader only against the format as understood, and real firmware is where that
understanding fails.

- Serves: `telemetry-ingest` -- [Telemetry evaluation](../design/spec.md#187-evaluation)
- Agent status: BLOCKED BY HUMAN
- Milestone: M6
- Dependencies: flight-log-readers, board-telemetry-sources.
- User-visible outcome: Authorized real logs from named boards and firmware pass each reader, or name
  exactly where it fails.
- Scope boundary: Owned or licensed samples from any available board, restricted by default. No
  purchase is required. A sensitive device stays restricted under the measurement-only scope.
- Data and artifact paths: `$DATA_DIR/import/<source-sha256>/`, `$DATA_DIR/run/<run-id>/`.
- Execution path: A person supplies logs and their rights, and an agent stages them and records what
  each reader covered.
- Acceptance gates: Each sample passes or yields a named reader defect. With no available log, a
  reader stays documented as checked against generated fixtures only, which is a valid negative
  result.
- Documentation target: [Current implementation](current.md#areas), page `current/telemetry.md`.
