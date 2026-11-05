# Contract registry

## Task and scope

- Id / capability: `contract-registry` / `data-contracts`
- State: accepted
- Source: plan task, owner request at `3168cbd`, clean tree on `st-04-data-contracts`.
- Plan counts at start: 133 tasks (111 agent, 22 human). Next agent: `decode-policy-reimport`; next
  human: `select-development-workload`.
- Accepted task:

```markdown
#### contract-registry

No format has a definition outside the Python that reads it, so a consumer needs this repository to
read one record.

- Serves: `data-contracts` -- [Contract families](../design/spec.md#171-contract-families)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts list` and `validate` work from an installed wheel over a
  registry of frozen contracts, and `make lint-contracts` runs inside `make ci`.
- Scope boundary: Registry, dialect meta-schema, shared definitions, identity, both fingerprints,
  packaging, and `record/frame-set` end to end as the first contract. No reader changes and no
  change classifier.
- Data and artifact paths: `contracts/`, `src/ss_track/schema/`, `tests/schema/`,
  `docs/guide/authoring-contracts.md`.
- Execution path: Ship root `contracts/` as package data through a setuptools `package-dir` mapping,
  and add `jsonschema` to the runtime dependencies and `uv.lock`. Validate with a strict integer type
  and reuse `canonical_json` for fingerprints. Keep `src/ss_track/schema/` distinct from
  `src/ss_track/contract/`, which holds events and scenarios. Add the authoring guide, and the
  `AGENTS.md` rule that a new interchangeable format adds its contract in the same change.
- Acceptance gates: A real frame set validates with no byte changed, from a wheel installed outside
  the checkout. A standalone validator given only `contracts/` accepts it and refuses an altered copy.
  The meta-schema refuses an open object, `if`, `not`, an untagged union and a property with no
  description. An edited frozen file and a stale fingerprint each fail the build.
