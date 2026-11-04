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
   writer stamps, as `tests/schema/test_agreement.py` does for the frame set. `seal` validates every
   record against the contract of its `kind`, so a writer of an unfrozen format cannot seal at all.
   A declaration reader takes its document from `schema.enforce.read_declaration`.

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
| A `pattern` is anchored with `^` and `$` and uses only ASCII literals, escapes, positive classes, groups, alternation and quantifiers: no `\d`, `\w`, `\s`, `\b`, `.`, negated class, lookaround or backreference | The rest differs between regular expression engines, or no change to it can be classified; write a literal `.` as `\.` or inside a class |
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
`--disposition view|facts|retired`, describing the previous major, and readers consume it. Choose
`view` only when every new field follows from an old record and the records it pins by a pure
function; freeze refuses `view` when the major adds or changes an operator judgment or an algorithm
revision, listed as `PROTECTED_PROPERTIES` in `src/ss_track/schema/dispositions.py`. A `view` also
needs its function: add a `View` to `src/ss_track/corpus/read_window.py` in the same change, naming
every value it derives, and test it with `check_view` on the kept real record of the older major.
Without it, reading such a record is `CONTRACT_SET_INVALID`. Freezing never rewrites a record. A
format whose facts a leak guard reads also adds the new major's entry to
`src/ss_track/corpus/projections.py`, and keeps the older one.

Freeze validates a scratch copy before publishing. Directory locking serializes publication, the
schema is created without overwriting different bytes, and the registry is replaced atomically.
A failed publication removes only a schema it created. A process killed between the two writes can
leave an unregistered candidate; the gate refuses it until a retry registers it. No frozen file is
rewritten. Review the generated change-log entry and include the candidate and registry in the change.

A new field must be absent when unused. Test production output against the previous frozen minor
and compare retained canonical bytes for unchanged inputs; schema validation alone does not detect
changed values. New-feature tests use the new schema explicitly. Existing `null` fields remain valid.

A pattern relaxation is minor only when its inclusion is proven. Removing a pattern, widening a
class or a count, adding an alternative or a part that may occur zero times, and a literal the new
pattern matches are proven by structure. A rewrite whose shape changed, such as `^(ab)*$` to
`^a*(ba)*b*$`, is minor when the derivative walk proves it. The
[current page](../impl/current/contracts.md#pattern-proofs) states the syntax and the state bound.
A relationship the walk does not finish requires a major. The test oracle checks every frozen
transition independently, and a disagreement in either direction fails CI. When it says the
classifier misses a proven relaxation, strengthen the proof in `schema/_patterns.py` or
`schema/_derivatives.py`; do not weaken a schema to obtain agreement.

## Historic formats

Use `retired_majors` for historic majors with no frozen contract. Each entry states `major`,
`status`, `reason` and `migration`; majors must be unique, sorted, and cannot also have a frozen
version. `status` is the disposition: `facts` while a retained record of that major has a route,
such as an amendment that reads it, and `retired` once none needs one. A historic major is never a
view. `migration` is the remedy ss-track gives when it refuses a
record of that major, so write it as what the holder must do. Kept compatibility fixtures are not
runtime evidence.
