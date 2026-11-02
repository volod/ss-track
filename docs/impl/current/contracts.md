# Contracts

Every interchangeable format has a published definition that a reader can use without this
repository. `contracts/` at the project root holds the frozen set, `src/ss_track/schema/` reads and
checks it, and the [specification](../../design/spec.md#17-data-contracts-and-schema-evolution)
states the rules. The [contract registry
record](../records/0017-data-contracts-contract-registry.md) keeps the accepted task, its decisions
and its evidence. To add or change a contract, follow the [authoring
guide](../../guide/authoring-contracts.md).

`record/frame-set` is the first contract, and `shared/types` holds the value types it references.
The other shipped formats have no contract yet, and their hand-written readers stay the only
statement of them. Nothing here changes a reader: no corpus command consults a contract.

## Commands

```bash
ss-track contracts list
ss-track contracts validate --file frame-set.json
ss-track contracts validate --file frame-set.json --contract record/frame-set --version 1.0.0
```

Neither reads the data root, and both work from an installed wheel. Each logs one JSON record, as
every command does.

`list` states each contract, its family, owner and status, and each frozen version with its URN,
pins and change-log entry. `validate` checks every field of a JSON file under one frozen version
and, for the `record` family, its seal. With no `--contract` it takes the contract from the file's
`kind`. With no `--version` it takes the newest version of the major the file stamps, or the newest
if it stamps none. Its result names the URN and whether a seal was checked.

`validate` checks structure and a seal, and no `x-rules` entry. A rule across fields or files stays
in the code that reads the record, so a resealed record in the wrong order passes here and fails at
`corpus verify`. It reads JSON only, more strictly than a parser needs to: a repeated key, `NaN` and
`Infinity` are refused, because another reader may keep a different value.

| Code | Raised when |
| --- | --- |
| `RECORD_INVALID` | A file is not strict JSON, or breaks a contract outside the `declaration` family. Details name the URN and up to 20 violations by JSON pointer |
| `MANIFEST_INVALID` | A file breaks a `declaration` contract |
| `RECORD_TAMPERED` | A record of valid shape does not match its seal |
| `CONTRACT_UNKNOWN` | The named contract or version does not exist, no contract states the file's `kind`, the file names no format and no `--contract` was given, a draft has no frozen version, or a `shared` contract was named, because it states no document |
| `CONTRACT_SET_INVALID` | The registry breaks its schema, or a frozen file is missing or differs from the hash the registry pinned |

## The set

| Path | Holds |
| --- | --- |
| `contracts/registry.yaml` | Each contract's family, id, owner, status and frozen versions, with `file_sha256`, both fingerprints and the change-log entry |
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
| `schema/check.py` | `make lint-contracts` |
| `schema/commands.py` | `contracts list` and `contracts validate` |

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

`make lint-contracts` runs inside `make ci` and reports each of these by contract and version:

- the registry against `meta/registry.json`, with contracts in family and id order and versions in
  numeric order, so a repeat cannot hide;
- a file on disk the registry does not list, and a listed file that is missing;
- `file_sha256`, which catches any edit, formatting included;
- `$id` against the path;
- the dialect, including the rule that the branches of a `oneOf` share one required `const` property
  with distinct values, which needs two branches at once and so cannot be a meta-schema rule;
- `schema_version` as the integer const of the major, in `declaration` and `record` contracts, and
  `kind` as a const with the seal required, in `record` contracts;
- both fingerprints, stating the pinned and computed values, which is how an author learns them
  until `freeze` exists;
- every `$ref`, once every file above is intact.

The fingerprints walk schema positions, because a property may be named `title` or `description`,
and such a key is a name and not an annotation. `structure` drops annotations and `$id`, so two
versions of one shape compare equal. `meaning` keeps annotations and `const` and `enum` values, and
drops whatever is left empty, so a definition with no annotation does not move it.

The gate compares a file only with its registry entry. A file edited together with its entry passes,
and only review or a comparison with the history can see that.

`tests/schema/` proves each construct the dialect refuses at the root and at each nested position,
each way of breaking the set, the wheel built from a source distribution as `uv build` builds it,
and a consumer in `tests/schema/_standalone.py` that imports no project code. `test_agreement.py`
keeps a contract and its writer from drifting until readers take their rules from contracts.
