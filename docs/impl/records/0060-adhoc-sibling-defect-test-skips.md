# Sibling defect test skips

## Task and scope

- Id / capability: `sibling-defect-test-skips` / `self-supervised-corpus`
- State: accepted
- Source: user request; start commit `d8bd040`; existing acquisition implementation changes remain
  in the working tree and are unrelated to this task.
- Plan counts at start: 105 agent, 23 human; next agent `corpus-combined-pool`, next human
  `define-locked-test-policy (optional)`.
- Accepted task: Investigate the seven skipped tests on this development host; make the tests run
  or remove unusable tests, preserving meaningful regression coverage.
- Amendments: none.

## Implementation

The seven skipped tests are real-release defect probes gated by `SST_PERCEPTION_PYTHON`, not CUDA
checks. The pinned ss-perception and dependencies were reconstructed from the local uv cache into
`$DATA_DIR/cache/ss-perception-probes/`, without a network or model download. `make test`,
`make coverage` and `make ci` now load the common environment and use that interpreter when it
exists and the operator has not chosen another one. Clean environments without the sibling still
skip these optional integration probes; deterministic fake-sibling tests continue to run there.

The unavailable-device probe now simulates unavailable CUDA on any host; the missing-checkpoint
probe substitutes a tiny model and no longer depends on cached DINO weights. The settings probe
reproduces the working-directory fallback regardless of where the sibling is installed. The
sandbox exposed no NVIDIA device, but these checks do not require one.

The real run exposed a sibling defect: a sibling installed below the ss-track project can discover
and open its ancestor `.env` despite a neutral working directory. The worker now refuses opening
`.env` or `.env.local` anywhere, and a fake-sibling regression demonstrated the old failure before
the fix. The real-release environment-loading probe continues to fail if this upstream behavior
is fixed, with an instruction to remove the workaround. The current
[discovery documentation](../current/corpus/discovery-runs.md) describes the boundary.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Skip reasons | `.venv/bin/pytest -q -rs tests/corpus/siblings/test_sibling_defects.py` before setup | seven skips: interpreter not configured |
| Guard regression | `.venv/bin/pytest -q tests/corpus/siblings/test_worker.py::test_a_sibling_cannot_read_ancestor_dotenv` | fails before fix and passes after |
| Real probes and guards | `source scripts/shared/common.sh; sst_load_test_env; .venv/bin/pytest -q -rs tests/corpus/siblings/test_sibling_defects.py tests/corpus/siblings/test_worker.py tests/quality/test_test_env.py` | pass, no skips; pinned sibling, no media or network |
| Required project gate | `make ci` | pass: 2318 passed, no skips |
| Documentation | `make lint-md` | pass |

## Audit handoff

- Fixed: an environment below a project root could read the project's `.env` despite the worker's
  neutral working directory. The worker refuses the read and the real-release probe detects removal
  of the underlying defect.
- Dropped: no ss-perception or other sibling repository change is required for the local workaround;
  this project does not control those releases.
- Observation: the sandbox exposes no NVIDIA device; the seven probes exercise configuration and
  workaround behavior and do not establish actual CUDA execution. This needs no further work for
  these tests.

## Close or resume

All gates passed with the locally installed pinned probe environment. The existing plan and its
counts are unchanged: 105 agent and 23 human tasks, with `corpus-combined-pool` next in the
agent lane and `define-locked-test-policy (optional)` next in the human lane.
