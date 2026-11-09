# corpus-motion-parallelism

## Task and scope

- Id / capability: `corpus-motion-parallelism` / `self-supervised-corpus`
- State: accepted
- Source: owner suggestion during `corpus-two-source-pilot`; start commit
  `21dae935e84a00431257617804114e65a4cb546d`. Existing working-tree changes belong to the
  active pilot, authorization, evaluation and progress tasks.
- Plan counts at start: 103 agent and 23 human; next agent `corpus-two-source-pilot`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-motion-parallelism (optional)

The pilot's uniform selection spent 11 minutes 11 seconds on one CPU core scoring 18.36 minutes
of footage. Independent stream motion calculations can use more of a multicore host, but each
worker needs memory for full-resolution frames and the existing integer scores must remain exact.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: An operator can use a bounded, host-appropriate number of CPU processes to
  score independent streams faster while retaining identical scores and refusals.
- Scope boundary: Motion scoring across streams in discovery and verification; no change to score
  revisions, sample designs, model outputs, or sealed result bytes.
- Data and artifact paths: `src/ss_track/corpus/selection/`, `tests/corpus/selection/`, and
  `$DATA_DIR/self-supervised-corpus/` for measured pilot evidence.
- Execution path: Provide an explicit worker limit and keep the safe serial path available; use
  host-aware limits and bounded work distribution, preserve per-stream ordering and structured
  frame-integrity errors, and measure actual CPU time, memory and wall time on this host.
- Acceptance gates: Deterministic offline fixtures verify serial and parallel scores and sealed
  results match, worker limits hold, and corrupt or unavailable frames still refuse correctly;
  measured results and resource limits are reported and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: the owner requested adaptive CPU and memory protection on the actual host.
  Revised task:

```markdown
#### corpus-motion-parallelism (optional)

The pilot's uniform selection spent 11 minutes 11 seconds on one CPU core scoring 18.36 minutes
of footage. Independent stream motion calculations can use more of a multicore host, but each
worker needs memory for full-resolution frames and the existing integer scores must remain exact.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: An operator can use a bounded, host-appropriate number of CPU processes to
  score independent streams faster while retaining identical scores and refusals.
- Scope boundary: Motion scoring across streams in discovery and verification; no change to score
  revisions, sample designs, model outputs, or sealed result bytes.
- Data and artifact paths: `src/ss_track/corpus/selection/`, `tests/corpus/selection/`, and
  `$DATA_DIR/self-supervised-corpus/` for measured pilot evidence.
- Execution path: Provide an explicit worker limit and keep the safe serial path available; cap
  automatic concurrency at half the available CPU capacity and bound it conservatively by available
  memory and frame dimensions. Fall back to serial if resource limits are unknown. Use bounded work
  distribution, preserve per-stream ordering and structured frame-integrity errors, and measure
  actual CPU time, memory and wall time on this host.
- Acceptance gates: Deterministic offline fixtures verify serial and parallel scores and sealed
  results match, CPU and memory limits hold, unknown resources fall back safely, and corrupt or
  unavailable frames still refuse correctly; measured results and resource limits are reported and
  `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: the host resource probe belongs in shared core, outside the corpus record-read gate.
  Revised task:

```markdown
#### corpus-motion-parallelism (optional)

The pilot's uniform selection spent 11 minutes 11 seconds on one CPU core scoring 18.36 minutes
of footage. Independent stream motion calculations can use more of a multicore host, but each
worker needs memory for full-resolution frames and the existing integer scores must remain exact.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: An operator can use a bounded, host-appropriate number of CPU processes to
  score independent streams faster while retaining identical scores and refusals.
- Scope boundary: Motion scoring across streams in discovery and verification; no change to score
  revisions, sample designs, model outputs, or sealed result bytes.
- Data and artifact paths: `src/ss_track/corpus/selection/`, `src/ss_track/core/`,
  `tests/corpus/selection/`, and `$DATA_DIR/self-supervised-corpus/` for measured pilot evidence.
- Execution path: Provide an explicit worker limit and keep the safe serial path available; cap
  automatic concurrency at half the available CPU capacity and bound it conservatively by available
  memory and frame dimensions. Fall back to serial if resource limits are unknown. Use bounded work
  distribution, preserve per-stream ordering and structured frame-integrity errors, and measure
  actual CPU time, memory and wall time on this host.
- Acceptance gates: Deterministic offline fixtures verify serial and parallel scores and sealed
  results match, CPU and memory limits hold, unknown resources fall back safely, and corrupt or
  unavailable frames still refuse correctly; measured results and resource limits are reported and
  `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

## Implementation

Motion scoring now shards independent streams across spawn-based processes. The default `auto`
cap is the minimum of half the effective logical CPU capacity, the number of streams and a
conservative available-memory estimate; `SST_MOTION_WORKERS` can lower it or force one worker.
The host probe accounts for CPU affinity and cgroup v2 ancestor quotas, `/proc/meminfo` and
remaining cgroup memory. It reserves 2 GiB and estimates each worker at 256 MiB plus 128 bytes
per pixel of the largest input frame; unknown resource limits use serial execution. The scheduler
rechecks headroom before dispatching more streams and restricts worker affinity. It preserves
integer scores and reconstructs structured frame refusals across process boundaries. See
[discovery runs](../current/corpus/discovery-runs.md#commands).

The estimate is not an absolute memory guarantee if unrelated workloads consume resources after
dispatch; already-running streams are not cancelled when the limit shrinks. Work is bounded per
stream, not within one long stream. On this host, six pilot streams including one 4K stream scored
in 86.099 s serial and 48.766 s adaptive after the final affinity change. Both results have SHA-256
`94f22a242e0928c541d996d12f15d84d3630c0626a84c8281e1d67a3dbf40fac`. The adaptive cap was six
workers (12 effective logical CPUs and about 10.2 GB available RAM); sampled summed process-tree
RSS peaked at 1146298368 bytes versus 428261376 bytes serial. Runs were sequential, so cache and
other host activity can affect the comparison. The earlier trial used a three-worker memory cap.
Both trials are under `$DATA_DIR/self-supervised-corpus/two-source-pilot-20261109/`, with the final
results in `motion-benchmark-serial-v2.json` and `motion-benchmark-auto-v2.json`.

## Acceptance evidence

Focused selection tests and the discovery sealed-record equality regression pass, including
serial versus parallel results, CPU and memory caps, unknown resource fallback, invalid worker
settings, and frame corruption. The final `make ci` passed: 2292 tests passed and 112 were
deselected. Earlier CI exposed
the corpus record-read guard; moving the operating-system probe into shared core fixed it
without weakening the guard.
The original pilot verifiers began before this implementation and both completed with serial scoring.

## Audit handoff

- `AUD-corpus-motion-parallelism-1`: The scheduler checks memory before dispatching each stream,
  but cannot stop already-running streams if other processes consume the remaining headroom.
  Its reserve is an estimate and cannot guarantee the host will avoid memory exhaustion. Owner:
  `corpus-motion-memory-pressure (optional)`.
- The serial fallback for a host whose resource limits cannot be measured is the specified safe
  behavior; it needs no separate work. The measured sample is an observation, not a throughput
  guarantee, because cache and other host activity differed between runs.

## Close or resume

All gates passed. The completed task is removed from the plan; the current discovery-runs page
documents configuration, limits and the measured host results. The pilot remains open for grouping
review and the blinded audit. The plan now has 103 agent and 23 human tasks; next are
`corpus-two-source-pilot` and `define-locked-test-policy (optional)` respectively. The
self-supervised corpus capability remains planned.
