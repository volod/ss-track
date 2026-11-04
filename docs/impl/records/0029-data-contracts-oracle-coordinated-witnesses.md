# Coordinated witnesses for the compatibility oracle

## Task and scope

- Id / capability: `oracle-coordinated-witnesses` / `data-contracts`
- State: accepted
- Source: plan task; starting commit `b055f1c`; working tree clean.
- Plan counts at start: 126 open tasks (104 agent, 22 human); next agent
  `decode-policy-reimport (optional)`, next human `select-development-workload`.
- Accepted task:

```markdown
#### oracle-coordinated-witnesses (optional)

The oracle's own witness search changes one position of the smallest seeds, so a break that needs two
values changed together goes unfound whenever jsoncompat wrongly calls it compatible.

- Serves: `data-contracts` -- [Compatibility rules](../design/spec.md#173-compatibility-rules)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A wrong compatible verdict from jsoncompat is refuted for breaks that need
  two coordinated values, such as a value that is only reachable once an optional sibling is set.
- Scope boundary: `tests/schema/_witness.py` only. The search stays deterministic and bounded, and
  every witness is still confirmed by `StrictValidator`.
- Data and artifact paths: `tests/schema/`.
- Execution path: Build a table of breaks that need two coordinated values and show which ones the
  single-position search misses with `analyze_compat` forced to `compatible`. Then extend the
  search to pairs of positions and to seeds for each combination of `oneOf` branches, with a bound
  on trials.
- Acceptance gates: Every break in the table is refuted with a confirmed, shrunk witness under a
  forced compatible verdict. `test_every_real_transition_agrees_with_the_oracle` stays under two
  seconds. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/contracts.md`.
```

- Amendments: the search stays in the test oracle and is still entered only through
  `tests/schema/_witness.py`. The builder and the node walk moved to `_witness_build.py` and
  `_witness_node.py` because one module was about 700 lines, past the line guide. The oracle's
  call is unchanged. The `_oracle.py` docstring was updated so it no longer describes a
  one-position search.

## Implementation

`search_one_position` is the previous search: one shared branch index, then one position, including
every property name. The table forces `analyze_compat` to `compatible` and shows that this returns
no witness. `search` then refutes the same pairs. `verdict` still confirms with `StrictValidator`
and shrinks.

Seeds are one minimal instance per `oneOf` combination actually walked, schema order, at most 32,
deduplicated. The mixed-branch witness is that seed. After the seeds, one position is tried, then
pairs: two missing properties of one object, then two scalars under one parent, then two scalars
under different parents. A position is only given an edge of its own node, or a value the new
schema or a pattern proof introduced. A value the old node rejects (const, enum, declared type,
numeric bound, string length) is not passed to the validator. An open property with no schema
still tries every boundary value, so `{"value": 0}` is unchanged.

The pair phase stops after 32 validator calls. At 256 the frozen-transition test took 2.52s,
almost all of it revalidating documents that stayed valid. At 32 it took 0.90s. Every table row
is found by the ninth call. Single-position trials stop at 4096. Current state:
[contracts](../current/contracts.md#independent-oracle).

No CLI, env, dependency, or frozen file changed.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| One position misses each row | `tests/schema/test_witness.py` with `analyze_compat` forced to `compatible` | pass: six rows, `search_one_position` is `NONE` |
| Shrunk confirmed witness | same test, `verdict(...).witness` | pass: `{"count": 0, "unit": "px"}`, `{"x": 1, "y": 1}`, `{"item": {"n": 0}, "ready": true}`, `[1, 1]`, mixed `oneOf` tags, `{"left": {"n": 1}, "right": {"n": 1}}` |
| Trial bound | `test_search_stops_within_the_trial_bound` | pass: calls stay within `MAX_TRIALS + PAIR_BUDGET` |
| Frozen transitions under two seconds | `pytest tests/schema/test_evolution.py::test_every_real_transition_agrees_with_the_oracle --durations=3` | pass: 0.90s call |
| `make ci` | `make ci` | pass: 1595 tests |

## Audit handoff

Reviewed the phase order, that local rejection only drops values the old node cannot accept, that
`StrictValidator` still confirms every witness, the six-row table against the caps, and the frozen
transitions at the pair cap that meets the time gate.

- `AUD-oracle-coordinated-witnesses-1`, nonblocking, dropped: combinations past 32 seeds and pairs
  past 32 validator calls stay unsearched, so a later coordinated break can still hide behind a
  wrong compatible verdict. This is the bound the task required. The table is inside it. A pair
  cap of 256 made the frozen-transition test take 2.52s.
- `AUD-oracle-coordinated-witnesses-2`, nonblocking, dropped: `_witness.py` is 303 lines and
  `_witness_node.py` is 281, over the soft 250-line aim. Each file is one step of this search.
  Another split would separate `search` from the phases it runs in order. `make quality-report`
  already lists longer test modules.

## Close or resume

Every gate passed. The task left the plan; no task named it as a dependency. The audit task in
the group remains. Plan counts after: 125 open tasks (103 agent, 22 human); next agent
`decode-policy-reimport (optional)`, next human `select-development-workload`. `data-contracts`
stays `planned`.
