# Contract evolution gate

## Task and scope

- Id / capability: `contract-evolution-gate` / `data-contracts`
- State: active.
- Source: plan task; start commit `18e711777a56c98d172501dcb71f60546bd92dcc`;
  working tree clean.
- Plan counts at start: 131 open tasks (109 agent, 22 human); next agent by priority:
  `decode-policy-reimport (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### contract-evolution-gate

A format can change only by a new integer that refuses every earlier record, and nothing notices a
changed unit.

- Serves: `data-contracts` -- [Compatibility rules](../design/spec.md#173-compatibility-rules)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts diff` names each change and its class, `freeze` refuses a
  wrong bump and writes the change-log entry, and CI refuses an unreviewed change.
- Scope boundary: JSON Schema contracts. The protobuf gate belongs to `event-schema-contract`.
- Data and artifact paths: `src/ss_track/schema/`, `contracts/`, `tests/schema/`.
- Execution path: Classify by walking both versions through nested objects, array items, fixed tuple
  positions, `$ref` targets and tagged branches, including capture scalar unions and the open
  command-result `details` boundary.
  Name each change by JSON pointer. Keep `jsoncompat` pinned in the dev
  extra as an independent oracle, never as the authority. Add the hash-stability test: writer output
  for input using no new feature validates against the previous frozen minor. `make lint-contracts`
  compares a frozen file only with its registry entry, so compare both with the frozen set of the merge
  base, and give the CI checkout the history that needs. `freeze` replaces copying pins by hand.
- Acceptance gates: Table-driven fixtures pass every row of spec section 17.3, each at a nested path
  and inside a tagged branch. A bump that is too small fails, and a disagreement with the oracle fails.
  Replaying the kept historic records classifies all five real bumps as major. A frozen file edited
  together with its registry entry fails. A new field written as
  `null` fails hash stability, as does a writer adding a key under an unchanged version, which is how
  source terms entered schema 3 corpus manifests. A major with no migration text or no disposition
  fails to freeze.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.
