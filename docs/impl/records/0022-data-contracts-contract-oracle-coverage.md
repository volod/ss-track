# Contract oracle coverage

## Task and scope

- Id / capability: `contract-oracle-coverage` / `data-contracts`
- State: accepted.
- Source: plan task; start commit `26527b5`; working tree clean.
- Plan counts at start: 129 open tasks (107 agent, 22 human); next agent by priority:
  `decode-policy-reimport (optional)`; next human: `select-development-workload`.
- Accepted task:

```markdown
#### contract-oracle-coverage (optional)

An independent structural oracle must distinguish real compatibility breaks from gaps in its own
reasoning, without overriding the repository's semantic rules.

- Serves: `data-contracts` -- [Compatibility rules](../design/spec.md#173-compatibility-rules)
- Agent status: CLEAR
- Milestone: M1
- Research: yes
- Dependencies: none.
- User-visible outcome: Provable pattern relaxations and open-object constraints receive reliable
  independent compatibility checks, with disagreements still failing CI.
- Scope boundary: Improve or replace the development oracle and extend local pattern proofs where
  justified. No runtime oracle dependency and no automatic override of a semantic major.
- Data and artifact paths: `tests/schema/`, `src/ss_track/schema/`, `pyproject.toml`, `uv.lock`.
- Execution path: Exercise pattern widening from `^[ab]+$` to `^[abc]+$`, an optional string
  constraint added inside open command-result `details`, and recursive references. Investigate a
  corrected pinned oracle or an independently verified alternative; preserve concrete witnesses.
- Acceptance gates: The oracle accepts the proven relaxation, refuses the open-object constraint
  with its numeric counterexample, terminates on recursive references and agrees on the existing
  structural table. All actual frozen transitions remain checked. A valid negative result retains
  fail-closed behavior and explicitly states the unsupported relationships; `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.
