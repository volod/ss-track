# ss-track data contracts

Every interchangeable format of ss-track has a published, versioned definition here, so a record can
be read and checked without the code that wrote it. This directory is complete on its own, and it
ships inside the `ss-track` wheel.

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