```

- Amendments: none.

## Implementation

- `schema/evolution.py` and `_change_rules.py` compare the restricted dialect at JSON pointers,
  including reference targets, recursion, tagged branches, tuples, scalar unions and open details.
  Semantic annotations remain policy, independent of the structural oracle. Unknown pattern
  relationships conservatively require a major; literal and single-class inclusions have proofs.
- `schema/versioning.py` enforces minimum bumps and every previous minor of the candidate major.
  `schema/freeze.py` validates a scratch set before creating schema bytes and generated pins.
  `_publishing.py` locks the directory, refuses a stale registry snapshot or conflicting candidate,
  preserves registry permissions, and rolls back a new schema if publication fails.
- `schema/history.py` compares frozen files and complete version entries with both the merge base
  and `HEAD`, and recalculates transitions entered by hand. The Make gate requires full history;
  GitHub CI provides the PR base SHA or push before SHA and `fetch-depth: 0`.
- CLI parsing stays in `cli.py`. `contracts diff` and `contracts freeze` produce contracted JSON.
  The implementation itself froze `result/command` 1.1.0 for those outputs and optional predecessor
  dispositions; the 1.0.0 bytes and all other frozen versions are unchanged. No corpus record or
  runtime refusal code changes. A major requires migration text and a predecessor disposition.
- `strict_json.py` shares duplicate-key, constant and overflow hooks without exposing a new record
  parser. Registry parsing stays in `schema/store.py`; the sealed-read architecture gate is unchanged.
- `jsoncompat==0.5.0` is pinned only in the dev extra, with `uv.lock` updated. There is no runtime
  dependency on it. The oracle compares every real frozen transition and errors on disagreement.
- Section 17.3 now states the open-object boundary and conservative pattern policy, and corrects
  the claim that schema validity alone proves unchanged bytes. Producer replay also compares
  canonical bytes and seals. The authoring guide describes the implemented commands and recovery.
- Current behavior and verification are in [Contracts](../current/contracts.md#evolution), with
  developer tooling and product-core descriptions updated. Disposition consumption remains in
  `record-read-window`; freezing supplies metadata and does not implement views or migrate records.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Compatibility table and oracle | `tests/schema/test_evolution.py` | Pass: nested and tagged table rows, every actual frozen transition, and explicit errors on the two known oracle disagreements |
| References and containers | `tests/schema/test_evolution_references.py` and container fixtures in `test_evolution.py` | Pass: external/local references, recursive shapes, aliases, arrays, tuples, tag order, scalar identity and open details |
| Freeze policy and publication | `tests/schema/test_freeze.py` | Pass: wrong bumps, missing migration/disposition, strict JSON, dangling references, initial owner, CLI results, conflict preservation, stale snapshots, rollback and permissions |
| Historic changes | `tests/schema/test_historic_evolution.py` | Pass: all five real bumps require major based on observed shapes, not stamps; same-major source-terms addition violates the previous closed shape |
| Hash stability | `tests/schema/test_hash_stability.py` | Pass: real frame-set producer replay, existing CLI output under previous minor, null/default additions, unannounced keys and changed values |
| History immutability | `tests/schema/test_history.py` | Pass: working and committed file-plus-pin edits, deletion, manual wrong bump, missing refs, shallow checkout and CI wiring |
| CLI smoke run | `$DATA_DIR/run/contract-evolution-gate/cli-smoke.log` | Pass: actual `diff`, `freeze`, and Git-free set validation against a disposable copy; scratch copy removed |
| Required gate | `make ci` | Final run pending; preceding full run passed |
| Coverage and extended checks | `UV_CACHE_DIR="$DATA_DIR/cache/uv" UV_OFFLINE=true make quality` after `sst_load_env` | Pass: 1,360 tests, 98.02% branch-aware coverage, all CI checks, Markdown, source and wheel build; `$DATA_DIR/run/contract-evolution-gate/quality.log` |
| Package build recovery | `UV_CACHE_DIR="$PWD/.data/cache/uv" UV_OFFLINE=true make build` | Initial online build failed on sandbox DNS; offline build and final full quality run passed using cached backend. Packaging tests also inspect an isolated wheel |
| Documentation | `make lint-md`, `make lint-doc-links`, `make lint-spec-plan` | Pass; links, task structure, registry order and Markdown checked |

The final coverage rerun includes the publication regressions and the reference-alias fix.
The task's table uses pattern removal for the oracle's
relaxation agreement case; the provable changed-pattern case explicitly proves disagreement refuses.
There is no skip, expected failure or exemption for an actual frozen transition.

## Audit handoff

- `AUD-contract-evolution-gate-1`: nonblocking for the delivered transition. `jsoncompat` 0.5.0
  returns incompatible for `^[ab]+$` to `^[abc]+$`, and compatible for adding an optional string
  constraint inside an open object. The latter rejects the previously legal numeric value, so the
  repository classifier must stay major. Tests retain both as disagreement errors, and actual
  frozen transitions cannot pass CI on such disagreement. General pattern rewrites remain
  conservatively major, and the independent oracle's reference expansion still needs recursive
  coverage. Owner: the new `contract-oracle-coverage (optional)` task states all three cases,
  independent validation, possible replacement, and the valid negative result.
- Completion review covered the dialect walk, change-log/registry compatibility, history baselines,
  strict parsing, read-gate import direction, publication failure paths, writer bytes, oracle
  direction and the new command-result minor. The raw parser duplication, open-object rule,
  boolean/numeric enum identity, publication permissions and identical fragment names across distinct
  reference resources were fixed in this change.
  No additional task is needed for them.
- A process killed between publishing the schema and registry may leave an unregistered candidate.
  Dropped as a separate follow-up: the checker fails closed, no old frozen byte is changed, and
  retrying freeze registers the same candidate. This is documented recovery, not lost evidence.
- Runtime view implementation remains owned by `record-read-window`, whose execution text now
  consumes the existing `change.disposition`; it no longer schedules adding that metadata again.

## Close or resume

Final required and documentation checks are pending. The delivered task is removed from the plan,
its three explicit downstream dependencies are cleared, and the oracle refinement has an owner.
Plan counts after routing remain 131 open tasks (109 agent, 22 human): one task removed and one
optional task added. The next tasks by lane priority remain `decode-policy-reimport (optional)`
and `select-development-workload`; `contract-enforced-readers` is the next required data-contracts
task. The capability remains `planned` because reader and read-window work is open.
