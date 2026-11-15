# ARM CI workload

## Task and scope

- Id / capability: `arm-ci-workload` / `reproducible-environment`
- State: accepted
- Source: user request to investigate long GitHub jobs and move suitable work locally; start commit
  `023553f`. The working tree contains the earlier shared-evidence-primitives change.
- Plan counts at start: 135 agent, 28 human; next agent `recording-capture-vocabulary`, next human
  `define-locked-test-policy` (optional).
- Accepted request: investigate the long GitHub Actions jobs and move suitable work locally to
  reduce load in distributed development, focusing on the reported ARM reproducibility check.
- Amendments: none.

## Implementation

Added `make test-architecture` for pixel, decoder policy and transform golden tests. Pull requests
and pushes run that target plus the existing cross-host fixture; manual dispatch retains the full
ARM suite. The full suite remains available locally with `make test`. See
[Developer Tooling](../current/developer-tooling.md).

## Acceptance evidence

| Gate | Exact command or artifact | Result and limit |
| --- | --- | --- |
| Architecture-sensitive subset | `make test-architecture` | 55 passed in 3.44 seconds on x86-64; not an ARM timing. |
| Required checks | `make ci` | Passed: 2385 tests passed, 112 deselected. |
| Package build | `UV_NO_BUILD_ISOLATION=1 UV_CACHE_DIR=/tmp/ss-track-build-uv-cache make build` | Passed using the installed build environment; the default cache path was read-only. |
| Markdown | `make lint-md` | One MD013 finding in the prior closed record; see audit handoff. |
| Full local quality | `make quality` | Interrupted during contract evolution tests; coverage result not obtained. |
| Hosted ARM job | `.github/workflows/arm64-reproducibility.yml` | Workflow shape checked locally; hardware execution and job timing not observed. |

## Audit handoff

- `AUD-arm-ci-workload-1`: `make lint-md` reports an overlong line in closed record 0081, so
  `make quality` cannot complete its Markdown gate. The closed-record rule prevents reflow without
  a human decision. Owner: `resolve-closed-record-markdown` in the human lane.
- Automatic ARM coverage excludes the rest of the suite. This is the requested workload tradeoff:
  a local ARM `make test` or manual workflow run retains the full check. No further work is needed
  for this intentional boundary.
- ARM hardware execution and a new job duration are not claimed; this host is x86-64 and the
  changed workflow has not run on GitHub.

## Close or resume

The required CI gate passed. Updated the developer tooling and corpus pages, development guide and
cross-host test plan, and linked this record. One human-gated Markdown issue was added to the plan:
135 agent and 29 human tasks remain. The capability remains shipped.
