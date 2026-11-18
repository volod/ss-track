# Contracts

Contracts describe interchangeable formats for readers outside this repository. `contracts/` at the
project root holds the set, `src/ss_track/schema/` reads and checks it, and the
[specification](../../design/spec.md#17-data-contracts-and-schema-evolution) states the rules. The
[contract registry record](../records/0017-data-contracts-contract-registry.md) keeps the accepted
task, its decisions and its evidence. To add or change a contract, follow the [authoring
guide](../../guide/authoring-contracts.md).

## Development stage

The registry states `stage: development`, as [spec section
17.7](../../design/spec.md#177-development-stage-and-release) requires until the first release.
Every contract therefore has exactly one version, `1.0.0`, with change class `initial`, and every
record and declaration stamps `schema_version: 1`. The set holds no older version, no
`retired_majors` entry, no disposition and no view. The [development baseline
record](../records/0099-data-contracts-contract-development-baseline.md) holds the collapse from the
earlier version history to this set.

A change to a format edits its `1.0.0` file in place and re-pins it: `ss-track contracts freeze`
with a candidate whose `$id` ends in `:1.0.0` replaces the file and its registry entry, and refuses
any other version. Writers, fixtures and tests change in the same change. The gate accepts the
edited file only with its new pins, and refuses a second version, a change class other than
`initial` or a retired major. `schema/registry/stage.py` states those rules.

Records written before an edit still stamp `schema_version: 1`, so a data root keeps
`contract-set.json`: structure and meaning fingerprints of the record and shared contracts. A record
or shared contract may reference only record and shared contracts, which
`schema/registry/references.py` holds in the gate, so these pins cover every contract a record's
shape depends on. Before the first sealed write, `core/evidence/contract_stamp.py` checks and writes
the stamp under `core/scratch.py` `directory_lock` on the root, the lock a freeze and an event
publication take on the contract set, and `core/evidence/stamp_file.py` parses and writes its
bytes; read-only commands write nothing. Every command taking the data root, through
`commands/report.py` `reported_on_data_root` or `checked_data_root`, compares it with the
installed set. A difference is `RECORD_SCHEMA_UNSUPPORTED`, with `changed_contracts` and the
remedy to delete sealed datasets and the stamp and regenerate them from retained declarations,
labels and review decisions. A stamp without meaning fingerprints cannot prove the earlier meaning
and is refused with the same remedy and `unverified_contracts`; no data is deleted by the check.
The development root `$DATA_DIR` is stamped with meanings; its [regeneration
record](../records/0106-data-contracts-development-data-root-regenerate.md) shows that a rebuild
from the retained inputs reproduced every sealed record's seal.
When the stamp is absent, `core/evidence/unstamped.py` walks the reachable root when a command first
checks it and again under the first-write lock. It streams object keys and refuses a file with both
record identity and seal keys at the top level, regardless of filename. It follows symlinks and
avoids directory cycles; inaccessible or non-regular files fail closed with `STORAGE_FAILED`. An
entry that disappears during the walk, such as another command's scratch file, and a dangling link
hold no readable bytes and are skipped. Declarations and other operator inputs remain in place, and
a read-only check writes no stamp. A record read rechecks a root whose stamp was absent or has
disappeared since the command started: a stamp written since by another command is verified, and
without one `core/evidence/sealed.py` refuses the object it loaded when it holds both record keys,
naming that record. No walk is needed there, because only such a file can pass a sealed read, and
the refusal judges the bytes actually read. Root-taking corpus operations and evidence readers check
the root too. Each checked root is kept for the command, so checking a second root does not stop the
stamping or rechecks of the first. `core/evidence/checked_roots.py` holds that context: inside one
command, which `commands/report.py` `reported` enters with `one_command`, a later check of the same
unstamped root reuses a clean walk when no sealed read or write of a path under it came between
them. A read or a write ends the reuse for every checked root holding its path, so an enclosing root
walks again after a nested root receives a record. The locked first-stamp check always walks, a
stamp that appears is always verified, and library calls outside a command walk at every check. A
standalone path-only read has no data root to infer; its caller must establish that context when it
belongs to a data root. A command that takes explicit output paths instead of the data root calls
`commands/report.py` `check_root_holding` before any work: when an output resolves under
`$DATA_DIR`, as spelled or through a link on either side, the root is checked and the sealed write
stamps it; an output outside the root stays standalone and the root is neither read nor stamped.
`annotate freeze --labels-out --revision-out` is the one such sealed writer;
`core/evidence/checked_roots.py` `holds_path` is the containment rule shared with the write-time
root lookup. The
[explicit-path record](../records/0107-data-contracts-development-explicit-path-revision-root.md)
lists the commands reviewed. `tests/commands/test_root_checks.py` builds every command from the
parser and holds each one that takes the data root to this check, on a root with unstamped evidence
and on a stale stamp: it refuses with the regenerate remedy and changes nothing. A command that
takes no root is exempt only by name, with its reason.

A sealed record that leaves its data root carries the pins of the install that wrote it:
`shared/types` `$defs/contract-set` states the rows, one `{contract, structure, meaning}` per record
and shared contract in contract order, or `null` in the released stage. `record/link-review-handoff`
and `record/staged-hashes` both reference it as `contract_set`. `core/evidence/carried_pins.py`
writes the rows (`carried_contract_set`) and checks them (`require_carried_contract_set`) with the
stamp's own comparison, `contract_stamp.changed_contracts`. Absent or null pins, or any differing
contract, refuse `RECORD_SCHEMA_UNSUPPORTED` with the record, `changed_contracts` and the carrier's
remedy before the reader writes anything; unsorted, repeated or incomplete rows are
`RECORD_TAMPERED`. In the released stage the check passes and a record's major identifies its
contract. `corpus compare` checks both staged-hashes records before it compares them, so another
host's record written under another development contract set leaves no `hash-comparison.json`; the
[staged-hashes provenance
record](../records/0110-data-contracts-development-staged-hashes-provenance.md) has the evidence.

The scan costs one directory traversal plus the bytes needed to identify JSON objects, with fixed
input buffers and directory-cycle tracking. On one private root of 25,000 PNG files (102.4 MB) in
50 directories, three checks took 0.983, 0.688 and 0.685 seconds; peak traced memory was 4.99 MiB
on the first check, including installed-contract initialization, and 0.06 MiB on each later check.
A stamped root does not scan. On an unstamped root, a command that writes no record walks it once
and a first-write command walks it twice: at its first check and under the first-write lock.
`tests/corpus/records/test_unstamped_scan_reuse.py` counts the walks. On a warm private root of
25,000 PNG files (102.4 MB) in 50 directories, a refused `corpus stage` took about 0.22 seconds
with one walk and a first `import` about 0.47 seconds with two. The
[unstamped-evidence record](../records/0104-data-contracts-development-unstamped-evidence.md)
states the scan fixture and its limits, and the
[scan-reuse record](../records/0108-data-contracts-development-unstamped-scan-reuse.md) the
command timings. A damaged stamp is `RECORD_TAMPERED`. `data clean` reads no
record and serves a stale root. Meaning fingerprints cover annotations including descriptions, so
even editorial edits conservatively require regeneration. A record of another major gets the same
regenerate remedy. The [audit record](../records/0102-data-contracts-data-contracts-audit.md) gives
the broader checks and evidence. The
[record-formatting decision](../records/0103-data-contracts-resolve-data-contract-record-markdown.md)
keeps the owner-authorized exception.

The section 17.3 classifier, the oracle, dispositions, views and comparison projections stay
installed. Their tests run on synthetic version pairs in a private copy of the set moved to
`stage: released` (`tests/schema/conftest.py` `release`), and on a synthetic older major 0 that a
test gives the current projection (`tests/corpus/conftest.py` `project_older_major`). The shipped
tool registers no view or stated shape, and no projection of another major, as
`tests/corpus/records/test_read_window_rules.py` holds for this stage.

Each structural, meaning-only and `shared/types` edit, re-pinned with `contracts freeze` on a
private set, refuses a root stamped before it and names that contract
(`tests/corpus/records/test_stamp_after_freeze.py`). Operator inputs are not regenerated, so
`tests/schema/registry/test_retained_inputs.py` validates every one the repository keeps under
`docs/impl/workloads/` and `scenarios/` against its declaration contract, and fails on a retained
input it does not list.

## The installed set

| Family | Contracts, each at `1.0.0` |
| --- | --- |
| `declaration` | `annotation-label`, `annotation-mask`, `annotation-review`, `annotation-seed`, `annotation-settlement`, `audit-review`, `corpus`, `corpus-pool`, `corpus-review`, `dataset`, `discovery-plan`, `link-decisions`, `recording`, `scenario-pack`, `source-inventory`, `video-hints` |
| `record` | `annotation-revision`, `audit-blinding`, `candidate-inventory`, `corpus-freeze`, `corpus-links`, `corpus-manifest`, `corpus-pool`, `derived-label`, `discovery-run`, `feature-rows`, `frame-bundle`, `frame-set`, `hash-comparison`, `image-sequence`, `link-review-handoff`, `source-acquisition`, `source-manifest`, `staged-hashes` |
| `result` | `command` |
| `shared` | `types` |
| `event` | `analytics`, `clock`, `frame`, `trial`, `wire` |

The [corpus baseline record](../records/0018-data-contracts-corpus-contract-baseline.md) records the
baseline scope and evidence. The `event` family is a frozen descriptor set, not a JSON Schema
document; the [runner page](runner.md) states the messages, the line checker and the breaking gate.

### Recordings, sources and corpus versions

`declaration/recording` states one video file or one ordered PNG image sequence, with an optional
rational frame rate, optional `source.video_stream_index`, optional `color.matrix` and optional
`origin`, omitted when a recording names no upstream collection. Its closed capture judgments
`camera_control_mode` and `observer_platform` are stored as `unknown` when omitted.
`record/source-manifest` seals one imported source: its sequence, with `video_stream_index` only
when the decoded stream is not the first, optional `declared_color` when conversion used that
declaration, the retained image inventory of an image sequence, and `origin`, which is sensitive, so
a public descriptor omits it. `record/image-sequence` seals an image sequence's ordered hashes and
declared rate. The [sequence source interface](corpus.md#ordered-image-sequences) states identity and
timing.

`declaration/corpus` states groups, encounters, streams and generated-case recipes: blur, noise,
`compression`, `variable_timing`, `crossing_occluder`, `moving_removal`, `similar_distractor`,
`out_of_view` and `scale_reduction`. `record/corpus-manifest` and `record/frame-bundle` hold those
recipes and the label transforms, including `compression`, `timing`, `track_status` and `scale`.
A corpus stream holds `content_sha256`, the file hash, only when its source identity is not that
hash. Both records and the source manifest carry `x-sensitivity` marks, which a dataset descriptor
reads. The corpus contract requires each stream's source terms. `declaration/corpus-pool` and
`record/corpus-pool` state a combined-pool selection, with per-collection `metadata_names`, and its
sealed result.

`declaration/source-inventory` records upstream candidate videos, pins and unresolved facts; the
[inventory reader](corpus.md#source-inventory) enforces cross-field and path rules.
`record/source-acquisition` links the provider selection, its input inventory hash, Zenodo split
metadata hashes, selected upstream metadata files, verified local video hashes and the normalized
inventory. The [acquisition workflow](corpus.md#source-acquisition) states the checks and the rights
boundary. `declaration/dataset` states the operator-supplied title, description, license, citation,
address and publication date that the [dataset descriptor](corpus.md#dataset-descriptors) consumes.

Each free-text declaration property states the `text` rule under `x-rules`: the value holds a
character other than whitespace. The dialect cannot state that over any script, and `Fields.text`
enforces it. `tests/schema/registry/test_agreement.py` fails when a free-text declaration property
lacks the rule.

### Labels

`declaration/annotation-label`, `declaration/annotation-seed`, `declaration/annotation-mask`,
`declaration/annotation-review` and `declaration/annotation-settlement` state operator labels,
seeds, masks and their review. `source_sha256` names the file hash of a video, the stream identity
of a later video stream, or the sequence identity of an ordered image sequence.
`record/annotation-revision` seals a frozen label revision and `record/derived-label` one derived
revision of a generated case. [Derived case labels](corpus.md#derived-case-labels) states the paths
and the transforms.

### Discovery, links and review

`record/discovery-run`, `record/candidate-inventory` and `record/feature-rows`, owned by
`self-supervised-corpus`, hold a discovery run, one stream's candidate windows and one extractor's
row keys for one stream; [discovery records](corpus/discovery-records.md) states their rules and
validators. A run holds optional `source_approval`, `feature_rows`, a hint source's `matches`, the
crop `tiled` and an extractor's optional `tile`. `declaration/discovery-plan` and
`declaration/video-hints` state a [discovery run's plan and an ss-video hint
file](corpus/discovery-runs.md), with an extractor's optional `tiles` and the optional `selection`.
`record/corpus-links` and `declaration/link-decisions` hold a link review of one version and a
reviewer's decisions on pairs of recordings; the [leakage review](corpus/leakage-review.md) states
their rules, which `read_links` enforces. `record/link-review-handoff` is the sealed manifest inside
a media-free portable review tar. It binds the corpus, frame set, link record, optional checkpoint
branch and every archive member by size and SHA-256. In the development stage its `contract_set`
lists the structure and meaning fingerprint of every record and shared contract the exporter
installs, the pins the exporting root's `contract-set.json` holds; `review-pack` checks the root
first. `review-unpack` and `review-accept` check them as [carried pins](#development-stage), with
the handoff remedy of `corpus/links/portable_provenance.py`, before recipes are extracted or any
local record, comparison or checkpoint is written; the [handoff provenance
record](../records/0105-data-contracts-development-portable-handoff-provenance.md) has the evidence.
Recipe members are text inputs only; media, staged frames, feature rows and model weights remain
local to independently prepared hosts.

`declaration/corpus-review` and `record/corpus-freeze` hold a reviewer's decisions on the windows a
discovery run offers and the sealed export of the version frozen from them, with optional
`independence`, `blinding`, `reviewer_minutes`, `audit_id` and `selection_pass`. A freeze copies a
field only when the review stated it. `declaration/audit-review` is the cue-free review of one
blinded audit sample, and `record/audit-blinding` the private mapping back to the candidates.
[Review and freeze](corpus/review-and-freeze.md) states their rules, which `read_review`,
`read_audit_review`, `read_blinding` and `read_freeze` enforce. A decision is a `oneOf` tagged by
`decision`, so an `unreviewed` entry carries no observation.

### Command results

`result/command` closes the result vocabulary of every command and leaves only `details` open.
Among others it states the `inspected` source inspection, `planned` and `cleaned` with the `clean`
object of `data clean`, `capture_encounters` on a corpus build, `unlinked`, `near_duplicates` and
`impact`, the `discover` fields, `links`, `queue`, `review` and `superseded`, the blind counts and
the paired selection comparison with `review_budget`, `sibling_offers` and `by_source`, and the
`annotation`, `label_review` and `label_derivation` objects of `ss-track annotate`. Optional objects
are absent when a command has nothing to report. A label result has no `score` field, and an
unscorable case is never a zero. An unrecorded review minute stays unmeasured rather than zero.

`shared/types` supplies hashes, identifiers and the contract pins a record carries between roots.
Every shipped document format has a contract, and every frame-set reference resolves at its
annotated schema pointer. Capture fields preserve operator descriptions and numbers: the dialect
allows exactly `["string", "number"]` and its nullable form. Numeric descriptive metadata has no
physical-unit claim; declared range retains metres.

Each sealed format's kind and major have one statement, its `RecordFormat` in
`corpus/records/kinds.py`. The writer stamps a record with `RecordFormat.stamp()` and the read path
reads with the same value. Declaration majors are constants in `corpus/declarations/declaration.py`,
`annotate/declarations/contracts.py` and `corpus/descriptors/descriptor.py`. Declaration and record
majors stay independent.

## Runtime enforcement

The [enforcement record](../records/0020-data-contracts-contract-enforced-readers.md) holds the
accepted task, its decisions and its evidence.

Contracts state structure at runtime, in `schema/validation/enforce.py`, with the refusal codes the
readers had:

- `read_declaration` parses operator YAML with the strict parser and validates the whole document
  under the newest frozen version of the major its reader reads. A violation is `MANIFEST_INVALID`
  and names the URN and the first violation, a wrong `schema_version` first; details list up to 20.
  An unreadable file is `MANIFEST_INVALID` too. The corpus readers then take typed values through
  `corpus/declarations/fields.py` and apply only the rules a contract states as `x-rules` or does
  not state.
- `require_record` validates a record, already holding its seal, under the newest frozen version of
  the major it stamps, and `core/evidence/sealing.py` `seal` calls it before returning. A writer defect,
  including an unregistered kind, a major with no frozen version or a `NaN`, is `RECORD_INVALID`
  with nothing written. An amendment or redecode seals its successor the same way, so no list of
  required keys is kept in code.
- `older_remedy` returns the change log's migration for an older major of a record kind.
- `older_disposition` returns how a record of an earlier major is read: the strictest disposition
  of each major it steps through to the current one, from `Contract.disposition_of`, which reads a
  `retired_majors` entry or the `change.disposition` of the major transition that replaced it. A
  step no change log states gives none, and the record is refused as unwritten.
  `readable_majors` lists the current major and every one a chain of views reaches, which a
  refusal reports as `accepted_schema_versions`.
- `is_shared_type` checks a value against a `shared/types` definition. Run ids and corpus ids given
  on the command line are checked as identifiers this way, so the pattern has one statement.

The installed set is read once per process and checked for stage rules, file hashes and structure
and meaning pins before it is used. Contract listing, validation and exports check the same pins.
The build gate also checks the dialect and references. A sealed read never validates: it checks
the data-root stamp when relevant, seal, kind and the disposition of its major. It does not walk
the contract to validate the record. Validation does not run `x-rules`. The
[corpus read path](corpus.md#reading-sealed-records) applies dispositions.

The validator reports a tagged `oneOf` through the branch its tag selects, so a wrong seed in a
`blur` recipe is `/groups/0/encounters/0/streams/0/generated_cases/0/seed` and not "not valid under
any of the given schemas". A tag no branch states is named with the tags that exist, and a missing tag
as a required property. An untagged union keeps the standard report.

YAML dates are normalized to their ISO text as `strict_yaml.YamlDate`, a `str` subclass.
`YamlValidator` in `schema/validation/strict.py`, which validates every YAML document, accepts one
only where its node states the `date` format: an unquoted `2024-01-05` is a date to a YAML 1.1
reader and text to a YAML 1.2 one. So `holder: 2024-01-05`, or a capture fact written that way, is
`MANIFEST_INVALID` from a reader and from `contracts validate` alike, while `retain_until` takes it.
Quoted, it is text. A JSON record cannot hold one, so its validation skips the check, which would
cost 5% of validating a large bundle before sealing. Text that is only whitespace is refused by
`Fields.text`, under the `text` rule each free-text property states.

## Commands

```bash
ss-track contracts list
ss-track contracts validate --file frame-set.json
ss-track contracts validate --file corpus.yaml --contract declaration/corpus
ss-track contracts validate --file recording.yaml --contract declaration/recording
ss-track contracts validate --file result.json --contract result/command
ss-track contracts validate --file frame-set.json --contract record/frame-set --version 1.0.0
```

The commands do not read the data root and work from an installed wheel. Each logs one JSON record.
`diff` and `freeze` are described under [evolution](#evolution).

`list` states each contract, its family, owner and status, and each frozen version with its URN,
pins and change-log entry. `validate` checks every field of a JSON file, or an explicitly named
declaration's YAML, under one frozen version and, for the `record` family, its seal. With no
`--contract` it takes the contract from the file's
`kind`. With no `--version` it takes the newest version of the major the file stamps, or the newest
if it stamps none. An explicitly named result contract defaults to its newest version, ignoring an
embedded record's `schema_version`. The validation result names the URN and whether a seal was checked.

`validate` checks structure and a seal, and no `x-rules` entry. A rule across fields or files stays
in the code that reads the record, so a resealed record in the wrong order passes here and fails at
`corpus verify`. Both parsers refuse duplicate keys and non-finite numbers, including JSON exponent overflow.
Declaration YAML uses `UniqueKeyLoader`, normalizes unquoted calendar dates to ISO strings, and
refuses non-string keys, timestamps, binary values and cyclic aliases outside the JSON data model.
The input file is never rewritten. Name a `declaration` contract to select the YAML parser.

| Code | Raised when |
| --- | --- |
| `RECORD_INVALID` | A non-declaration file is not strict JSON, or breaks a contract outside the `declaration` family. Details name the URN and up to 20 violations by JSON pointer |
| `MANIFEST_INVALID` | A file is not supported declaration YAML, or breaks a `declaration` contract |
| `RECORD_TAMPERED` | A record of valid shape does not match its seal |
| `CONTRACT_UNKNOWN` | The named contract or version does not exist, no contract states the file's `kind`, the file names no format and no `--contract` was given, a draft has no frozen version, a `shared` contract was named, because it states no document, or an `event` contract was named, because its instances are protobuf-JSON lines rather than one JSON document |
| `CONTRACT_SET_INVALID` | The registry breaks its schema, or a frozen file is missing or differs from the hash the registry pinned |

## The set

| Path | Holds |
| --- | --- |
| `contracts/registry.yaml` | Each contract's family, id, owner, status and frozen versions, with `file_sha256`, both fingerprints, the change-log entry and optional retired-major dispositions |
| `contracts/<family>/<id>/<version>.json` | One frozen JSON Schema version, whose `$id` is `urn:ss-track:contract:<family>:<id>:<version>` |
| `contracts/event/<id>/<version>.binpb` | One frozen descriptor set for an event package. It is not a JSON Schema document |
| `contracts/shared/types/` | The `sha256`, `identifier` and `contract-set` value types |
| `contracts/meta/dialect.json` | The restricted JSON Schema a contract may use |
| `contracts/meta/registry.json` | The shape of `registry.yaml` |
| `contracts/README.md` | What a consumer holding only this directory needs |

`pyproject.toml` maps the directory to the package `ss_track.contract_files`. That mapping rules out
package discovery, so `packages` is an explicit list, and `tests/test_packaging.py` fails
when a package is missing from it. `contracts/__init__.py` exists because an editable install finds
a mapped package only through one. `ss_track.schema.registry.store.default_root` gives one lookup
for a checkout and a wheel.

| Module | Owns |
| --- | --- |
| `schema/validation/strict.py` | The local validator and its YAML variant, violation reports and tagged-union reporting |
| `schema/registry/contract.py` | A contract, its frozen versions, their identity and the registry's vocabulary |
| `schema/registry/store.py` | Loading the registry and frozen files against their pins, and `$ref` resolution by URN |
| `schema/registry/fingerprints.py` | The schema walk and both fingerprints |
| `schema/registry/dialect.py` | The meta-schema check and the shared-tag rule |
| `schema/registry/check.py` | Registry, file, dialect and identity checks without Git |
| `schema/registry/references.py` | `$ref` and `x-references` resolution, and the families a record or shared contract may reference |
| `schema/registry/stage.py` | The stage rules and the one reading of a registry's stage |
| `schema/compatibility/evolution.py`, `schema/compatibility/change_rules.py` | JSON-pointer comparison and keyword compatibility rules |
| `schema/compatibility/patterns.py` | The structural pattern-inclusion proof |
| `schema/compatibility/derivatives.py`, `schema/compatibility/derivative_expr.py` | Inclusion of a pattern whose shape changed |
| `schema/compatibility/versioning.py` | Minimum bump, change-log, disposition-floor and backward-transitive policy |
| `schema/compatibility/dispositions.py` | The disposition floor and the properties no view may derive, named in code |
| `schema/compatibility/freeze.py`, `schema/compatibility/publishing.py` | Candidate validation, generated pins and publication under the set's directory lock through one atomic writer, `write_contract_file` |
| `schema/compatibility/history.py` | `make lint-contracts`: merge-base immutability and transition checks |
| `schema/validation/commands.py` | `contracts list` and `contracts validate` |
| `schema/validation/enforce.py` | Runtime validation of declarations and records, change-log remedies and dispositions, and shared types |
| `schema/validation/_documents.py`, `strict_json.py` | Private document parsing and shared strict JSON decoder hooks |

Event descriptor checks live in `ss_track.contract` and are described on the [runner page](runner.md).
`ss_track.schema` imports nothing from `ss_track.corpus`, because the corpus writers validate
through it. `ss_track.core.refusal`, `ss_track.core.canonical` and `ss_track.core.strict_yaml` sit
below both, and a test holds that import direction.

## Validation

`schema/validation/strict.py` extends the standard validator at two points where it is loose. `1.0`
and `True` are not integers. `$` in a `pattern` means the end of the value, as it does in ECMA-262:
Python's `re` would also match before a final newline, so a hash with one would pass here and fail
elsewhere. `date` is the only `format` the dialect allows, because no other is enforced with the
installed dependencies, and an unenforced format would read as a rule.

The dialect closes what it can for a third-party validator. It refuses `\d`, `\w`, `\s` and `\b`,
whose meaning differs between regular expression engines, and bounds every pattern at both ends.
`pattern_findings` in `schema/registry/dialect.py` then refuses any pattern outside the syntax
`schema/compatibility/patterns.py` reads: ASCII literals, escapes, positive classes, groups,
alternation and quantifiers, with no top-level alternation. `.` and a negated class match line
terminators and astral characters differently in Python's `re` and ECMA-262, and no change to
lookaround or a backreference could be classified. A literal `.` stays available escaped or inside a
class. What stays looser elsewhere is `1.0` for an integer, which JSON Schema itself accepts, and a
final newline under an engine with Python's `$`.

## The gate

`make lint-contracts` runs inside `make ci`. Its local set check reports these by contract and
version:

- the registry against `meta/registry.json`, with contracts in family and id order and versions in
  numeric order, so a repeat cannot hide;
- a file on disk the registry does not list, and a listed file that is missing;
- `file_sha256`, which catches any edit, formatting included;
- `$id` against the path;
- the dialect, including the rule that the branches of a `oneOf` share one required `const` property
  with distinct values, which needs two branches at once and so cannot be a meta-schema rule;
- the pattern syntax, which needs a parser and so cannot be a meta-schema rule;
- `schema_version` as the integer const of the major, in `declaration` and `record` contracts, and
  `kind` as a const with the seal required, in `record` contracts;
- both fingerprints, stating the pinned and computed values; `freeze` generates these pins;
- the rules of the registry's stage: in `development`, one version `1.0.0` per contract with change
  class `initial`, and no retired major;
- every `$ref`, once every file above is intact, and in a record or shared contract only to a record
  or shared contract, the families the data-root stamp pins. The `event` family skips `$id`, the
  dialect, the stamps and `$ref`. Its file hash still catches any edit. The descriptor check then
  requires the contract URN, the protobuf package, `json_name` equal to the field name, and both
  fingerprints.

The fingerprints walk schema positions, because a property may be named `title` or `description`,
and such a key is a name and not an annotation. Fixed `prefixItems` positions are walked in order;
`items: false` and object openness affect structure, while tuple units and descriptions affect
meaning. `structure` drops annotations and `$id`, so two
versions of one shape compare equal. `meaning` keeps annotations and `const` and `enum` values, and
drops whatever is left empty, so a definition with no annotation does not move it.

The history gate reads the merge base of `HEAD` and `CONTRACT_BASE_REF` (default `origin/main`),
`HEAD`, and every released registry revision in the ancestry of `HEAD`. A return to development
after any released ancestor is refused, even if a later revision releases again. A released
revision's every frozen file and complete version entry must be unchanged, so local edits to a
version already committed on the feature branch are caught, and deleting a version or editing it
together with its registry pins fails. A development revision froze nothing, so a development set
is compared with its own pins alone, and a registry that predates the `stage` field reads as
development. A revision whose stage is any other value, missing refs and shallow history fail
closed: `schema/registry/stage.py` `stated_stage` is the one reading of a registry's stage. A baseline
predating `contracts/registry.yaml` permits the initial set; all subsequent transitions still
undergo compatibility checks. `python -m ss_track.schema.registry.check --root <contracts>` remains
the Git-free check for an installed or copied set.

CI checks out full history. A pull request uses its base SHA, and a push uses its before SHA, so a
push to main cannot compare only with itself. The gate recalculates every transition's required
bump and verifies every earlier minor of the same major, including transitions entered by hand.

`tests/schema/` proves each construct the dialect refuses at the root and at each nested position,
each way of breaking the set, the wheel built from a source distribution as `uv build` builds it,
and a consumer in `tests/schema/registry/_standalone.py` that imports no project code. `test_agreement.py`
keeps the few statements a contract and code still share from drifting: each writer's `RecordFormat`
against its contract's newest major, a writer for every record contract, the descriptor's split
vocabulary against the corpus contract, and the `text` rule on every free-text declaration field.
`tests/_sealing.py` seals a fixture without its contract, because production `seal` refuses the
damaged records that read tests need.

## Baseline coverage and boundaries

Recipes use one closed tagged branch per transform in declarations, corpus manifests and bundle
identities. Label transforms similarly distinguish identity, translation, frame mapping and region
status. A transform cannot carry another transform's parameters. Cross-field facts such as window
containment, inherited membership, deterministic label mappings and seal calculations live in
`x-rules`; explicit schema validation does not execute them. FFmpeg color integers carry
`x-vocabulary`, and numeric quantities carry `x-unit`.

Staged hashes describe each frame as an exact three-position `[frame_index, pts, sha256]` tuple.
The command-result contract closes the result field vocabulary and leaves only `details` open.
Success field presence depends on the invoked command, since `unchanged` is shared by several
commands; that relationship is stated under `x-rules`. The result's optional `schema_version` belongs
to its embedded comparison, not to a newly stamped result version.

`tests/conftest.py` validates production sealed writes and CLI JSON emissions throughout the test
session, independently of the runtime check in `seal`. It checks records before tests deliberately
damage them. Subprocess outputs are checked by retained examples and end-to-end
artifact validation rather than an in-process hook. `tests/schema/examples/` holds an example of
every frozen document contract. Baseline tests also hold the refusal-code enum equal to `RefusalCode`,
check units and vocabularies, exercise transform branches and resolve the available frame-set
references. Scalar-union fixtures check text, numeric, nullable and invalid values. Runtime
enforcement is described [above](#runtime-enforcement).

## Evolution

```bash
ss-track contracts diff record/frame-set --file frame-set-next.json --root contracts
ss-track contracts freeze record/frame-set --file frame-set-next.json --root contracts \
  --summary "Describe the change."
```

`ss-track contracts freeze` refuses `event/<id>`. An event package is published by `make proto-gen`,
which will not overwrite a frozen image whose bytes differ. A later event version is classified by
`buf breaking` with category `WIRE_JSON`: identical bytes are refused, a breaking change is a major
whose disposition is at least `facts`, a compatible structure change is a minor, and any other
change is a patch. The [runner page](runner.md) states the rule.

In the development stage, `freeze` takes only a `1.0.0` candidate, replaces that file and its
registry entry in place with change class `initial`, and classifies no transition; `diff` still
explains the edit against the current file. Everything below applies once the set is released.

The candidate's `$id` names its family, id and proposed version. `--root` defaults to the installed
contract set; publishing needs a writable set. Initial contracts also require `--owner`. `diff`
returns `status: diffed`, `contract`, `version`, `required_bump`, and `changes`, each with `pointer`,
`class` and `reason`. A pointer refers to the new schema, or to the old schema for a removed node.
A no-change or initial candidate reports `required_bump: none`. `freeze` returns the same shape with
`status: frozen`, in the same `result/command` shape.

The walk compares nested properties, list items, fixed tuple positions, local and external reference
targets, capture scalar unions and tagged branches matched by tag value. Reordering branches is
not a change. Recursive shapes terminate by active reference pairs; dangling references and alias
cycles refuse. Semantic annotations cannot silently change within a major. Adding an optional
constraint under open `details` is major because previously legal values may fail it. A `const`
replaced by an `enum` that holds its value is one minor change at `/enum`.

Freeze stages the whole set, verifies identities, strict JSON, dialect, references and pins, then
checks the bump and backward compatibility with every earlier minor in the same major. Major
transitions require nonblank migration text and a `change.disposition` of `view`, `facts` or
`retired` for the predecessor major. `view` is refused below the disposition floor: a major that
adds or changes a property in `PROTECTED_PROPERTIES` (`schema/compatibility/dispositions.py`:
rights, sensitivity, scenario rights, retention, split, group, encounter, decode policy, transform,
transform revision, recipe and revision) floors at `facts`. The list stays a named code rule rather
than an annotation: the read path checks a view's derived pointers by name without walking a
contract, and a test holds every name to a property some installed contract states. The floor reads
property names on each major change's pointer, and inside an added node except what an added list
holds, since a view may derive an empty list. A removal never raises it. A freeze installs no view:
the owning area registers a view with `core/evidence/read_window.py`, and a declared view with no
function installed is
`CONTRACT_SET_INVALID` when a record of that major is read. `CONTRACT_SET_INVALID` also reports a
bad candidate or forbidden publication. Directory locking and an atomic registry replacement prevent
concurrent freezes from losing entries. A crash between schema creation and registry replacement
leaves an unregistered file, which fails the gate and can be registered by retrying. All preexisting
frozen bytes remain intact.

### Pattern proofs

`schema/compatibility/patterns.py` proves pattern inclusion by structure. The old and new pattern
are read as sequences of parts, and the new one must hold the old one's parts in order, each
admitting at least what its counterpart does, plus parts that may occur zero times. A class covers a
smaller class, a repetition a narrower count, and a group covers each old alternative with some new
one. An old repetition may give up one occurrence to a new single part, so `^[0-9a-f]{64}$` fits
`^[a-z0-9][a-z0-9._-]{0,63}$`. Removing a pattern and a literal the new pattern matches are also
relaxations.

When that reading does not apply, `schema/compatibility/derivatives.py` decides the same question
by Brzozowski derivatives. `schema/compatibility/derivative_expr.py` stores the expression so that
union ignores order and duplicates, and so that a star of a star stays one star. Each character
takes a derivative of both patterns; inclusion fails where the old language can end and the new one
cannot. The walk stops at 8192 pairs and then the relationship stays major, as does any pattern
outside the syntax below. `^(ab)*$` within `^a*(ba)*b*$` is therefore a minor. The syntax read by
both proofs is ASCII literals, escapes, positive classes, groups, alternation and quantifiers, where
`re` and ECMA-262 agree, and the dialect refuses every other pattern. On the patterns the frozen
contracts use, the two proofs together decide exactly what an automaton decides. The derivative walk
shares no code with that automaton. The [reshaped-inclusion
record](../records/0028-data-contracts-pattern-reshaped-inclusion.md) holds the measured cost.

### Independent oracle

The [oracle record](../records/0022-data-contracts-contract-oracle-coverage.md) holds the accepted
task, its decisions and its evidence. The oracle lives in the tests and shares no compatibility rule
with the classifier. `tests/schema/compatibility/_oracle.py` strips meaning keywords, inlines
references and keeps a recursive target once under `$defs`, so recursive shapes terminate. Two sound
rewrites then run at aligned positions, and `jsoncompat==0.5.0` `analyze_compat` decides the result:

- an explicitly open object in the old schema states each property the new one adds as any JSON
  value, which accepts exactly what it did. Without it, jsoncompat calls an optional string
  constraint in open `details` compatible, although `{"value": 0}` then fails. The project does
  not patch third-party packages, so this rewrite is the fix.
  `test_open_object_workaround_is_still_needed` fails once a pinned release sees the break itself,
  which is the signal to remove the rewrite;
- a new pattern that `tests/schema/compatibility/_automaton.py` proves admits the old one is
  replaced by the old one, which only narrows the new schema. jsoncompat alone returns unknown for
  `^[ab]+$` to `^[abc]+$`. The automaton builds both patterns as automata and walks them together,
  so it proves inclusion or returns the shortest string that breaks it.

A counterexample counts only once `StrictValidator` accepts it under the original old schema and
refuses it under the new; `tests/schema/compatibility/_witness_shrink.py` then shrinks it to its
simplest values. When jsoncompat returns none, `tests/schema/compatibility/_witness.py` searches.
`_witness_build.py` writes one seed for each combination of `oneOf` branches on the smallest
instance, at most 32, instead of one shared branch index. `_witness_node.py` drops a value the old
node itself rejects, `_witness_bind.py` finds the node a value sits under, and
`_witness_document.py` names each position of a candidate. The search tries one position, then pairs
of positions, and stops after 4096 validator calls, at most 32 of them on pairs. A compatible
verdict is checked. An unknown verdict such as a raised `minimum` is still refuted by `1`, and so is
a break that needs two coordinated values, such as a number that is legal only once an optional
sibling is present. Combinations and pairs past those caps stay unsearched. The [coordinated-witness
record](../records/0029-data-contracts-oracle-coordinated-witnesses.md) holds the table and the
measured cost.

`require_oracle_agreement` compares the classifier's verdict on the stripped pair with the oracle's,
on the rule table, on reference and recursion cases and on every consecutive pair of frozen
versions. A disagreement in either direction fails CI and names the witness or proof. A
classifier that misses a break fails, and so does one that requires a major for a relationship the
automaton proves; the remedy is a stronger local proof, never a weaker schema. The oracle fails
closed with `Undecided` when jsoncompat returns unknown and no witness is found, when a
counterexample is not confirmed, or when a changed pattern uses syntax the automaton does not read.
The automaton reads the dialect's whole pattern syntax, so the last case arises only for schemas
outside the dialect.

### Evolution tests

`tests/schema/compatibility/test_evolution.py` repeats the compatibility table at nested and tagged
paths. Reference tests cover external targets and recursion, each also under the oracle.
`tests/schema/compatibility/test_patterns.py` checks every structural verdict and every derivative
verdict against the automaton. Freeze and history tests exercise insufficient bumps, missing
metadata, rollback, repinning, deletion and missing history in isolated Git repositories, on a
private set moved to `stage: released`. `tests/schema/registry/test_stage.py` covers the development
stage: an in-place edit with and without its re-pin, a refused second version and retired major,
the in-place freeze, history that accepts a development edit, compares a released revision,
refuses a return to development and fails closed on a stage it cannot read.
`tests/schema/compatibility/test_dispositions.py` covers the floor and its freeze refusal on a
synthetic next major. Hash-stability tests reject new null/default fields,
unannounced keys and changed existing values. The [evolution task
record](../records/0019-data-contracts-contract-evolution-gate.md) holds the gate's acceptance.

### ODCS catalog export

```bash
ss-track contracts export --format odcs --out "$DATA_DIR/odcs/catalog"
```

The exporter writes one ODCS 3.2 JSON document per registered JSON Schema contract, under
`<out>/<family>/<id>.json`, using the newest frozen version. The ODCS `id` is the registry's
`family/id` and `version` is that frozen version. This is a generated catalog view; the frozen JSON
Schema remains the authority for instance validation and compatibility. The command validates every
document before writing any of them with the bundled official schema, pinned by SHA-256 and upstream
commit in [ODCS schema provenance](../../../contracts/meta/standards/README.md). Validation needs no
network and no new runtime dependency. `result/command` covers the `exported` and `written` results
and their file lists, including the reference-docs command.

A schema object lists flattened schema-like property paths. Nested arrays use `/items`, tuple
positions use `/prefixItems/<n>`, and `/$defs/<name>` names a separately listed source definition.
Tagged-union branches merge by logical path, omitting their `oneOf` positions. A property gets
`logicalType` only where its encountered types agree;
`ssTrackSources` gives each original schema URN and JSON pointer. This view does not claim that ODCS
checks object membership, closed objects, conditional branches, tuple positions or other source rules.
Top-level `customProperties` include the original JSON Schema and a conservative inventory of every
source keyword and pointer, including the constructs that ODCS does not state or states differently.
The [ODCS task record](../records/0025-data-contracts-odcs-contract-export.md) records the evidence.

`schema/views/odcs_projection.py` follows local and registered external references with cycle
protection, merges branch fields and records source positions. `schema/views/odcs.py` checks the
upstream schema hash, validates and writes the views. `tests/schema/views/test_odcs.py` checks every
registered JSON Schema contract, source property and keyword, the tagged union, recursive
references, CLI results, and the pinned schema. The wheel test runs the exporter outside the
checkout.

### Generated reference

`ss-track contracts docs --out <dir>` writes a Markdown dictionary for each frozen JSON Schema contract
under `<dir>/<family>/<id>.md` and a lineage table in `<dir>/lineage.md`. Dictionaries list
schema property pointers, descriptions, enum values and their first frozen version. The lineage
lists `x-references` targets. `make lint-contracts` checks that annotated targets resolve against
the latest frozen version of the named contract. The [task record](../records/0023-data-contracts-contract-reference-docs.md)
contains the implementation and acceptance evidence.
