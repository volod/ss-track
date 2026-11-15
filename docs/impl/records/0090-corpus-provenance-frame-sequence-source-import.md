# Frame sequence source import

## Task and scope

- Id / capability: `frame-sequence-source-import` / `corpus-provenance`
- State: accepted
- Source: plan task at `a0fab37`; no unrelated dirty files.
- Plan counts at start: 133 agent, 28 human; next agent `frame-sequence-source-import`, next human `define-locked-test-policy`.
- Accepted task:

```markdown
#### frame-sequence-source-import (optional)

Public airborne-observer collections often ship as numbered images, and import accepts one video
stream of one file, so such a source cannot enter a corpus.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A recording declares an ordered image sequence as its source, and import,
  build, stage and verify treat it as they treat a video stream.
- Scope boundary: Lossless image files in a declared order, with one source identity over the
  ordered file hashes. A sequence stores no presentation time, so its timestamp quality is
  `missing` unless the declaration states a frame rate, which makes it `derived`. No lossy image
  format, no resampling and no reordering by guesswork.
- Data and artifact paths: `contracts/declaration/recording/`, `contracts/record/source-manifest/`,
  `src/ss_track/corpus/sources/`, `src/ss_track/corpus/decoding/`, `tests/corpus/`.
- Execution path: Evolve both contracts under the spec section 17.3 rules, read each image through
  the pinned decoder into the canonical pixel format, and add fixtures with a missing index, a
  changed image and mixed dimensions.
- Acceptance gates: One sequence imported twice gives one source identity and one bundle hash. A
  missing index, a changed image and mixed dimensions are each refused by name. Time-based scores
  of a sequence with no declared rate are unavailable with their cause, and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment authorized by the user: update current contracts and data flow in place without
  historical-format compatibility; remove obsolete historical data and regenerate affected corpus
  evidence as needed. The plan execution path now reflects this direction.

## Implementation

Recording declarations now accept explicit ordered PNG membership, required per-image hashes and
an optional rational frame rate. Import copies and checks images before decoding retained bytes;
the aggregate identity hashes ordered image hashes under an image-sequence domain tag. Paths and
rate do not affect identity. A sealed inventory records membership and timing, and the source
manifest pins its bytes. Changed, missing and extra retained members are refused. The existing
shared decode entry point serves build/stage, near-duplicate sampling and redecode; amendments
continue to work after originals are removed. Video behavior uses the same existing path.

New focused modules are `declarations/image_sequence.py`, `sources/image_sequence.py` and
`decoding/image_sequence.py`. The source inventory uses the shared sealed-record reader, not a
parallel JSON parser. Contracts add recording/source-manifest optional fields at 3.1.0 and an
image-sequence inventory at 1.0.0. The registry retains its existing version gate; no historical
compatibility layer was added for this work. No dependency, CLI command or environment change.
Imported images and inventories are evidence, not a new clean kind. PNG is the supported lossless
image format; other codecs are explicitly refused. No filename sorting or resampling is performed.
See [Corpus](../current/corpus.md#ordered-image-sequences) and
[Contracts](../current/contracts.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Repeat identity and bundle hash | `tests/corpus/sources/test_image_sequence.py` | Pass for missing rate, 25, 1 and 30000/1001 fps |
| Missing index, changed image, dimensions | `test_bad_sequence_is_refused` | Pass; failures name the member or index |
| Full corpus flow | `test_sequence_import_build_stage_repeats` | Pass: build, stage, verify, redecode, amendment, sampled reads |
| Missing timing stays unavailable | Same test, `StreamTiming.unmappable()` | Pass: missing PTS/time base and `missing_timestamps`; no invented durations |
| Integrity and governance | Retained membership, rate conflict and amendment tests | Pass: inventory, missing/extra/changed images and removed originals |
| Strict decoder | `tests/corpus/decoding/test_image_sequence.py` | Pass: order, rate, dimensions and sequence-wide deadline |
| CI | `make ci` | Pass: 2442 passed, 115 deselected |

## Audit handoff

- AUD-frame-sequence-source-import-1: The scoring engine is scheduled work, so there is no shipped
  time-based score to exercise. Current frame metadata and temporal mapping preserve missing timing
  and its explicit cause. Nonblocking owner: `plugin-evaluator-core`, amended to require unavailable
  time metrics with `missing_timestamps` for these sequence inputs. This does not add a scoring
  engine to the corpus importer.
- Reviewed source identity, sealing, file copying, failure cleanup, timestamp claims, sampling,
  redecode, amendments, retained membership and corpus boundaries. Findings fixed here: the source
  directory must remain searchable, inventories must use the shared sealed reader, and the decode
  deadline must cover the whole sequence. PNG-only support is an explicit supported-format boundary,
  not inferred acceptance of TIFF or BMP containers that may themselves contain lossy compression.
- Markdown lint also reports pre-existing long lines in closed records 0086 and 0087. Dropped as an
  unrelated formatting chore; closed records are not rewritten. Current pages touched here were
  wrapped where needed.

## Close or resume

All corpus import acceptance gates passed. `make ci` completed with 2442 passing tests and
115 external tests deselected by its standard light-test lane. Targeted integration and static
checks also passed. Current corpus and contract pages now document available behavior and link
this record; the records index includes it. Removed the completed plan block and replaced the
source-authorization task's obsolete dependency with the supported-source boundary. The group audit
retains the user's instruction to improve implementation and contracts for clarity, lineage,
governance and future effectiveness. Scoring integration is explicitly owned by the amended
`plugin-evaluator-core` task.

Plan counts after: 132 agent, 28 human, 160 total. Next agent: `corpus-provenance-audit`;
next human: `define-locked-test-policy`. Capability status stays planned because open corpus work
remains. No corpus regeneration was necessary: tests generate fresh sequence evidence and existing
video evidence remains valid. Only intended changes remain; no service, port or external resource
was started. Temporary helper scripts were removed and runtime caches retain their existing clean
kinds. No new reproducible data-root kind was introduced.
