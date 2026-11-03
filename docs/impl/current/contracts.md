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
| `declaration/dataset` | `1.0.0` |
| `declaration/recording` | `2.0.0` |
| `record/corpus-manifest` | `3.0.0` |
| `record/frame-bundle` | `3.0.0` |
| `record/frame-set` | `1.0.0` |
| `record/staged-hashes` | `1.0.0` |
| `record/hash-comparison` | `1.0.0` |
| `record/source-manifest` | `2.0.0` |
| `result/command` | `1.0.0`, `1.1.0`, `1.2.0`, `1.3.0` |

`declaration/dataset` states the operator-supplied title, description, license, citation, address
and publication date. It can be checked with `ss-track contracts validate` and is consumed by the
[dataset descriptor](corpus.md#dataset-descriptors).

`shared/types` supplies hashes and identifiers. Every shipped document format has a frozen contract,
and every frame-set reference resolves at its annotated schema pointer. Capture fields preserve
operator descriptions and numbers: the dialect allows exactly `["string", "number"]` and its nullable
form. Numeric descriptive metadata has no physical-unit claim; declared range retains metres.
The extension does not allow arbitrary scalar unions or change a recording's accepted values.

Declaration and sealed-record majors are independent constants in `corpus/declaration.py`,
`corpus/builder.py` and `corpus/importer.py`; their existing integer values and written bytes remain
unchanged. The corpus contract requires source terms even at major 3: an earlier schema-3 manifest
without them fails explicit validation, and at runtime the read path tells it apart as a stated
shape with the `facts` disposition, as no major does.

Earlier recording/source major 1 and corpus/bundle majors 1 and 2 are listed in `retired_majors`
without frozen schemas. Each entry's `status` is its disposition, `facts` or `retired`, and the read
path consumes it. Source major 1 is `facts`, because `--amend-terms` reads its stated facts and
writes the current major; every other entry is `retired`, because no retained record needs it.
The reason distinguishes retained runtime evidence from historic test fixtures, and `migration`
states what a holder of such a record must do. That text is the remedy a
`RECORD_SCHEMA_UNSUPPORTED` refusal of an older record gives. `result/command` 1.3.0 lists either
status; it was frozen for this and for lineage `not_compared`.

## Runtime enforcement

The [enforcement record](../records/0020-data-contracts-contract-enforced-readers.md) holds the
accepted task, its decisions and its evidence.

Contracts state structure at runtime, in `schema/enforce.py`, with the refusal codes the readers had:

- `read_declaration` parses operator YAML with the strict parser and validates the whole document
  under the newest frozen version of the major its reader reads. A violation is `MANIFEST_INVALID`
  and names the URN and the first violation, a wrong `schema_version` first; details list up to 20.
  An unreadable file is `MANIFEST_INVALID` too. The corpus readers then take typed values through
  `corpus/fields.py` and apply only the rules a contract states as `x-rules` or does not state.
- `require_record` validates a record, already holding its seal, under the newest frozen version of
  the major it stamps, and `corpus/sealed.py` `seal` calls it before returning. A writer defect,
  including an unregistered kind, a major with no frozen version or a `NaN`, is `RECORD_INVALID`
  with nothing written.
- `older_remedy` returns the change log's migration for an older major of a record kind.
- `older_disposition` returns how a record of an earlier major is read: the strictest disposition
  of each major it steps through to the current one, from `Contract.disposition_of`, which reads a
  `retired_majors` entry or the `change.disposition` of the major transition that replaced it. A
  step no change log states gives none, and the record is refused as unwritten.
  `readable_majors` lists the current major and every one a chain of views reaches, which a
  refusal reports as `accepted_schema_versions`.
- `is_shared_type` checks a value against a `shared/types` definition. Run ids and corpus ids given
  on the command line are checked as identifiers this way, so the pattern has one statement.

The installed set is read once per process. A sealed read never validates: it checks seal, kind and
the disposition of its major, so `corpus verify` costs what it did before. Validation does not run
`x-rules`. The [corpus read path](corpus.md#reading-sealed-records) applies dispositions.

The validator reports a tagged `oneOf` through the branch its tag selects, so a wrong seed in a
`blur` recipe is `/groups/0/encounters/0/streams/0/generated_cases/0/seed` and not "not valid under
any of the given schemas". A tag no branch states is named with the tags that exist, and a missing tag
as a required property. An untagged union keeps the standard report.

YAML dates are normalized to their ISO text as `strict_yaml.YamlDate`, a `str` that validates as one.
A reader's text field refuses it, so an unquoted `holder: 2024-01-05` keeps the refusal it had; a date
field takes it. Text that is only whitespace is also refused by the readers. Neither rule is in a
declaration contract yet, so `contracts validate` accepts both; `data-contracts-audit` in the
[plan](../plan.md#data-contracts-audit-optional) owns that disagreement.

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
| `schema/strict.py` | The local validator, violation reports and tagged-union reporting |
| `schema/store.py` | The registry, frozen files, identity and `$ref` resolution by URN |
| `schema/fingerprints.py` | The schema walk and both fingerprints |
| `schema/dialect.py` | The meta-schema check and the shared-tag rule |
| `schema/check.py` | Registry, file, dialect, identity and reference checks without Git |
| `schema/evolution.py`, `schema/_change_rules.py` | JSON-pointer comparison and keyword compatibility rules |
| `schema/_patterns.py` | The structural pattern-inclusion proof |
| `schema/versioning.py` | Minimum bump, change-log, disposition-floor and backward-transitive policy |
| `schema/dispositions.py` | The disposition floor and the properties no view may derive |
| `schema/freeze.py`, `schema/_publishing.py` | Candidate validation, generated pins and locked publication |
| `schema/history.py` | `make lint-contracts`: merge-base immutability and transition checks |
| `schema/commands.py` | `contracts list` and `contracts validate` |
| `schema/enforce.py` | Runtime validation of declarations and records, change-log remedies and dispositions, and shared types |
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
`pattern_findings` in `schema/dialect.py` then refuses any pattern outside the syntax
`schema/_patterns.py` reads: ASCII literals, escapes, positive classes, groups, alternation and
quantifiers, with no top-level alternation. `.` and a negated class match line terminators and
astral characters differently in Python's `re` and ECMA-262, and no change to lookaround or a
backreference could be classified. A literal `.` stays available escaped or inside a class.
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
- the pattern syntax, which needs a parser and so cannot be a meta-schema rule;
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
keeps the few statements a contract and code still share, such as a writer's `kind` and major, from
drifting. `tests/_sealing.py` seals a fixture without its contract, because production `seal` refuses
the damaged records that read tests need.

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
damage them. An amendment's archived copy of a
retired source major is checked against the original record and its seal, not against today's shape.
Subprocess outputs are checked by retained examples and end-to-end
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
constraint under open `details` is major because previously legal values may fail it. A `const`
replaced by an `enum` that holds its value is one minor change at `/enum`, as `result/command` 1.3.0
did for a historic major's status.

Freeze stages the whole set, verifies identities, strict JSON, dialect, references and pins, then
checks the bump and backward compatibility with every earlier minor in the same major. Major
transitions require nonblank migration text and a `change.disposition` of `view`, `facts` or `retired`
for the predecessor major. `view` is refused below the disposition floor: a major that adds or
changes a property in `PROTECTED_PROPERTIES` (`schema/dispositions.py`: rights, sensitivity,
scenario rights, retention, split, group, encounter, decode policy, transform, recipe and revision)
floors at `facts`. The floor reads property names on each major change's pointer, and inside an added
node except what an added list holds, since a view may derive an empty list. A removal never raises
it. A freeze installs no view: a view is code in `corpus/read_window.py`, and a declared view with no
function there is `CONTRACT_SET_INVALID` when a record of that major is read.
`CONTRACT_SET_INVALID` also reports a bad candidate or forbidden publication.
Directory locking and an atomic registry replacement prevent concurrent freezes from losing entries.
A crash between schema creation and registry replacement leaves an unregistered file, which fails
the gate and can be registered by retrying. All preexisting frozen bytes remain intact.

### Pattern proofs

`schema/_patterns.py` proves pattern inclusion by structure. The old and new pattern are read as
sequences of parts, and the new one must hold the old one's parts in order, each admitting at least
what its counterpart does, plus parts that may occur zero times. A class covers a smaller class, a
repetition a narrower count, and a group covers each old alternative with some new one. An old
repetition may give up one occurrence to a new single part, so `^[0-9a-f]{64}$` fits
`^[a-z0-9][a-z0-9._-]{0,63}$`. Removing a pattern and a literal the new pattern matches are also
relaxations. The syntax read is ASCII literals, escapes, positive classes, groups, alternation and
quantifiers, where `re` and ECMA-262 agree, and the dialect refuses every other pattern. A true
inclusion of a different shape, such as `^(ab)*$` within `^a*(ba)*b*$`, conservatively requires a
major. On the patterns the frozen contracts use, the proof decides
exactly what an automaton decides.

### Independent oracle

The [oracle record](../records/0022-data-contracts-contract-oracle-coverage.md) holds the accepted
task, its decisions and its evidence. The oracle lives in the tests and shares no compatibility
rule with the classifier. `tests/schema/_oracle.py` strips meaning keywords, inlines references and
keeps a recursive target once under `$defs`, so recursive shapes terminate. Two sound rewrites then
run at aligned positions, and `jsoncompat==0.5.0` `analyze_compat` decides the result:

- an explicitly open object in the old schema states each property the new one adds as any JSON
  value, which accepts exactly what it did. Without it, jsoncompat calls an optional string
  constraint in open `details` compatible, although `{"value": 0}` then fails. The project does
  not patch third-party packages, so this rewrite is the fix.
  `test_open_object_workaround_is_still_needed` fails once a pinned release sees the break itself,
  which is the signal to remove the rewrite;
- a new pattern that `tests/schema/_automaton.py` proves admits the old one is replaced by the old
  one, which only narrows the new schema. jsoncompat alone returns unknown for `^[ab]+$` to
  `^[abc]+$`. The automaton builds both patterns as automata and walks them together, so it proves
  inclusion or returns the shortest string that breaks it.

A counterexample counts only once `StrictValidator` accepts it under the original old schema and
refuses it under the new; it is then shrunk to its simplest values. When jsoncompat returns none,
`tests/schema/_witness.py` builds the old schema's smallest instances and tries each position with
every boundary value the two schemas name and each object with every property name they state. So
a compatible verdict is checked, and an unknown verdict such as a raised `minimum` is still refuted,
by `1`.

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

`tests/schema/test_evolution.py` repeats the compatibility table at nested and tagged paths.
Reference tests cover external targets and recursion, each also under the oracle.
`tests/schema/test_patterns.py` checks every structural proof against the automaton. Freeze and
history tests exercise insufficient bumps, missing metadata, rollback, repinning, deletion and
missing history in isolated Git repositories.
Historic replay tests project observed keys and types from the five real bumps; they do not invent
complete historic schemas or count a changed stamp as proof. The same replay gives each bump its
warranted disposition: the floor and a candidate view applied to the real older record give `view`
for bundle 1 to 2, bundle 2 to 3 and corpus 2 to 3, and `facts` for corpus 1 to 2 and source 1 to 2.
`tests/schema/test_dispositions.py` covers the installed dispositions, the floor and its freeze
refusal. Hash-stability tests replay the real
frame-set producer, validate existing command output against the previous minor and reject new
null/default fields, unannounced keys and changed existing values. The
[evolution task record](../records/0019-data-contracts-contract-evolution-gate.md) holds the gate's
acceptance.

### Generated reference

`ss-track contracts docs --out <dir>` writes a Markdown dictionary for each frozen contract
under `<dir>/<family>/<id>.md` and a lineage table in `<dir>/lineage.md`. Dictionaries list
schema property pointers, descriptions, enum values and their first frozen version. The lineage
lists `x-references` targets. `make lint-contracts` checks that annotated targets resolve against
the latest frozen version of the named contract. The [task record](../records/0023-data-contracts-contract-reference-docs.md)
contains the implementation and acceptance evidence.
