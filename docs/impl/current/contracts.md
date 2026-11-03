# Contracts

Frozen contracts describe interchangeable formats for readers outside this repository. `contracts/`
at the project root holds the frozen set, `src/ss_track/schema/` reads and
checks it, and the [specification](../../design/spec.md#17-data-contracts-and-schema-evolution)
states the rules. The [contract registry
record](../records/0017-data-contracts-contract-registry.md) keeps the accepted task, its decisions
and its evidence. To add or change a contract, follow the [authoring
guide](../../guide/authoring-contracts.md).

The [corpus baseline record](../records/0018-data-contracts-corpus-contract-baseline.md) records the
baseline scope and evidence. The installed set contains these document contracts:

| Contract | Frozen version |
| --- | --- |
| `declaration/corpus` | `3.0.0` |
| `declaration/recording` | `2.0.0` |
| `record/corpus-manifest` | `3.0.0` |
| `record/frame-bundle` | `3.0.0` |
| `record/frame-set` | `1.0.0` |
| `record/staged-hashes` | `1.0.0` |
| `record/hash-comparison` | `1.0.0` |
| `record/source-manifest` | `2.0.0` |
| `result/command` | `1.0.0`, `1.1.0` |

`shared/types` supplies hashes and identifiers. Every shipped document format has a frozen contract,
and every frame-set reference resolves at its annotated schema pointer. Capture fields preserve
operator descriptions and numbers: the dialect allows exactly `["string", "number"]` and its nullable
form. Numeric descriptive metadata has no physical-unit claim; declared range retains metres.
The extension does not allow arbitrary scalar unions or change a recording's accepted values.

Declaration and sealed-record majors are independent constants in `corpus/declaration.py`,
`corpus/builder.py` and `corpus/importer.py`; their existing integer values and written bytes remain
unchanged. The corpus contract requires source terms even at major 3: an earlier schema-3 manifest
without them fails explicit validation. Normal corpus readers still apply their existing rules and
refusal codes; none consults a schema at runtime yet.

Earlier recording/source major 1 and corpus/bundle majors 1 and 2 are listed in `retired_majors`
without frozen schemas. The reason distinguishes retained runtime evidence from historic test
fixtures. This registry metadata does not change the reader's accepted majors or amendment path.

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
| `CONTRACT_UNKNOWN` | The named contract or version does not exist, no contract states the file's `kind`, the file names no format and no `--contract` was given, a draft has no frozen version, or a `shared` contract was named, because it states no document |
| `CONTRACT_SET_INVALID` | The registry breaks its schema, or a frozen file is missing or differs from the hash the registry pinned |

## The set

| Path | Holds |
| --- | --- |
| `contracts/registry.yaml` | Each contract's family, id, owner, status and frozen versions, with `file_sha256`, both fingerprints, the change-log entry and optional retired-major dispositions |
| `contracts/<family>/<id>/<version>.json` | One frozen version, whose `$id` is `urn:ss-track:contract:<family>:<id>:<version>` |
| `contracts/shared/types/` | The `sha256` and `identifier` value types |
| `contracts/meta/dialect.json` | The restricted JSON Schema a contract may use |
| `contracts/meta/registry.json` | The shape of `registry.yaml` |
| `contracts/README.md` | What a consumer holding only this directory needs |

`pyproject.toml` maps the directory to the package `ss_track.contract_files`. That mapping rules out
package discovery, so `packages` is an explicit list, and `tests/schema/test_packaging.py` fails
when a package is missing from it. `contracts/__init__.py` exists because an editable install finds
a mapped package only through one. `ss_track.schema.store.default_root` gives one lookup for a
checkout and a wheel.

| Module | Owns |
| --- | --- |
| `schema/strict.py` | The local validator and violation reports |
| `schema/store.py` | The registry, frozen files, identity and `$ref` resolution by URN |
| `schema/fingerprints.py` | The schema walk and both fingerprints |
| `schema/dialect.py` | The meta-schema check and the shared-tag rule |
| `schema/check.py` | Registry, file, dialect, identity and reference checks without Git |
| `schema/evolution.py`, `schema/_change_rules.py` | JSON-pointer comparison and keyword compatibility rules |
| `schema/versioning.py` | Minimum bump, change-log and backward-transitive policy |
| `schema/freeze.py`, `schema/_publishing.py` | Candidate validation, generated pins and locked publication |
| `schema/history.py` | `make lint-contracts`: merge-base immutability and transition checks |
| `schema/commands.py` | `contracts list` and `contracts validate` |
| `schema/_documents.py`, `strict_json.py` | Private document parsing and shared strict JSON decoder hooks |

`ss_track.schema` imports nothing from `ss_track.corpus`, because the corpus writers will validate
through it. `ss_track.refusal`, `ss_track.canonical` and `ss_track.strict_yaml` sit below both, and
a test holds that import direction.

## Validation

`schema/strict.py` extends the standard validator at two points where it is loose. `1.0` and `True`
are not integers. `$` in a `pattern` means the end of the value, as it does in ECMA-262: Python's
`re` would also match before a final newline, so a hash with one would pass here and fail elsewhere.
`date` is the only `format` the dialect allows, because no other is enforced with the installed
dependencies, and an unenforced format would read as a rule.

The dialect closes what it can for a third-party validator. It refuses `\d`, `\w`, `\s` and `\b`,
whose meaning differs between regular expression engines, and bounds every pattern at both ends.
What stays looser elsewhere is `1.0` for an integer, which JSON Schema itself accepts, and a final
newline under an engine with Python's `$`.

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
- `schema_version` as the integer const of the major, in `declaration` and `record` contracts, and
  `kind` as a const with the seal required, in `record` contracts;
- both fingerprints, stating the pinned and computed values; `freeze` generates these pins;
- every `$ref`, once every file above is intact.

The fingerprints walk schema positions, because a property may be named `title` or `description`,
and such a key is a name and not an annotation. Fixed `prefixItems` positions are walked in order;
`items: false` and object openness affect structure, while tuple units and descriptions affect
meaning. `structure` drops annotations and `$id`, so two
versions of one shape compare equal. `meaning` keeps annotations and `const` and `enum` values, and
drops whatever is left empty, so a definition with no annotation does not move it.

The history gate also compares every frozen file and its complete version entry with the merge
base of `HEAD` and `CONTRACT_BASE_REF` (default `origin/main`). It compares with `HEAD` too, so local
edits to a version already committed on the feature branch are caught. Deleting a version or
editing it together with its registry pins fails. Missing refs and shallow history fail closed.
A baseline predating `contracts/registry.yaml` permits the initial set; all subsequent transitions
still undergo compatibility checks. `python -m ss_track.schema.check --root <contracts>` remains the
Git-free check for an installed or copied set.

CI checks out full history. A pull request uses its base SHA, and a push uses its before SHA, so a
push to main cannot compare only with itself. The gate recalculates every transition's required
bump and verifies every earlier minor of the same major, including transitions entered by hand.

`tests/schema/` proves each construct the dialect refuses at the root and at each nested position,
each way of breaking the set, the wheel built from a source distribution as `uv build` builds it,
and a consumer in `tests/schema/_standalone.py` that imports no project code. `test_agreement.py`
keeps a contract and its writer from drifting until readers take their rules from contracts.

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
session. It checks records before tests deliberately damage them. An amendment's archived copy of a
retired source major is checked against the original record and its seal, not against today's shape.
Subprocess outputs are checked by retained examples and end-to-end
artifact validation rather than an in-process hook. `tests/schema/examples/` holds an example of
every frozen document contract. Baseline tests also hold the refusal-code enum equal to `RefusalCode`,
check units and vocabularies, exercise transform branches and resolve the available frame-set
references. Scalar-union fixtures check text, numeric, nullable and invalid values. Runtime reader
enforcement remains future work under `contract-enforced-readers`.

## Evolution

```bash
ss-track contracts diff record/frame-set --file frame-set-next.json --root contracts
ss-track contracts freeze record/frame-set --file frame-set-next.json --root contracts \
  --summary "Describe the change."
```

The candidate's `$id` names its family, id and proposed version. `--root` defaults to the installed
contract set; publishing needs a writable set. Initial contracts also require `--owner`. `diff`
returns `status: diffed`, `contract`, `version`, `required_bump`, and `changes`, each with `pointer`,
`class` and `reason`. A pointer refers to the new schema, or to the old schema for a removed node.
A no-change or initial candidate reports `required_bump: none`. `freeze` returns the same shape with
`status: frozen`; these outputs and the optional listing disposition use `result/command` 1.1.0.
Existing command outputs still validate under 1.0.0.

The walk compares nested properties, list items, fixed tuple positions, local and external reference
targets, capture scalar unions and tagged branches matched by tag value. Reordering branches is
not a change. Recursive shapes terminate by active reference pairs; dangling references and alias
cycles refuse. Semantic annotations cannot silently change within a major. Adding an optional
constraint under open `details` is major because previously legal values may fail it.

Freeze stages the whole set, verifies identities, strict JSON, dialect, references and pins, then
checks the bump and backward compatibility with every earlier minor in the same major. Major
transitions require nonblank migration text and a `change.disposition` of `view`, `facts` or `retired`
for the predecessor major. No runtime view is installed by freezing; `record-read-window` owns
consuming that metadata. `CONTRACT_SET_INVALID` reports a bad candidate or forbidden publication.
Directory locking and an atomic registry replacement prevent concurrent freezes from losing entries.
A crash between schema creation and registry replacement leaves an unregistered file, which fails
the gate and can be registered by retrying. All preexisting frozen bytes remain intact.

Pattern inclusion is proven for removal, a literal, or a single positive class written with ASCII
letters, digits, underscore and hyphen, with repetition bounds. Other rewrites conservatively require
a major. The dev-only `jsoncompat==0.5.0`
oracle is independent of runtime classification. Tests strip semantic annotations, resolve references
and compare its backward-compatibility verdict with each frozen transition; disagreement or error
fails CI. It rejects `^[ab]+$` to `^[abc]+$`, although inclusion is provable, and accepts an optional
string constraint in an otherwise open object, although a numeric value then fails. Regression tests
retain both disagreements as refusal cases; `contract-oracle-coverage` owns improving this coverage.
Until then those transitions cannot pass the independent CI check. Recursive shapes also need
independent-oracle coverage in that task; the classifier itself handles them.

`tests/schema/test_evolution.py` repeats the compatibility table at nested and tagged paths.
Reference tests cover external targets and recursion. Freeze and history tests exercise insufficient
bumps, missing metadata, rollback, repinning, deletion and missing history in isolated Git repositories.
Historic replay tests project observed keys and types from the five real bumps; they do not invent
complete historic schemas or count a changed stamp as proof. Hash-stability tests replay the real
frame-set producer, validate existing command output against the previous minor and reject new
null/default fields, unannounced keys and changed existing values. The
[evolution task record](../records/0019-data-contracts-contract-evolution-gate.md) holds acceptance
and the routed oracle limitation.
