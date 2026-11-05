# Corpus contract baseline

## Task and scope

- Id / capability: `corpus-contract-baseline` / `data-contracts`
- State: accepted.
- Source: plan task; start commit `82d4950bc4b0ee428f3a17349c56fe586739012b`; clean worktree.
- Plan counts at start: 132 tasks (110 agent, 22 human). Next by priority: agent
  `decode-policy-reimport`; human `select-development-workload`.
- Accepted task:

```markdown
#### corpus-contract-baseline

Every shipped format still has no contract, and some of its values mean nothing outside FFmpeg.

- Serves: `data-contracts` -- [Identity and versions](../design/spec.md#172-identity-and-versions)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Recording, corpus, source manifest, corpus manifest, frame bundle, staged
  hashes, hash comparison and command result each have a frozen contract at their shipped major, and
  `contracts validate` reads a declaration's YAML.
- Scope boundary: Describe formats as the current code writes them, changing no shipped byte and no
  reader's behavior. Split the shared version constants so each format owns its major. Cross-field
  rules go in `x-rules`. FFmpeg color integers gain `x-vocabulary`. Earlier majors are listed `retired`
  with no contract, because no retained record exists, which `contracts/meta/registry.json` does not
  state yet. Corpus 3.0.0 requires source terms, so a schema 3 manifest written before they existed
  stays refused. The dialect widens by what these formats need and no further: positional `frames`
  tuples in staged hashes, and the open `details` of the command result.
- Data and artifact paths: `contracts/declaration/`, `contracts/record/`, `contracts/result/`,
  `tests/schema/`.
- Execution path: Add a session-wide test hook that validates every record any test writes, examples
  per contract, and one tagged branch per transform and label-transform kind. Teach `walk` and both
  fingerprints each keyword the dialect gains. `contracts validate` parses JSON only today, so add a
  `declaration` read through the strict YAML loader.
- Acceptance gates: Every record the suite writes validates, and every `x-references` target of
  `record/frame-set` exists at its pointer. A recipe carrying another transform's
  parameters is refused by the schema alone. Each numeric quantity has `x-unit`, each coded integer
  has `x-vocabulary`, and the result contract's `code` enum equals `RefusalCode`, so a test fails when
  either changes alone. A format the dialect cannot state stays `draft` with its reason.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.
```

- Amendments: The user explicitly selected "Allow text-or-number unions and freeze all formats"
  after the capture scalar limitation was identified. This extends the original dialect scope by
  exactly `["string", "number"]` and `["string", "number", "null"]`. All formats must now freeze;
  no capture draft or unresolved frame-set reference is retained.

## Implementation

- Froze the eight requested formats at their shipped majors under `contracts/declaration/`,
  `contracts/record/` and `contracts/result/`. Together with the existing frame-set contract, all
  nine shipped document formats are covered; `shared/types` remains unchanged.
- Added closed transform and label-transform branches, exact staged-frame tuples, cross-field
  `x-rules`, numeric units, FFmpeg vocabularies and complete frame-set reference targets. The result
  code enum matches `RefusalCode`; only its root `details` object is open.
- Extended the dialect and fingerprints for fixed `prefixItems`, boolean `items`, the open result
  boundary and the user-approved exact capture scalar unions. Arbitrary unions remain refused.
- Added explicit retired-major metadata and listing output without inventing historic contracts.
  Kept historic fixtures remain test evidence, not accepted runtime records. Corpus major 3 requires
  source terms even though an earlier writer omitted them under that same integer.
- Separated declaration and record version constants without changing their values. Corpus readers,
  source terms, decoded bytes, seals and algorithm revisions retain their existing behavior.
- `schema/_documents.py` provides private strict JSON/YAML parsing for explicit validation. It uses
  `UniqueKeyLoader`, normalizes calendar dates, rejects repeated keys and non-JSON values, and catches
  numeric overflow. The static read-boundary test permits only the validation command to import it.
  Result validation selects its own latest contract rather than an embedded record's major.
- Added a session-wide production-write and CLI-output hook, examples for every frozen document,
  standalone standard-validator cases, dialect/fingerprint regressions, and a generated-case
  end-to-end test. Archived retired source records are checked against their original content and
  seal; newly emitted source records must pass the current contract.
- No dependency, lockfile or environment changes. Current behavior is documented in
  [Contracts](../current/contracts.md), with authoring guidance and specification updates.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Required repository gate | `make ci` | Pass: 1,225 tests; format, lint, typing, complexity, shell, links, spec-plan and contracts pass |
