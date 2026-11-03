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
5. Run `ss-track contracts freeze <family>/<id> --file <candidate.json> --owner <capability>`
   with `--summary "Initial contract."`. It creates the registry entry and pins after validating the
   complete proposed set. Use `--root contracts` to select a writable set explicitly.
6. Run `make lint-contracts`. Its history comparison needs a full Git checkout and the base ref
   (default `origin/main`; override with `CONTRACT_BASE_REF=<ref>`).
7. Add a test that a real output of the writer validates, and that the contract stamps what the
   writer stamps, as `tests/schema/test_agreement.py` does for the frame set.

A format the dialect cannot state stays listed as `draft`, with its `reason` and no `versions`, and
its hand-written reader stays in force.

## The dialect

`contracts/meta/dialect.json` is the authority, and its refusals are the point: each one keeps a
change classifiable.

| Rule | Reason |
| --- | --- |
| Every object has `properties` and `additionalProperties: false`, except command-result root `details` | A writer that adds a key fails its own contract, so a format cannot change unannounced |
| Every property has a `description` | The contract is what a reader has instead of this repository |
| Every node states `type`, or is a `$ref` or a `oneOf` | A `const: 1` with no `type` accepts `1.0` |
| A list of types is one type paired with `null`, or the exact capture scalar forms `["string", "number"]` and `["string", "number", "null"]` | A nullable value is common, and anything wider is a tagged union |
| A `oneOf` holds inline closed objects sharing one required `const` property with distinct values | The tag says which branch applies, so a change inside a branch can be classified |
| No `if`, `then`, `else`, `not`, `anyOf`, `allOf` or `patternProperties` | They hide which rule applies to a value |
| `$ref` names `#/$defs/<name>`, or a frozen URN with a fragment, with only annotations beside it | A reference to an exact version cannot change under a contract |
| A `pattern` is anchored with `^` and `$` and avoids `\d`, `\w`, `\s` and `\b` | Those classes differ between regular expression engines |
| `format` is `date` | No other format is enforced |
| A positional tuple uses `prefixItems`, `items: false`, and equal `minItems`/`maxItems` matching its length | Each position is checked and fingerprinted |

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
included, is covered by a pin. Copy the newest file to a candidate, change its `$id` to the proposed
version, and edit the copy. A candidate can be outside the set, or at its not-yet-registered target
path. Do not add registry pins by hand.

```bash
ss-track contracts diff record/frame-set --file frame-set-next.json --root contracts
ss-track contracts freeze record/frame-set --file frame-set-next.json --root contracts \
  --summary "Describe the change."
make lint-contracts
make ci
```

`diff` names each change by schema JSON pointer, its minimum bump and its reason. `freeze` refuses
an insufficient or non-increasing bump and validates every earlier minor in the candidate's major.
A major starts at `<major>.0.0`; a minor starts at `<major>.<minor>.0`. A larger bump is allowed but
still needs its metadata. A major also requires both `--migration "What the holder must do"` and
`--disposition view|facts|retired`, describing the previous major. These fields are metadata; freezing
does not implement a view or migrate a record. Runtime support follows its own plan task.

Freeze validates a scratch copy before publishing. Directory locking serializes publication, the
schema is created without overwriting different bytes, and the registry is replaced atomically.
A failed publication removes only a schema it created. A process killed between the two writes can
leave an unregistered candidate; the gate refuses it until a retry registers it. No frozen file is
rewritten. Review the generated change-log entry and include the candidate and registry in the change.

A new field must be absent when unused. Test production output against the previous frozen minor
and compare retained canonical bytes for unchanged inputs; schema validation alone does not detect
changed values. New-feature tests use the new schema explicitly. Existing `null` fields remain valid.

Pattern removal, literal inclusion, and single positive classes written with ASCII letters, digits,
underscore and hyphen, with repetition bounds, have local relaxation proofs. Other pattern rewrites
require a major until inclusion can be proved. The pinned `jsoncompat` oracle checks every frozen transition in the tests and a disagreement
fails CI. Its known pattern and open-object limits are described on the
[current page](../impl/current/contracts.md#evolution); do not weaken a schema to obtain agreement.

## Historic formats

Use `retired_majors` for historic majors with no frozen contract and no retained runtime evidence.
Each entry states `major`, `status: retired` and `reason`; majors must be unique, sorted, and cannot
also have a frozen version. Kept compatibility fixtures are not runtime evidence.
