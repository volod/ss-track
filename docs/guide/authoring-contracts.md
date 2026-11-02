# Authoring Contracts

A format that crosses a process, host, language, person or software version needs a contract, added
in the change that introduces it. The
[specification](../design/spec.md#17-data-contracts-and-schema-evolution) states the rules, and the
[current page](../impl/current/contracts.md) states what exists.

## Add a contract

1. Choose the family: `declaration` for operator-written YAML, `record` for sealed JSON, `result`
   for command output, `shared` for value types other contracts reference.
2. Create `contracts/<family>/<id>/1.0.0.json`, or `<major>.0.0.json` for a format already shipped
   at that `schema_version`. A record the code writes today must conform with no byte changed.
3. Set `$schema` to JSON Schema 2020-12 and `$id` to
   `urn:ss-track:contract:<family>:<id>:<version>`, and give the root a `title` and `description`.
4. State the format, as in [the dialect](#the-dialect).
5. Add an entry to `contracts/registry.yaml`, in family and id order, with an `owner` from the
   [capability registry](../design/spec.md#capability-registry) and a `change` of class `initial`.
6. Run `make lint-contracts`. Each finding states the computed `file_sha256` or fingerprint. Copy
   each into the entry and run it again.
7. Add a test that a real output of the writer validates, and that the contract stamps what the
   writer stamps, as `tests/schema/test_agreement.py` does for the frame set.

A format the dialect cannot state stays listed as `draft`, with its `reason` and no `versions`, and
its hand-written reader stays in force.

## The dialect

`contracts/meta/dialect.json` is the authority, and its refusals are the point: each one keeps a
change classifiable.

| Rule | Reason |
| --- | --- |
| Every object has `properties` and `additionalProperties: false` | A writer that adds a key fails its own contract, so a format cannot change unannounced |
| Every property has a `description` | The contract is what a reader has instead of this repository |
| Every node states `type`, or is a `$ref` or a `oneOf` | A `const: 1` with no `type` accepts `1.0` |
| A list of types is one type paired with `null`, in that order | A nullable value is common, and anything wider is a tagged union |
| A `oneOf` holds inline closed objects sharing one required `const` property with distinct values | The tag says which branch applies, so a change inside a branch can be classified |
| No `if`, `then`, `else`, `not`, `anyOf`, `allOf` or `patternProperties` | They hide which rule applies to a value |
| `$ref` names `#/$defs/<name>`, or a frozen URN with a fragment, with only annotations beside it | A reference to an exact version cannot change under a contract |
| A `pattern` is anchored with `^` and `$` and avoids `\d`, `\w`, `\s` and `\b` | Those classes differ between regular expression engines |
| `format` is `date` | No other format is enforced |

A nullable value cannot use a `$ref`, because a union of a reference and `null` is untagged. Repeat
the pattern inline, as `parent_stream_id` does in `record/frame-set`, and add a line to
`tests/schema/test_agreement.py`.

Annotate what a number or code means with the [annotations of section
17.2](../design/spec.md#172-identity-and-versions). State rules JSON Schema cannot state under
`x-rules`, as named sentences. `x-references` is `<family>/<id>#<pointer>`, a JSON pointer into that
contract's schema. Mark a property `public` in `x-sensitivity` only when a public descriptor may
carry it, because loosening it later takes a major.

## Freeze with care

A frozen file is never edited, so read it once more before it merges. Everything in it, descriptions
included, is covered by a pin. Until `ss-track contracts freeze` exists, change a format by copying
the newest file to the next version, editing the copy, and adding a version to the registry entry
with a `change` of class `patch`, `minor` or `major` per [section
17.3](../design/spec.md#173-compatibility-rules). A major also states its `migration`, because that
text is what a refusal shows a holder of an old record.