| Every current writer conforms | `tests/conftest.py`, `tests/corpus/test_contract_outputs.py` | Pass: production writes and CLI records checked; all seven generated transforms exercised |
| Kept bytes and source terms | `tests/schema/test_baseline.py` | Pass: current-major historic examples validate unchanged; pre-terms corpus 3 refuses |
| Frame-set references | `test_every_frame_set_reference_resolves_at_its_pointer` | Pass: every annotated target exists at its exact schema pointer |
| Tagged recipes and labels | `test_schema_alone_refuses_parameters_from_another_transform`, `test_label_transform_kinds_are_tagged` | Pass: incompatible parameters refuse through the schema alone |
| Units, vocabularies and codes | `test_all_numeric_quantities_and_color_codes_are_annotated`, `test_corpus_declaration_major_and_refusal_codes_agree` | Pass: quantities annotated and refusal-code sets equal |
| YAML and scalar extension | `tests/schema/test_yaml_documents.py`, `tests/schema/test_extensions.py` | Pass: dates, descriptions, numbers and stored nulls retain their meaning; invalid values refuse |
| Independent consumer and packaging | `tests/schema/test_standalone.py`, `tests/schema/test_packaging.py` | Pass: standard validator accepts every record example and rejects a malformed tuple; wheel includes the set |
| Actual fixed-corpus run | `make fixed-corpus-sources RUN_ID=contract-baseline`; `make fixed-corpus-stage RUN_ID=contract-baseline` | Pass: generated sources imported, built, staged and verified on this host |
| Actual output validation | `$DATA_DIR/run/contract-baseline/contract-validation.log` | Pass: 153 sealed records and 72 recording/corpus YAML declarations validate; no drafts |
| Documentation | `make lint-md`, `make lint-doc-links`, `make lint-spec-plan` | Pass |

The fixed run retains sources, imported records and frames under `DATA_DIR`. Its pipeline log and
self-comparison are in `$DATA_DIR/run/contract-baseline/`; the frame-set seal is
`43b241fcf5ed3d2258e3a41f19134578f7561b0da8b4f782f4949613b7713af0`. The self-comparison exercises
comparison output only and makes no cross-host reproducibility claim. Final CI evidence is retained
as `$DATA_DIR/run/contract-baseline/ci.log`.

To repeat the explicit checks, run `ss-track contracts validate --file <record>` for each manifest,
frame-set and run record, and add `--contract declaration/recording` or `--contract declaration/corpus`
for the declarations listed in `contract-validation.log`. `recordings.yaml` is the test helper's list
of declaration filenames, not itself a recording declaration.

## Audit handoff

- AUD-corpus-contract-baseline-1: Capture text-or-number values could not be represented under the
  original dialect scope. Fixed here after explicit user authorization; both contracts now freeze
  and all references resolve. Dropped as completed, with no residual capture task.
- AUD-corpus-contract-baseline-2: Schema drafts initially misstated missing timestamp quality,
  repeated-frame content indexes and absent split summaries. The writer hook caught each mismatch;
  corrected the contracts without changing output. Dropped as completed.
- AUD-corpus-contract-baseline-3: The deep parser could preserve JSON exponent overflow as infinity,
  and a result could select a version from its embedded comparison. Fixed with regression cases.
  Dropped as completed.
- AUD-corpus-contract-baseline-4: Evolution must classify tuple positions, capture scalar unions and
  open result details. Owned by the amended `contract-evolution-gate` task, which names each construct.
- AUD-corpus-contract-baseline-5: Corpus readers still enforce structure manually, and `x-rules`
  remain descriptive rather than executable schema checks. Owned by `contract-enforced-readers`,
  whose text retains cross-field rules in code and now reuses the strict parser. This is the declared
  baseline boundary, not a hidden validation claim.

Reviewed schema/writer agreement, unchanged seals and algorithms, read-boundary isolation,
standalone validation, packaging, historic-major dispositions, plan dependencies and documentation.
No new capability or remaining baseline defect was identified. No service, port or external resource
was started; test/run processes have exited. Runtime evidence is retained.

## Close or resume

All required gates passed. The task is removed from the forward-only plan, its dependency is removed
from `contract-evolution-gate`, and that task now states the new dialect constructs it must classify.
The current page and records index link this record. The capability remains `planned` because its
other tasks remain open.

Plan counts after: 131 tasks (109 agent, 22 human), down from 132 (110 agent, 22 human). Next by
priority remains `decode-policy-reimport` in the Agent lane and `select-development-workload` in the
Human lane; `contract-evolution-gate` is the next task in the data-contracts group.
