# Data contract design

Analysis and rationale for
[specification section 17](spec.md#17-data-contracts-and-schema-evolution). The specification stays
authoritative when they differ. Sources and tools were checked on 2026-11-02. The spike scripts were
not kept, and their results are in
[record 0012](../impl/records/0012-adhoc-data-contract-and-telemetry-design.md).

## Decision

Yes, ss-track can and should define its interchangeable data as open schemas with evolution support.
It should copy the fl-op **process** and replace its **schema language**.

fl-op is a planner fed by tables. Its sources are many flat CSV and Avro files that project onto one
canonical model, so a table contract written in ODCS suits it. ss-track exchanges nested,
hash-sealed documents and cross-language events. Its hardest requirement has no fl-op counterpart: a
sealed record is evidence, so a schema change must not change the bytes or hash of old evidence, and
old evidence can never be migrated in place.

| Layer | Choice | Reason |
| --- | --- | --- |
| Structure of documents | JSON Schema 2020-12, restricted dialect | Validators exist in every language, it closes objects and states tagged unions, and it reads YAML and JSON alike |
| Structure of events | Protobuf, as section 5 already requires | C++20 parity, binary framing and a mature breaking-change checker |
| Governance | One registry, immutable frozen versions, a CI gate, a change log | Adopted from fl-op, made stricter |
| Dataset description | Croissant 1.1, generated from sealed records | The ML dataset standard, and the part that actually enables self-service |
| Catalog view | ODCS 3.2, generated, optional | Useful to a data catalog, lossy as a source of truth |
| Field meaning for telemetry | fl-op style mapping profiles | The one place ss-track has the many-sources problem fl-op solved. See [telemetry sources](telemetry-sources.md) |

## What is interchangeable today

| Format | Written by | Location | `schema_version` | Starting contract |
| --- | --- | --- | --- | --- |
| `recording.yaml` | Operator | Beside the media | 2 | `declaration/recording` 2.0.0 |
| `corpus.yaml`, including recipes | Operator | Operator's choice | 3 | `declaration/corpus` 3.0.0 |
| Source manifest | `import` | `$DATA_DIR/import/<sha256>/` | 2 | `record/source-manifest` 2.0.0 |
| Corpus manifest | `corpus build` | `$DATA_DIR/corpus/<id>/` | 3 | `record/corpus-manifest` 3.0.0 |
| Frame bundle manifest | `corpus stage` | `$DATA_DIR/corpus/<id>/frames/<stream>/` | 3 | `record/frame-bundle` 3.0.0 |
| Frame set | `corpus stage` | `$DATA_DIR/corpus/<id>/` | 1 | `record/frame-set` 1.0.0 |
| Staged hashes | `corpus hashes` | `$DATA_DIR/run/<run-id>/` | 1 | `record/staged-hashes` 1.0.0 |
| Hash comparison | `corpus compare` | `$DATA_DIR/run/<run-id>/` | 1 | `record/hash-comparison` 1.0.0 |
| Command result and refusal | Every command | One JSON log line | None | `result/command-result` 1.0.0 |

Planned formats enter through their owning tasks: labels, seeds and masks, the scenario, scenario
packs, events, the run manifest and bundle, metric results, host profiles, hardware protocols,
instrument and calibration records, power traces, stand requirements and telemetry profiles.
Configuration is covered too: `.env` carries only local paths, and every behavior-changing setting
already lives in a declaration or a pinned scenario.

## Findings in the shipped code

These are the reasons this work comes before labels and events.

1. **One integer answers three questions.** `read_sealed` in `src/ss_track/corpus/sealed.py`
   accepts one exact value, so a format change has only one possible outcome. The refusal is deliberate
   and safe, and what it costs is in [reading older records](#reading-older-records).
2. **Version constants are shared across formats.** `CORPUS_SCHEMA_VERSION` versions both a
   declaration and a sealed record, and `importer.SCHEMA_VERSION` is `RECORDING_SCHEMA_VERSION`. A
   declaration change therefore forces a new record version with no change to the record.
3. **A format can only be read by reading the Python.** `Fields` in `corpus/fields.py`,
   `read_recipe` and the record writers are the definition of each format. A consumer without this
   repository has nothing to validate against.
4. **Two null conventions.** `capture` stores an unknown fact as explicit `null`, while `supersedes`
   is absent when unused, so that old corpus manifests keep their hash. Only the second can extend a
   sealed record. The spec now makes it the rule.
5. **Some sealed values mean nothing outside FFmpeg.** `color.matrix`, `primaries`, `transfer`,
   `range` and `chroma_location` are FFmpeg enum integers with no stated vocabulary.
6. **Command output is an unversioned interface.** Automation parses refusals, yet nothing states
   their shape, and `code` is a closed vocabulary only in Python.

## What to take from fl-op

Inspected: `contracts/`, `src/fl_op/contracts/evolution.py`, `odcs_loader.py`, the authoring manual
and the current-state pages at the repository head.

| fl-op element | Verdict | Reason |
| --- | --- | --- |
| Registry with one entry per contract | Adopt | One place to answer what exists, its version and its fingerprints |
| `evolution-check` and `evolution-freeze` in CI | Adopt, stricter | A reviewed baseline is the right gate. A change with no bump always fails |
| Structural and semantic fingerprints | Adopt | Section 5 forbids changing a unit or enum meaning, and only a meaning hash can detect that |
| Major and minor rule table | Adopt, amended | Adds hash stability, and treats a unit change as forbidden within a major, where fl-op allows a minor |
| Step-by-step authoring manual | Adopt, shorter | The [authoring guide](../guide/authoring-contracts.md) |
| Physical, canonical and mapping layers | Adopt for telemetry only | Corpus records have one physical form and nothing to project |
| ODCS as the authored schema | Replace | See the comparison below |
| `schema_snapshot` of top-level name, type and required | Replace | It sees no nested field, enum, pattern or bound. Almost every ss-track rule is nested, such as `rights.sharing` and `groups[].split` |
| JSON baselines embedding a full history | Replace | One immutable file per version is smaller, diffable and directly usable by a validator |
| Generated Avro, Elasticsearch and Parquet schemas | Drop | No consumer exists. An unused generator is untested surface |
| `apiVersion: v3.0.0`, never checked against the standard | Do not repeat | `odcs_loader.py` only parses YAML, and ODCS is at 3.2.0. Any generated ODCS here is validated against the official schema |

## Schema language options

| Option | Fits nested documents | Tagged unions | Closed objects | Any-language validation | Evolution tooling | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| JSON Schema 2020-12 | Yes | Yes, `oneOf` on a `const` | Yes | Yes | `jsoncompat` classifies both directions | **Structure of documents** |
| Protobuf | Yes | Yes, `oneof` | Unknown fields kept or refused by the parser | Yes, generated | `buf breaking`, `WIRE_JSON` category | **Structure of events** |
| ODCS 3.2 | Yes, with `properties` and `items` | No conditional construct in its schema | No such rule | Validates the contract, not the data | `datacontract breaking` compares contracts | **Generated view only** |
| Avro | Partly | Unions only | By construction | Yes | Reader and writer schema resolution | No: no Avro bytes exist here |
| LinkML | Yes | Limited | Yes | Through generated JSON Schema | Immature for field-number safety | No: a second language that compiles to the one needed |
| Pydantic, code first | Yes | Yes | Yes | Only through export | None | No: the schema must outlive the class that produced it |

ODCS is a good standard with a different job: it is a producer-consumer agreement about a dataset,
with teams, roles, service levels and servers. ODCS 3.2 improved a great deal, with nested
`properties`, `items`, `map`, enum values with descriptions, and relationships. Still, it offers no
way to say that `parameters` depends on `transform`, no way to refuse an unknown key, and no unit
field, so units would sit in `customProperties`. A misspelled key could not be refused, which is a
rule ss-track already enforces.

A one-off projection of the frame-set contract onto ODCS 3.2 validated with no error against the
official `odcs-json-schema-v3.2.0.json`, so a generated view is cheap whenever a real catalog
consumer appears. It is optional for that reason, and not rejected.

`datacontract-cli` pulls 49 packages and 74 MB, and `mlcroissant` 29 packages and 233 MB. Neither
belongs in the runtime closure. `mlcroissant` is a validator in a separate extra.

## Why the record stamps only a major

A sealed record's hash covers every field, including `schema_version`. Stamping `1.2.0` would change
every hash on every additive release, which splits cohorts and breaks "two stagings give one hash".
So the record keeps today's integer, which is the contract major, and the minor lives in the registry.

This has two useful results. Every record the current code writes already conforms with no byte
changed, so adoption needs no migration. And `schema_version: 3` maps directly onto contract `3.0.0`.

The cost is that a reader cannot tell which minor wrote a record. It does not need to. Objects are
closed, so an older tool that meets a newer field refuses, and a newer tool reads every older minor by
the backward-transitive rule. A descriptor lists exact contract versions outside the seal, for people.

Hash stability has an elegant test. Because objects are closed, a writer's output for input that uses
no new feature must still validate against the previous frozen minor. If it does, no field was added
to those records. This alone cannot prove existing values stayed equal; replay tests also compare
canonical bytes and seals with retained output, using fixed facts independent of the decoder.

## Reading older records

This section corrects an earlier reading. Refusing older records was described as a contradiction of
section 15. It is not: section 15 speaks of run artifacts, and none exist yet. The refusal was
deliberate, recorded in records 0003, 0004 and 0006, and added to stop an old manifest reaching staging
and failing on a missing key. No corpus record exists on the data root, so nothing has been lost. The
gap is that the product made no promise about sealed records at all, and the mechanism has real costs
the moment evidence exists.

Each era's own code wrote real records from one clip, and later code read them.

| Format change | What changed in real records | Needed a refusal? | Warranted outcome |
| --- | --- | --- | --- |
| Corpus 1 to 2 | `sequences` renamed `streams`, with encounter, group, split and scenario rights added | Yes: those are operator judgments | `facts` |
| Bundle 1 to 2 | `sequence_id` renamed `stream_id` | No | `view` |
| Corpus 2 to 3 | `generated_cases`, `width` and `height` added to every record | No | `view` |
| Bundle 2 to 3 | `generated: null` added to every record | No | `view` |
| Source 1 to 2 | `retain_until` and `derived_frames` required, with no safe default | Yes: correct as shipped | `facts` |
| Corpus, no bump | Source terms copied into `streams[].rights` under schema 3 | A version was owed | Two formats share schema 3, and a key check in `terms.py` stands in for the version |

Three of five bumps need not have refused anything, two were right to, and one real change had no
version. A hand-managed integer erred in both directions.

Source schema 1 is itself two formats. Records of `0238d55` lack `sequence.color`,
`sequence.interlaced_frames`, `sequence.source_bits_per_component` and
`decode_policy.conversion_flags`, which later schema 1 records hold under the same number. Every real
schema 1 record also predates policy revision 3, so a `facts` source record is normally stranded by
its decoder as well as its terms. The amendment accepts a record only with the current decoded facts,
and an amended later record is byte-identical to one the first schema 2 code writes.

| Case on current code | Result |
| --- | --- |
| `stage`, `verify` and `hashes` on any older era | `RECORD_SCHEMA_UNSUPPORTED`, as designed |
| Re-import over an older source | `RECORD_SCHEMA_UNSUPPORTED`, naming `--amend-terms`, before any decode |
| Source moved to `locked`, predecessor at the current major | `SPLIT_LEAKAGE`, as designed |
| Same move, predecessor at another major | `RECORD_SCHEMA_UNSUPPORTED`, and no version can link to it |
| Same move, `supersedes` dropped | **Builds and stages as `no_lineage`.** The guard's only exit goes around it |
| Successor whose predecessor holds another major's bundle | Stages, naming that bundle under `other_schema`, because section 4.1 says such a predecessor is reported |
| Same source as a new corpus version | `bundle_sha256` equal across all four eras, while corpus seal, frame set and bundle seal differ and every frame is stored again |

The last row sets the price: a million 1080p frames is 6 TB and about four hours of staging. A decode
policy revision blocks records the same way with no schema change. That one is correct, because new
pixels need new evidence, and `decode-policy-reimport` owns it.

Root cause: one exact integer answers whether a tool can parse a record, whether the record may serve
as evidence, and what changed, so every change gets one response. Reading and checking are two calls
that can be separated, and no step classifies a change when it is made.

A prototype confirmed the remedy. A real bundle given its major 2 shape was refused by the exact check
and passed `corpus verify` through a four-line in-memory view, with its frame-set hash and file bytes
unchanged.

| Long-lived format | Practice | Applied here |
| --- | --- | --- |
| [SQLite](https://www.sqlite.org/fileformat.html) | Separate read and write versions: unknown write version means read-only, unknown read version means no access | Parsing and using are separate questions |
| [ext4](https://docs.kernel.org/filesystems/ext4/super.html), and ULog and MAVLink here | Compatible, read-only compatible and incompatible flags | An unknown change is refused only as far as it must be |
| [TUF](https://theupdateframework.github.io/specification/latest/) | Hashes and signatures cover data a reader does not understand | Seal first, on original bytes, then interpret |
| [OCI descriptors](https://github.com/opencontainers/image-spec/blob/main/descriptor.md) | A digest is a content identifier, and existing identifiers must not be modified | No view or amendment changes a pin |
| [Event sourcing](https://www.infoq.com/news/2017/07/versioning-event-sourcing) | Never update an old event: upcast at read, copy and replace as the last resort | `view` first, `facts` with a successor record last |
| [Schema Registry](https://docs.confluent.io/platform/7.2/schema-registry/avro.html) | `BACKWARD_TRANSITIVE` checks against every earlier version | Every in-service major, not only the last |
| [Kubebuilder](https://book.kubebuilder.io/multiversion-tutorial/conversion-concepts) | Versions are representations of one stored object, converted without a function per pair | Views step one major at a time and compose |
| [Arrow](https://issues.apache.org/jira/browse/ARROW-5915) and [Parquet](https://github.com/isabella232/parquet-testing) | Keep real files from older writers as test data | A real record per major, never a resealed number |

`view` and `facts` are decided per change because some changes truly lack information. Two cases argue
against a simpler rule. Accepting all older majors would invent rights, which record 0006 rightly
refused. Refusing all of them is what produces the guard exit above.

## Why validation is not on every read

Validating a million-frame index with `jsonschema` took 15 s, where `json.loads` took 0.34 s. The
existing reader spends about 2 s on the same index. A seal already proves a record is unchanged since
it was written, so full validation runs once, before sealing, and a read checks seal, kind and major.
Declarations are small and are validated in full on every read. `ss-track contracts validate` gives
anyone a deep check on demand.

Full validation at write time adds about 15 s per million frames to staging, which takes hours for
that many frames.

## A schema is necessary, not sufficient

Draft schemas accepted the real recording, corpus and frame-set documents, and a tagged union
refused a recipe with another transform's parameters. Probing the differences from today's reader
found four cases that JSON Schema alone would weaken:

| Input | `Fields` today | JSON Schema alone | Handling |
| --- | --- | --- | --- |
| `start_frame: 1.0` | Refused | Accepted, since `1.0` is an integer in 2020-12 | Local validator uses a strict integer type |
| `fov: .nan` or `.inf` | Refused | Accepted by the Python validator | YAML loader refuses non-finite values before validation |
| `start_frame` not below `end_frame` | Refused | Accepted, a cross-field rule | Stays in code, and is stated in the contract under `x-rules` |
| Unquoted YAML date | Normalized | Refused, a `date` object is not JSON | YAML loader normalizes before validation |
| A hash ending in a newline | Refused, by `fullmatch` | Accepted by the Python validator, whose `$` also matches before a final newline | Local validator ends a pattern at the end of the value |
| `\d` in a pattern | Not used | Matches other digits in Python, ASCII only in ECMA-262 | The dialect refuses `\d`, `\w`, `\s` and `\b` |
| `format: date-time` | Not used | Passes everything unless an optional package is installed | The dialect allows only `date`, which is enforced |

A third-party validator gets the structure right and may be looser on the first two. That is
acceptable: this repository's reader stays the strict gate, and the contract states the rule in words.

The dialect meta-schema can state nearly everything, including that a branch of a `oneOf` holds a
`const` property. It cannot state that all branches hold the same one, because a schema sees one branch
at a time, so `make lint-contracts` adds that rule. The registry also pins each file's bytes as well
as its fingerprints: a fingerprint ignores formatting by design, and a frozen file is never edited at
all.

## Self-service

A future consumer needs five things without this repository: find a dataset, judge whether it suits
them, know the terms, load it, and follow its changes.

| Need | Provided by |
| --- | --- |
| Find | Croissant descriptor, built on schema.org `Dataset`, which dataset search and hubs read |
| Judge | Generated dataset card: splits, encounters, classes, capture conditions, generated-case slices, limitations |
| Terms | `rights`, `sensitivity` and retention, carried into the descriptor, with `locked` reduced to counts |
| Load | Croissant record sets over the manifests, plus the frozen contract for raw layouts |
| Follow changes | The change log, frozen versions and corpus version lineage |

A one-off Croissant 1.1 document generated only from sealed records loaded with `mlcroissant` 1.1.1
with zero errors: streams, bundles and the per-frame index all came back as records. One real limit
appeared. Its loader refuses a `FileSet` of `.rgb24` files with `application/octet-stream`, because
it tries to parse each as a table. A descriptor can therefore index raw frames and state their layout,
and a consumer reads the bytes through the frame-bundle contract. An export to a standard image
format is the way past this, and it stays out of scope until someone needs it.

A hosted catalog, access requests, publication and pricing are not part of this. Publication decisions
stay outside the repository.

## Evolution workflow

```text
copy the newest frozen file to the next version -> edit it
ss-track contracts diff <contract> --file <candidate.json>
ss-track contracts freeze <contract> --file <candidate.json> --summary "What changed"
make ci                                # refuses an edited frozen file or a stale fingerprint
```

A breaking change also states its migration in the change log, because that text is what a refusal
shows a person holding an old record. The classifier is written here because it must name each
changed field, and `jsoncompat` answers only compatible, incompatible with a counterexample, or
unknown. `jsoncompat` stays a dev-only independent oracle in the tests, so a disagreement fails CI.
It is a small project at version 0.5.0, MIT licensed, and being an oracle rather than the authority
makes it replaceable. In the spike its answers on a closed object matched the rule table on all ten
structural change kinds tried. On an open object it called an added optional constraint
compatible, and it cannot decide pattern widening or a raised bound. The tests therefore wrap it:
equivalent rewrites, an automaton for patterns, and a deterministic witness search, with every
counterexample confirmed by the local validator. It cannot see an annotation, so a unit change
stays with the meaning fingerprint.

## Risks

| Risk | Control |
| --- | --- |
| Schema and reader drift | Readers take structure from contracts at runtime; the group audit owns any rule still stated twice |
| Frozen-file growth | One small file per version. Corpus-era history shows a handful of changes |
| Dialect too narrow | Widening the dialect is a reviewed change to one meta-schema |
| Effort before labels | The baseline describes existing formats and changes no behavior, and every later contract is cheaper to write now than to retrofit |
| A view hides a meaning change | A view names each derived value, cannot derive an operator judgment, and golden records of each major pin its result |
| Reader refactor regressions | Refusal codes stay, and the existing suite is the gate |