- Documentation target: [Current implementation](current.md#areas), new page `current/contracts.md`.
```

- Amendments: none.

## Implementation

Root `contracts/` holds `registry.yaml`, the frozen `record/frame-set` 1.0.0 and `shared/types`
1.0.0, and the two meta-schemas. `src/ss_track/schema/` reads them: `strict.py` is the local
validator, `store.py` the set, `fingerprints.py` the schema walk, `dialect.py` the dialect check,
`check.py` the gate, and `commands.py` the two commands. `make lint-contracts` runs inside `make
ci`. `jsonschema` and `referencing` join the runtime dependencies, because the code imports both
directly. `types-jsonschema` and `setuptools` join the dev extra, the second so a test can build a
wheel with no network. See [Contracts](../current/contracts.md).

Decisions beyond the task text, which the specification now states:

- **A `shared` family.** Section 17.1 had no home for value types that contracts reference by exact
  version. It states no document, so `contracts validate` refuses to use one: with no `type` at its
  root it would call any file valid, which a test caught.
- **`file_sha256` beside the two fingerprints.** A fingerprint ignores formatting by design, and a
  frozen file is never edited at all. The hash finds the edit, and the fingerprints say what kind.
- **`contracts validate` checks a record's seal.** A schema cannot, so a record whose content moved
  would otherwise be called valid. `x-rules` states the seal in words, and a test recomputes it from
  those words alone.
- **It reads strict JSON,** refusing a repeated key and `NaN`. Record 0016 dropped a repeated key on
  the read path for its cost per object. A deep check is run on demand and can afford it.
- **`RECORD_INVALID`, named by section 17.4, exists now,** with `CONTRACT_UNKNOWN` and
  `CONTRACT_SET_INVALID`. A declaration that breaks its contract is `MANIFEST_INVALID`, as a reader
  reports it.
- **The file picks its contract.** With no `--contract`, the file's `kind` and major choose it, from
  the contract files and with no second list in the registry.
- **`$` means the end of the value.** Python's `re` also matches before a final newline, so a hash
  ending in one passed here and failed in the Rust validator. `strict.py` closes that, and the
  dialect refuses `\d`, `\w`, `\s` and `\b`, which differ by engine. Spike results in the design
  covered integers and YAML but not this.
- **`format` is `date` alone.** `date-time` passes everything unless an optional package is
  installed, so it would read as a rule and enforce none.
- **`oneOf` holds inline branches.** The meta-schema can then state that each branch is a closed
  object with a `const`. The rule that all branches share one tag needs two at once, so the gate
  adds it.

Moved, with no behavior change, so that `ss_track.schema` need not import `ss_track.corpus`, which
will validate through it: `corpus/refusal.py` to `ss_track/refusal.py`, `canonical_json`,
`sha256_bytes` and `SEAL_FIELD` to `ss_track/canonical.py`, and the unique-key loader to
`ss_track/strict_yaml.py`. `seal_of` is new and replaces two copies of one expression. These account
for most of the touched test imports. `ss_track.corpus` still exports `CorpusRefusal` and
`RefusalCode`.

Packaging needs more than the task named. A `package-dir` mapping rules out package discovery, so
`packages` is an explicit list, guarded by a test. An editable install finds a mapped package only
through an `__init__.py`, so `contracts/` holds one, and a consumer can ignore it.

`test_sealed_reads.py` fired on the two new JSON readers, as it should. `schema/store.py` reads the
contract set, which holds no record, and `contracts validate` gives a verdict and hands no record
on. Each is a named exemption, the scan still catches any other module, a test holds the second
reason, and section 17.4 states the distinction.

Compatibility: the CLI gains `contracts list` and `contracts validate`, and `RefusalCode` gains
three values. `from ss_track.corpus.refusal import ...` and importing the three moved names from
`ss_track.corpus.sealed` no longer work; nothing outside this repository uses them. `pyproject.toml`
and `uv.lock` changed. No record, hash or reader behavior moved.

Limits: only `record/frame-set` has a contract. `contracts validate` reads JSON and runs no
`x-rules` entry. `make lint-contracts` cannot see a file edited together with its registry entry.
See the handoff.

## Acceptance evidence

One-off scripts were not kept. The wheel and validator runs used a fresh environment outside the
checkout.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A real frame set validates with no byte changed, from a wheel outside the checkout | `test_packaging.py`, building a source distribution and a wheel from it as `uv build` does, and running with the wheel first on the path. One-off: `uv build`, `uv pip install` into a new venv, `ss-track contracts validate` on the kept record | pass: `valid`, `seal_checked: true`, `sha256sum -c` unchanged, `ss_track.__file__` under that venv. Network-free in the test, because `setuptools` is in the dev extra |
| A freshly staged frame set, case lines included | `test_a_staged_record_conforms_to_its_contract_case_lines_included`. One-off: real `import`, `corpus build`, `corpus stage` on a generated clip, then `contracts validate` from the checkout and from the wheel, then `corpus verify` | pass: same hash before and after, exit 0 |
| A standalone validator given only `contracts/` accepts it and refuses an altered copy | `test_standalone.py`: `tests/schema/_standalone.py` under `python -I`, an empty environment and a copied directory, failing if `ss_track` was imported. One-off: `jsonschema-rs`, a Rust implementation sharing no code with the Python one | pass in both. Rust: kept record valid, altered invalid, a hash ending in a newline invalid. Both accept `1.0` as a major, which JSON Schema itself allows, and neither can check a seal |
| The meta-schema refuses an open object, `if`, `not`, an untagged union and a property with no description | `test_dialect.py`: 41 constructs, each at the root and nested in an item, a definition and a tagged branch, and `test_the_meta_schema_alone_refuses_a_union_with_no_tag_in_a_branch` | pass. The meta-schema alone refuses a branch with no tag. Tags that differ across branches, or repeat a value, are refused by the gate, because a schema sees one branch at a time |
| An edited frozen file and a stale fingerprint each fail the build | `test_check.py`, including a formatting-only edit. One-off: `python -m ss_track.schema.check --root` on a copy with `minItems` edited, and on one with a changed registry fingerprint | pass: exit 1 with 2 findings and with 1 finding, each by contract and version |
| `contracts list` and `validate` work from an installed wheel | `test_the_wheel_lists_its_contracts_outside_the_checkout`, and the one-off above | pass |
| `make lint-contracts` runs inside `make ci` | `test_the_gate_runs_inside_ci`, and `make --dry-run ci-checks` | pass |
| Contract and writer agree | `test_agreement.py`: kind, major, both shared patterns, every owner is a capability, every code is documented | pass |
| Tests notice a removed protection | One-off: 44 mutations of the validator, gate, commands, meta-schemas, packaging and Makefile, in a copy of the tree | 44 of 44 caught. The first pass caught 40. The four misses were weak tests, now strengthened: a property named `title`, the meta-schema alone, a missing `file_sha256`, and the import direction |
| Whole gate | `make quality` | pass: exit 0, 1166 passed, 99.20% coverage, 0 contract findings, 0 spec-plan findings, 0 broken links, package built |

Tests found two defects in the first draft, both fixed: a definition with no annotation moved the
`meaning` fingerprint, and `--contract shared/types` called any file valid.

## Audit handoff

Reviewed: the whole diff, every plan task naming a contract or a moved module, and the specification
and design against what was built.

- `AUD-contract-registry-1`: `make lint-contracts` compares a file only with its registry entry, so
  an edit of both passes. Nonblocking. Owner: `contract-evolution-gate`, amended to compare with the
  merge base and to fail that case.
- `AUD-contract-registry-2`: the dialect cannot state positional `frames` tuples in staged hashes or
  the open `details` of the command result. Owner: `corpus-contract-baseline`, amended to widen it
  and to teach the walk each new keyword.
- `AUD-contract-registry-3`: `contracts validate` parses JSON only, and declarations are YAML.
  Owner: `corpus-contract-baseline`, amended.
- `AUD-contract-registry-4`: `record/frame-set` holds `x-references` to contracts that do not exist
  yet. Owner: `corpus-contract-baseline`, amended with a gate. The general check stays with
  `contract-reference-docs`, whose text states it.
- `AUD-contract-registry-5`: `meta/registry.json` cannot yet list a `retired` major with no
  contract. Owner: `corpus-contract-baseline`, amended.
- `AUD-contract-registry-6`: the registry, the gate and the `$id` pattern hold JSON Schema files
  only. Owner: `event-schema-contract`, amended.
- `AUD-contract-registry-7`: `shared/types` and `fields.py` state the same two patterns, held equal
  by a test. Owner: `contract-enforced-readers`, amended to remove both the constants and the test.
- Dropped: `contracts validate` runs no `x-rules`. A record that breaks one needs a deliberate
  reseal, and the code reading the record refuses it, as `corpus verify` does.
- Dropped: a third-party validator accepts `1.0` as an integer. JSON Schema defines it so, and
  section 17.4 already says the local validator is the strict gate.
- Dropped: command output is logged, so `ss-track contracts list | jq` gets nothing on stdout. That
  holds for every command, and `corpus-contract-baseline` freezes the log line as it stands.

## Close or resume

Every gate passed. Next action: none. [Contracts](../current/contracts.md) and the authoring guide
are new, `AGENTS.md` gains the contract rule, and the specification and design are updated. The task
is removed from the plan, and `corpus-contract-baseline`, `annotation-contract` and
`event-schema-contract` lose the dependency. Plan after this change: 132 tasks (110 agent, 22
human). Next agent: `decode-policy-reimport`; next human: `select-development-workload`.
`data-contracts` stays `planned`. Nothing was committed.
