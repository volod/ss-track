# ss-track data contracts

Interchangeable formats of ss-track have published definitions here, so their records can be
checked without the code that wrote them. Registry drafts explicitly name remaining gaps.
This directory is complete on its own and ships inside the `ss-track` wheel.

`registry.yaml` states the set's `stage`. Before the first release it is `development`: each
contract has one version, `1.0.0`, that may still be edited in place and re-pinned, so a record is
checked only against the set shipped with the ss-track that wrote it. From release the stage is
`released`, every version is frozen and never edited, and a change is a new version.

| Path | Holds |
| --- | --- |
| `registry.yaml` | The stage, and every contract: family, id, owner, status, versions, change log |
| `<family>/<id>/<version>.json` | One JSON Schema version, in JSON Schema 2020-12, never edited once released |
| `event/<id>/<version>.binpb` | One frozen protobuf descriptor set. It is not a JSON Schema document |
| `shared/` | Value types that other contracts reference by exact version |
| `meta/dialect.json` | The restricted JSON Schema a contract may use |
| `meta/registry.json` | The shape of `registry.yaml` |

A JSON Schema contract is identified by `urn:ss-track:contract:<family>:<id>:<version>`, which is
its `$id`. An event package uses the same URN, stored as a protobuf file option rather than `$id`.
The [runner page](../docs/impl/current/runner.md) states how a protobuf-JSON line is checked.
`ss-track contracts validate` does not parse those lines, and `ss-track contracts freeze` does not
publish an event package.

To validate with any JSON Schema 2020-12 validator, load every frozen JSON Schema file and register
each under its `$id`. Validate against the version whose major equals the record's
`schema_version`. `$ref`
points only at those URNs, so nothing needs a network.

A record stamps `kind` and the contract's major. It does not stamp a minor, because its seal covers
that field. `x-rules` in a contract states in words what JSON Schema cannot state, including how a
record's seal is computed. A `text` rule on a declaration property means the value holds a character
other than whitespace.

Declarations are YAML. A value such as `2024-01-05` is a date to a YAML 1.1 reader and text to a
YAML 1.2 one, so ss-track accepts it unquoted only where the contract states `format: date`; quote it
anywhere else.

The baseline freezes recording and corpus declarations, scenario packs, annotation labels, seeds
and masks, source and corpus manifests,
frame bundles, frame sets, staged hashes, hash comparisons and command results. Discovery runs and
candidate inventories record why a window of staged frames became a candidate for review. Every
frame-set reference annotation resolves at its exact schema pointer. General drafts still have
a `reason` and must not be treated as validated without a frozen version.

In a released set, `retired_majors` lists earlier majors with no frozen contract, each with a
disposition (`facts` or `retired`, as its `status`), a reason and the `migration` a holder of such a
record must make. A development set holds none.

Fixed tuples use `prefixItems` with `items: false` and exact length bounds. Only command-result
`details` is open. Descriptive capture scalars use exactly `["string", "number"]` or
`["string", "number", "null"]`. These extensions preserve the remaining closed-object and tagged-union
rules, and do not reinterpret descriptive metadata as measured quantities.

Every version's `change` gives its class and summary; in a development set it is `initial`. In a
released set a major transition also gives `migration` and
`disposition` (`view`, `facts` or `retired`) for the predecessor major. ss-track reads a `view`
record as the next major in memory, keeps a `facts` record readable for inspection and comparison
but not as evidence, and refuses a `retired` one. The metadata supplies no executable migration
code, and no record is rewritten. `ss-track contracts diff` explains a
candidate by JSON pointer and `ss-track contracts freeze` generates its pins and log entry. CI
compares released bytes and entries with Git history and rejects an insufficient version bump.