```

- Amendments: none to the task block. After review the owner decided three handoff items in this
  change: keep strict agreement in both directions, and ban `.` and negated classes in the
  dialect. For the jsoncompat defect, the owner first asked for an upstream report and a required
  fix task, then dropped the upstream part entirely, because the project does not control
  third-party packages: the workaround is the fix, and a test signals when it can be removed. The
  owner also changed the project rules so that a bug or an improvement is never dropped and gets a
  plan task, and a third-party bug is fixed here behind a workaround (`AGENTS.md`, section
  Findings).

## Implementation

Research result: no corrected oracle exists to pin. PyPI lists `jsoncompat` 0.5.0 as the newest
release (checked 2026-11-03), so the pin stays, and the tests wrap it in an independently verified
oracle. Its typed `analyze_compat` returns compatible, incompatible with a counterexample, or
unknown. The old helper used `check_compat`, which folds unknown into "incompatible". That hid the
real behavior: unknown for `^[ab]+$` to `^[abc]+$` and for a raised `minimum`, and a wrong
compatible verdict for an optional constraint inside an open object.

- `tests/schema/_oracle.py`: strips meaning keywords, inlines references with `_Expander` and keeps
  a recursive target once under `$defs`, so recursion terminates; the old inliner recursed forever.
  Two sound rewrites at aligned positions: an explicitly open old object states each added property
  as any JSON value (an equivalence), and a new pattern the automaton proves admits the old one
  takes the old pattern (a narrowing, so compatibility still holds for the original). A
  counterexample counts only after `StrictValidator` accepts it under the original old schema and
  refuses it under the new, and it is then shrunk. `require_oracle_agreement` fails on disagreement
  in either direction and names the witness or proof. `Undecided` covers unread syntax, an unknown
  verdict with no witness, and an unconfirmed counterexample.
- `tests/schema/_pattern_reader.py` and `tests/schema/_automaton.py`: Thompson automata over the
  ASCII subset, with a breadth-first product walk that proves inclusion or returns the shortest
  breaking string, plus `shortest` for instance building.
- `tests/schema/_witness.py`: deterministic seeds (the smallest instance per `oneOf` choice) varied
  by boundary values and property insertion. It refutes jsoncompat's unknown verdicts and checks
  its compatible ones. jsoncompat's own generator is random and unseeded, so it was not used.
- `src/ss_track/schema/_patterns.py` (local pattern proofs, extended): with the oracle exact on
  patterns, the old single-class proof would have made every non-class widening a CI disagreement,
  including at a voluntary major. The structural proof covers groups, alternatives, optional parts
  and repetition unrolling. `pattern_relaxed` in `_change_rules.py` uses it, and the literal rule is
  kept. Effect: `contracts diff` and `freeze` now give `minor` for these proven relaxations where
  they gave `major`. No frozen file, pin, CLI shape or dependency changed.

Dialect: `pattern_findings` in `schema/dialect.py` refuses any contract pattern outside the syntax
`schema/_patterns.parse` reads. That covers `.` and negated classes, which Python's `re` and
ECMA-262 match differently at line terminators and astral characters. It also covers lookaround,
backreferences, non-ASCII text and top-level alternation, because no change to them can be
classified. Every installed pattern already fits, and `meta/dialect.json` states the rule in its
description. `freeze` runs the same check, so a candidate is refused before publication.

Rejected: putting the automaton in `src` for the classifier, because the oracle would then check
the classifier with its own code. Also rejected: a lenient agreement that accepts a conservative
major, because the task requires disagreements to fail; the remedy is a stronger proof, stated in
the authoring guide. Current state: [contracts](../current/contracts.md#pattern-proofs).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Accepts the proven relaxation | `tests/schema/test_evolution.py::test_pattern_relaxation_is_proven_by_classifier_and_oracle` | pass: proof `^[ab]+$ within ^[abc]+$`; the reverse gives witness `"c"` |
| Refuses the open-object constraint with its numeric counterexample | `test_optional_constraint_inside_open_details_is_breaking`; `test_oracle.py::test_the_search_alone_catches_the_open_object_jsoncompat_passes` | pass: witness `{"details": {"value": 0}}`; the search alone finds `{"value": 0}` |
| Terminates on recursive references | `test_evolution_references.py::test_recursive_shapes_terminate_and_still_compare_fields` | pass: changed field refuted with `{"head": {"value": ""}}`; an added optional field is compatible |
| Agrees on the structural table | `test_evolution.py::test_rule_table_and_independent_oracle` (54 cases, plain and tagged) | pass: includes the raised bound jsoncompat leaves unknown |
| Every frozen transition checked | `test_evolution.py::test_every_real_transition_agrees_with_the_oracle` | pass: `result/command` 1.0.0 to 1.3.0 |
| Disagreement and undecided fail | `tests/schema/test_oracle.py` (unsound classifier, conservative classifier, unknown, unconfirmed, unread pattern) | pass |
| Dialect refuses unread patterns | `tests/schema/test_dialect.py::test_the_dialect_refuses_each_construct_everywhere` (six pattern kinds at every position) | pass; a literal `.` escaped or in a class is accepted |
| Workaround still needed | `test_oracle.py::test_open_object_workaround_is_still_needed` | pass: raw verdict `compatible`, oracle witness found; fails once a pinned release fixes it |
| Local proofs sound | `tests/schema/test_patterns.py` | pass: every structural proof holds under the automaton; on contract patterns they agree exactly |
| `make ci` | `make ci` | pass |
| `make quality` | `make quality` | pass: 1516 tests, coverage 98.09%, Markdown lint, sdist and wheel built |

## Audit handoff

Reviewed: every changed module and test, the soundness argument of each rewrite (the dialect has
only monotone keywords, and tagged `oneOf` branches stay disjoint under narrowing), the agreement
direction, witness confirmation against the original schemas, the docs naming the old limitation,
and the completeness of the structural proof on contract patterns. The audit fixed three defects in
this change, each with a test: a class read `.` and `$` as metacharacters; the open-object rewrite
added `properties` beside a bare `oneOf`, which jsoncompat read as `allOf`; and the proof missed
`^[0-9a-f]{64}$` within the identifier pattern, now proven by unrolling.

- `AUD-contract-oracle-coverage-1`, nonblocking, fixed in this change: the dialect refused `\d`
  because engines read it differently, but allowed `.` and negated classes, which also differ and
  which neither proof reads. The dialect now refuses every pattern outside the proven syntax.
- `AUD-contract-oracle-coverage-2`, nonblocking improvement: a true inclusion of another shape, such
  as `^(ab)*$` within `^a*(ba)*b*$`, stays conservatively major, and the oracle reports it as a
  disagreement, which fails CI as the owner decided. Owner: `pattern-reshaped-inclusion (optional)`.
- `AUD-contract-oracle-coverage-3`, nonblocking improvement: the witness search changes one
  position of the smallest seeds, so a two-value break can go unfound behind a wrong jsoncompat
  compatible verdict. Owner: `oracle-coordinated-witnesses (optional)`.
- `AUD-contract-oracle-coverage-4`, nonblocking, fixed in this change: `jsoncompat` 0.5.0 calls an
  optional constraint added inside an open object compatible. `_declare_open` and the witness
  search fix it here, and `test_open_object_workaround_is_still_needed` fails once a pinned release
  fixes it. Dropped as a plan item by the owner: no upstream report, because the project does not
  control third-party packages.

## Close or resume

Every gate passed. The task left the plan; no task depended on it. The specification (section
17.3 and the dialect paragraph), `docs/design/data-contracts.md`, the authoring guide,
`contracts/meta/dialect.json` and `current/contracts.md` describe the oracle, the proofs and the
pattern syntax. Plan counts after: 130 open tasks (108 agent, 22 human); next agent
`decode-policy-reimport (optional)`, next human `select-development-workload`. The two added
optional tasks carry the improvement items above. `data-contracts` stays `planned`, with open work.
