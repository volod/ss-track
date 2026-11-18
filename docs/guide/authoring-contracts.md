# Authoring Contracts

A format that crosses a process, host, language, person or software version needs a contract, added
in the change that introduces it. The
[specification](../design/spec.md#17-data-contracts-and-schema-evolution) states the rules, and the
[current page](../impl/current/contracts.md) states what exists.

## Add a contract

1. Choose the family: `declaration` for operator-written YAML, `record` for sealed JSON, `result`
   for command output, `shared` for value types other contracts reference. An event package is not
   a JSON Schema file. Follow [event packages](#event-packages).
2. Create `contracts/<family>/<id>/1.0.0.json`. Before release every contract is at `1.0.0` and
   stamps `schema_version: 1`. A record the code writes today must conform with no byte changed.
3. Set `$schema` to JSON Schema 2020-12 and `$id` to
   `urn:ss-track:contract:<family>:<id>:<version>`, and give the root a `title` and `description`.
4. State the format, as in [the dialect](#the-dialect).
5. Run `ss-track contracts freeze <family>/<id> --file <candidate.json> --owner <capability>`
   with `--summary "Initial contract."`. It creates the registry entry and pins after validating the
   complete proposed set. Use `--root contracts` to select a writable set explicitly.
6. Run `make lint-contracts`. Its history comparison needs a full Git checkout and the base ref
   (default `origin/main`; override with `CONTRACT_BASE_REF=<ref>`).
7. Give the writer a `RecordFormat` that it stamps with `stamp()`, add it to the formats
   `tests/schema/registry/test_agreement.py` holds against their contracts, and add a test that a
   real output of the writer validates. `seal` validates every record against the contract of its
   `kind`, so a writer of an unfrozen format cannot seal at all. A declaration reader takes its
   document from `schema.validation.enforce.read_declaration`.

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
`tests/schema/registry/test_agreement.py`.

Annotate what a number or code means with the [annotations of section
17.2](../design/spec.md#172-identity-and-versions). State rules the dialect cannot state under
`x-rules`, as named sentences. A free-text declaration property, a string no pattern, vocabulary or
format bounds, states `text`, the not-blank rule its reader enforces; `test_agreement.py` checks it.
A YAML date is accepted only where a node states `format: date`, so no contract needs to say so.
`x-references` is `<family>/<id>#<pointer>`, a JSON pointer into that contract's schema. Mark a
property `public` in `x-sensitivity` only when a public descriptor may carry it, because loosening
it later takes a major.

## Change a contract before release

The registry states `stage: development` until the first release ([spec section
17.7](../design/spec.md#177-development-stage-and-release)). Each contract then has one version,
`1.0.0`, and a change to it, including the fix of an architecture or planning mistake, is an edit
in place, never a new version:

```bash
cp contracts/record/frame-set/1.0.0.json frame-set.json   # edit the copy; keep its $id at 1.0.0
ss-track contracts diff record/frame-set --file frame-set.json --root contracts
ss-track contracts freeze record/frame-set --file frame-set.json --root contracts \
  --summary "Initial contract."
make ci
```

`freeze` replaces the file and re-pins its registry entry, and refuses any version but `1.0.0`. Update
the writer, its fixtures and tests in the same change. Add no version, `retired_majors` entry,
disposition, view or historic fixture to keep outdated development data or tests readable.

A data root's `contract-set.json` pins structure and meaning for record and shared contracts. A
command on a root written before either changes refuses with `RECORD_SCHEMA_UNSUPPORTED` and
`changed_contracts`. A structure-only stamp cannot prove the earlier meaning and is also refused.
If the stamp is missing, an unstamped root containing record-shaped evidence is refused instead of
being stamped under the current set. Regenerate it: delete the root's sealed datasets and
`contract-set.json`, keep operator-written declarations, labels and review decisions, and run the
commands that built the datasets again. An
edit of descriptions or examples also asks for regeneration, because the meaning fingerprint
cannot distinguish editorial prose from a changed interpretation. A change that alters the shape of
an operator-written input also edits every retained one in the same change and states the edit in its
task record. `tests/schema/registry/test_retained_inputs.py` holds each input the repository keeps
to its declaration contract, and lists them, so an input it does not name fails there too.

A record or shared contract may `$ref` only record and shared contracts, the families the stamp
pins, so that the stamp covers every contract a record's shape depends on; the gate refuses any
other reference.

## Freeze with care

The rest of this guide applies once the set is released: `contract-release-freeze` moves it to
`stage: released`, and the gate refuses a return to development. A frozen file is never edited,
so read it once more before it merges. Everything in it, descriptions included, is covered by a
pin. Copy the newest file to a candidate, change its `$id` to the proposed
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
an insufficient or non-increasing bump and validates every earlier minor in the candidate's major. A
major starts at `<major>.0.0`; a minor starts at `<major>.<minor>.0`. A larger bump is allowed but
still needs its metadata. A major also requires both `--migration "What the holder must do"` and
`--disposition view|facts|retired`, describing the previous major, and readers consume it. Choose
`view` only when every new field follows from an old record and the records it pins by a pure
function; freeze refuses `view` when the major adds or changes an operator judgment or an algorithm
revision, listed as `PROTECTED_PROPERTIES` in `src/ss_track/schema/compatibility/dispositions.py`. A
property that holds a new operator judgment or algorithm revision joins that list in the change that
adds it, because the floor and the read path match it by name. A `view` also needs its function: add
a `View` to the owning area and register it with `src/ss_track/core/evidence/read_window.py` in the
same change, naming every value it derives; `tests/corpus/records/test_historic_records.py` then
runs `check_view` on each kept real record of the older major. Without it, reading such a record is `CONTRACT_SET_INVALID`.
Freezing never rewrites a record. A format whose facts a leak guard reads also adds the new major's
entry to `src/ss_track/corpus/records/projections.py`, and keeps the older one.

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
classifier misses a proven relaxation, strengthen the proof in `schema/compatibility/patterns.py` or
`schema/compatibility/derivatives.py`; do not weaken a schema to obtain agreement.

## Event packages

An event package is a protobuf file under `src/ss_track/contract/proto/`, not a JSON Schema
document. `ss-track contracts freeze` refuses `event/<id>`. Publish with `make proto-gen`, which
writes `contracts/event/<id>/<version>.binpb` only when that file is missing or already identical,
and refreshes the generated Python bindings. Put the registry pins in the same change. `make
proto-check` fails when the image, the bindings, buf lint, buf format or `buf breaking` disagree
with that frozen image.

The file option `contract_urn` is `urn:ss-track:contract:event:<id>:<version>`. The protobuf
package is `ss_track.event.<id>.v<major>`. Set `json_name` to the proto field name. Do not edit a
frozen image. A change to a file that other packages import changes their image bytes too, so each
affected package needs a new version in that change. `buf breaking` with category `WIRE_JSON`
decides whether the version is major or compatible. A wire-incompatible major needs migration text
and a disposition of at least `facts`.

In the development stage an event package also stays at `1.0.0`, but `make proto-gen` and `make
proto-check` still treat its image as frozen, so an in-place edit of an event package is not yet
possible; the `event-package-development-edit` task in the plan owns that.

G2 records are a new event package. They do not edit the frozen G0 descriptor bytes or the
`FrameResult` message. The [runner page](../impl/current/runner.md) states the packages that exist.

## Historic formats

The development stage holds no historic format, and the gate refuses a `retired_majors` entry
there. Once released, use `retired_majors` for historic majors with no frozen contract. Each entry
states `major`, `status`, `reason` and `migration`; majors must be unique, sorted, and cannot also
have a frozen version. `status` is the disposition: `facts` while a retained record of that major
has a route, such as an amendment that reads it, and `retired` once none needs one. A historic
major is never a view. `migration` is the remedy ss-track gives when it refuses a record of that
major, so write it as what the holder must do. Kept compatibility fixtures are not runtime evidence.
