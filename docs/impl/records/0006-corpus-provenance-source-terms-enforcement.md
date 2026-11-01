# Source terms enforcement

## Task and scope

- Id / capability: `source-terms-enforcement` / `corpus-provenance`
- State: accepted.
- Source: plan task; starting commit `d6b704d12326bb762ef43aca67adea1ba1760fda`; clean worktree.
- Plan counts at start: 89 tasks (68 agent, 21 human). Next agent: source-terms-enforcement;
  next human: select-development-workload.
- Accepted task:

```markdown
#### source-terms-enforcement

Recorded terms protect nothing while an expired source, or one that forbids derived frames, passes
every check.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A recording declares when its retention ends and whether derived frames are
  permitted, and a source outside those terms cannot enter or stay in a corpus.
- Scope boundary: Recording schema 2 with `rights.retain_until` and `rights.derived_frames`, neither
  with a default. `holder` and `basis` stay uncompared, and refusal deletes nothing.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add both fields to `declaration.py`, a retention check shared by build, stage and
  verify with an injected date so fixtures stay deterministic, and the derived-frame rule in
  `grouping.py`.
- Acceptance gates: An expired source is `RETENTION_EXPIRED` at build, stage and verify, one day
  either side of its date. A generated case of a source that forbids derived frames is
  `RIGHTS_CONFLICT`. A date never enters a sealed record, so a rerun stays byte-identical.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

Recording declarations and source manifests use schema 2, with required `retain_until` and
`derived_frames`. The deadline is an inclusive ISO date or explicit null; derivation permission is
a boolean. `fields.py` validates these values, and quoted/unquoted YAML dates normalize identically.
`holder`, `basis` and descriptive `retention` remain recorded terms without comparison.

`terms.py` supplies the shared retention rule. Build, stage and verify each capture one UTC day or
accept keyword-only `today` for deterministic evaluation. The evaluation day never enters sealed
records. Stage and verify check every stream before touching bundles, including existing bundles.
Refusal deletes nothing. `grouping.py` refuses recipes whose parent forbids derivation before corpus
publication; ordinary stream staging remains allowed.

Existing source records require schema 2. Legacy corpora missing explicit terms refuse rather than
silently receiving defaults. Migration is operator-managed import and a new corpus version, described
in the [current corpus contract](../current/corpus.md). Corpus and bundle schemas remain unchanged.
No dependency, lockfile, environment-variable or CLI-option changes were needed. The builder remains
one cohesive module at 268 lines, slightly above the approximate size target.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Retention boundaries | `tests/corpus/test_source_terms.py::test_retention_boundary_at_every_entrypoint` | Pass: build, stage and verify before/on/after the deadline |
| Refusal before publication | `test_expired_source_never_publishes_a_corpus` | Pass: no corpus is written and source evidence remains |
| Derivation permission | `test_derivation_permission_controls_generated_cases_only` | Pass: forbidden case is `RIGHTS_CONFLICT`; ordinary staging and permitted cases succeed |
| Stable evidence | Boundary test plus `test_quoted_and_yaml_dates_seal_identically` | Pass: all stored bytes unchanged across valid dates and after refusals |
| Strict schema and migration | Invalid/missing terms and legacy-record tests in `test_source_terms.py` | Pass: no defaults or implicit permission |
| UTC evaluation | `test_default_evaluation_day_is_utc` | Pass with an injected clock |
| Required gate | `make ci` | Pass: 473 tests, formatting, lint, typing, complexity, shell, links and plan integrity |
| Coverage | Coverage stage of `make quality` | Pass: 473 tests; 98.77%, above the 90% floor |
| Markdown | `make lint-md` | Pass after fixing one overlong documentation line |
| Package | `make build` | Pass: wheel and source distribution; cache access required sandbox escalation |

`make quality` initially stopped at the Markdown line-length finding. Its remaining stages were
rerun individually after the fix. The package build's first attempt encountered the read-only user
cache; the approved retry completed. No external footage or network-backed test was required.

## Audit handoff

- `AUD-source-terms-enforcement-1`: Verification checks retention from pinned corpus terms but still
  does not re-read current source records. This pre-existing limitation is blocking for withdrawn-rights
  verification, not for this task. Owner: `corpus-verify-rights` in the
  [plan](../plan.md), whose scope explicitly requires re-reading source records
  and detecting changed rights without re-hashing media.
- Legacy record migration is intentionally explicit. Automatic migration is dropped because neither
  a retention deadline nor derivation permission can be inferred safely from old descriptive terms.
- Reviewed schema validation, date boundaries, preflight placement, unchanged reruns, deletion behavior,
  source identity and generated-case membership. No additional work identified.

## Close or resume

All required gates passed. Current corpus documentation and the records index link this record;
the specification now makes the date, null and ordinary-decoding boundaries explicit. Removed only
`source-terms-enforcement` and cleared its two completed dependencies. Remaining plan: 88 tasks
(67 agent, 21 human); next agent is `corpus-verify-rights`, next human is
`select-development-workload`. `corpus-provenance` remains planned because its other tasks remain.
No service, port or external resource was started. Build outputs and tool evidence are retained;
no temporary implementation scaffold remains.
