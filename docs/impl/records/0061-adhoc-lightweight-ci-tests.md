# Lightweight CI tests

## Task and scope

- Id / capability: `lightweight-ci-tests` / ad hoc
- State: accepted
- Source: user request; start commit `c89a862`; working tree clean.
- Plan counts at start: 105 agent, 23 human; next agent `corpus-combined-pool`, next human
  `define-locked-test-policy (optional)`.
- Accepted task: Create two test groups so `make ci` runs only lightweight tests with no external
  artifact dependency, and GitHub Actions spends less time on the suite.
- Amendments: none.

## Implementation

The suite is two groups, selected by the `external` marker from `tests/grouping.py`. A test is
external when its module calls `check_contract_set`, `history_findings`, `freeze_contract`,
`freeze_next` or `private_contracts`, when it is a real sibling-release probe, or when it refuses
to start without the optional Croissant package. `make test-light` runs the complement.
`make test-external` runs the external group. `make test` and `make coverage` run both.
`make ci` and `make ci-github` run the lightweight group after the existing checks.

The full suite measured 590.19s. The slow calls were private rechecks and freezes of the shipped
contract set and Git histories of that set, about 6s to 19s each. Those 112 tests are the external
group. The lightweight group finished in 108.49s. `make lint-contracts` still checks the shipped
set once inside `make ci`. The arm64 workflow still runs `make test`, so both groups run on that
architecture. The
[developer tooling](../current/developer-tooling.md#quality-gates) page states the split.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Group sizes | `.venv/bin/pytest --collect-only -q -m external` and `-m "not external"` | 112 external, 2209 lightweight |
| Lightweight group before the record file existed | `.venv/bin/pytest -q -m "not external" --durations=15` | 2208 passed, 1 failed, 112 deselected, 108.49s. The failure was the new documentation link to this record |
| Marker and Make wiring | `.venv/bin/pytest -q tests/quality/test_test_groups.py tests/quality/test_workflows.py` | pass |
| Required project gate | `make ci` | pass: checks green; 2209 passed, 112 deselected, 104.23s in the lightweight group |

## Audit handoff

- Dropped: GitHub's `make ci` jobs no longer execute the external group. That is the requested
  boundary. The shipped contract set is still checked once by `make lint-contracts`, and `make test`
  plus the arm64 job still run both groups. This needs no further task.
- Dropped: a few lightweight tests still take a few seconds (the evolution oracle, the ODCS export,
  and fixed-corpus setup). They do not recheck a private contract copy or need an optional runtime,
  and the lightweight group is under two minutes. A time cutoff would be a different rule. This
  needs no further task.

## Close or resume

The groups and the CI selection are in place. Plan counts stay 105 agent and 23 human, with
`corpus-combined-pool` next in the agent lane and `define-locked-test-policy (optional)` next in
the human lane.
