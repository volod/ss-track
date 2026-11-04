# Pattern inclusion whose shape changed

## Task and scope

- Id / capability: `pattern-reshaped-inclusion` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `a740376`; working tree clean.
- Plan counts at start: 127 open tasks (105 agent, 22 human); next agent
  `decode-policy-reimport (optional)`, next human `select-development-workload`.
- Accepted task:

```markdown
#### pattern-reshaped-inclusion (optional)

The classifier requires a major for a true pattern inclusion whose shape changed, so that relaxation
cannot ship as a minor, and the independent oracle reports the pair as a disagreement.

- Serves: `data-contracts` -- [Compatibility rules](../design/spec.md#173-compatibility-rules)
- Agent status: CLEAR
- Milestone: M1
- Research: yes
- Dependencies: none.
- User-visible outcome: `contracts diff` gives `minor` for a proven relaxation of another shape,
  such as `^(ab)*$` to `^a*(ba)*b*$`, and the oracle agrees.
- Scope boundary: Proofs over the dialect's pattern syntax in `schema/_patterns.py`. The classifier
  shares no code with `tests/schema/_automaton.py`, gains no runtime dependency, and keeps an
  unproven relationship major.
- Data and artifact paths: `src/ss_track/schema/`, `tests/schema/`.
- Execution path: Today that pair fails `require_oracle_agreement` with `classifier backward=False,
  oracle=True`, held by `test_unproven_pattern_relationship_requires_a_major_and_the_oracle_says_so`.
  Evaluate a decision procedure for the classifier, such as Brzozowski derivatives, written apart
  from the test automaton so the oracle still checks it with different code. Measure its cost on the
  contract patterns and on a generated table of reshaped pairs.
- Acceptance gates: The reshaped pairs are minor and agree with the oracle, every pair the
  structural proof decides keeps its verdict, and the gate's run time on the installed set does not
  grow measurably. A valid negative result keeps the conservative major and names the shapes left
  unproven. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.
```

- Amendments: none. The derivative walk lives beside the structural proof, in
  `schema/_derivatives.py` and `schema/_derivative_expr.py`, because one file would pass the line
  guide. The classifier still enters through `pattern_relaxed`.

## Implementation

`pattern_relaxed` still asks `covers` first. When that reading does not prove inclusion, and both
patterns are inside the dialect, `decide` walks Brzozowski derivatives. A character class is one
symbol for every character with the same membership, so `[a-z]` is not twenty-six steps. Union is
stored as a set, a star of a star stays one star, and `(r?){m,n}` is `r{0,n}` when `r` cannot be
empty. The walk proves inclusion only when it finishes without a string the old pattern accepts and
the new one rejects. At 8192 pairs it stops and the relationship stays major.

The structural proof is unchanged, including `^(ab)*$` against `^a*(ba)*b*$`, which `covers` still
rejects. The derivative walk proves that pair, so `contracts diff` reports `minor` and the oracle
agrees. The walk shares no code with `tests/schema/_automaton.py` and adds no dependency. Patterns
the dialect does not read stay unproven. A literal old value can still match a pattern outside that
syntax, as `^ab$` does inside `^a.$`.

No installed transition changes a pattern, so the frozen-set gate does not enter the walk. The
shapes left unproven are syntax outside the dialect and any walk that passes 8192 pairs. None of
the contract patterns, the reshaped table, or the 729 generated pairs reached the bound.

Current state: [Pattern proofs](../current/contracts.md#pattern-proofs).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Reshaped pairs are minor and the oracle agrees | `tests/schema/test_evolution.py::test_reshaped_pattern_inclusion_is_a_minor_and_the_oracle_agrees`; `tests/schema/test_patterns.py::test_reshaped_inclusion_is_minor_exactly_when_it_holds` | pass: proof `^(ab)*$ within ^a*(ba)*b*$`. 17 reshaped pairs, 12 inclusions, 0 bounded, peak 14 states, 0.0017s |
| Structural verdicts stay | `tests/schema/test_patterns.py::test_structural_proof_is_sound_against_the_automaton` | pass: `covers` is unchanged on every pair it used to decide. The `^ab$` / `^[a-z]+$` row now records that structure misses it; derivatives prove it, and `decide` agrees with the automaton on every pair, including `^[0-9a-f]{64}$` |
| Installed gate does not grow from this walk | `tests/schema/test_evolution.py::test_every_real_transition_agrees_with_the_oracle` | pass. No frozen transition changes a pattern, so the walk is not on the path. Wall time 127.67s before this change and 132.05s after; the derivative tables themselves are a few milliseconds |
| Cost on contract patterns and the generated table | direct `decide` over `_contract_patterns` and `_generated_patterns` | pass: 3 contract patterns, 5 non-structural pairs, 0.0031s, peak 132 states, none bounded. 729 generated pairs, 0.0340s, peak 11 states, none bounded. The test bound is 1s |
| Unproven stays major | `test_an_unfinished_walk_does_not_relax_a_pattern`; `test_syntax_outside_the_subset_is_unproven_by_both` | pass: a walk limited to 1 pair does not relax `^(ab)*$` to `^a*(ba)*b*$`; syntax outside the subset stays unproven |
| `make ci` | `make ci` | pass: 1588 tests, format, lint, typing, complexity, shell lint, doc links, spec-plan integrity, and frozen contracts |

## Audit handoff

Reviewed the derivative rules, the smart constructors, the state bound, and agreement with the
independent automaton on the structural table, the reshaped table, the contract patterns, and 729
generated pairs, plus string membership against `re` through length 4.

`none identified` beyond the following, each dropped:

- Repeating the empty language, and a derivative of a repetition whose upper bound is already zero,
  are not produced by the parser. The guards stay so the algebra remains total. No product gap.
- The oracle's confirmed witness for `^(ab)*$` against `^(ba)*$` is `abababab`. Deleting one
  character leaves a string the old pattern rejects, so the existing shrink stops. The verdict is
  still major. Shortening that string would not change the classification.

## Close or resume

Every gate passed. The task left the plan; no task named it as a dependency. The specification
(section 17.3), the authoring guide, and `current/contracts.md` describe both proofs and the bound.
Plan counts after: 126 open tasks (104 agent, 22 human); next agent
`decode-policy-reimport (optional)`, next human `select-development-workload`. `data-contracts`
stays `planned`, with open work.
