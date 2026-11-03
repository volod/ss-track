# ss-track data contracts

Frozen interchangeable formats of ss-track have published definitions here, so their records can
be checked without the code that wrote them. Registry drafts explicitly name remaining gaps.
This directory is complete on its own and ships inside the `ss-track` wheel.

| Path | Holds |
| --- | --- |
| `registry.yaml` | Every contract: family, id, owner, status, frozen versions, change log |
| `<family>/<id>/<version>.json` | One frozen version, never edited, in JSON Schema 2020-12 |
| `shared/` | Value types that other contracts reference by exact version |
| `meta/dialect.json` | The restricted JSON Schema a contract may use |
| `meta/registry.json` | The shape of `registry.yaml` |

A contract is identified by `urn:ss-track:contract:<family>:<id>:<version>`, which is its `$id`. To
validate with any JSON Schema 2020-12 validator, load every frozen file, register each under its
`$id`, and validate against the version whose major equals the record's `schema_version`. `$ref`
points only at those URNs, so nothing needs a network.

A record stamps `kind` and the contract's major. It does not stamp a minor, because its seal covers
that field. `x-rules` in a contract states in words what JSON Schema cannot state, including how a
record's seal is computed.

The baseline freezes recording and corpus declarations, source and corpus manifests, frame bundles,
frame sets, staged hashes, hash comparisons and command results. Every frame-set reference annotation
resolves at its exact schema pointer. General drafts still have a `reason` and must not be treated
as validated without a frozen version.

`retired_majors` lists earlier majors with no frozen contract, each with a disposition and reason.
Historic compatibility fixtures are retained separately from usable runtime evidence.

Fixed tuples use `prefixItems` with `items: false` and exact length bounds. Only command-result
`details` is open. Descriptive capture scalars use exactly `["string", "number"]` or
`["string", "number", "null"]`. These extensions preserve the remaining closed-object and tagged-union
rules, and do not reinterpret descriptive metadata as measured quantities.
