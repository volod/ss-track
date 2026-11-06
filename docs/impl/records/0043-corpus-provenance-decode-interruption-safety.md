# Decode interruption safety

## Task and scope

- Id / capability: `decode-interruption-safety` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `4052790`; clean worktree.
- Plan counts at start: 134 open (111 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=105, HUMAN-GATED=13, RUN NEEDED=6. Next agent `decode-interruption-safety (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### decode-interruption-safety (optional)

Ctrl-C ends a long run with a traceback, and a pathological file can decode with no limit.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An interrupted or over-limit import or stage ends with a structured refusal
  and leaves nothing partial.
- Scope boundary: SIGINT and a declared decode time limit. A hung native call stays a known limit if
  it never returns to Python.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Report `KeyboardInterrupt` through the command path and check a deadline in the
  decode loop, with an injected clock.
- Acceptance gates: SIGINT exits 1 with one JSON record and no traceback, leaving no scratch behind.
  A fixture past its limit is refused with the elapsed time.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`src/ss_track/corpus/decoding/deadline.py` bounds one strict decode to `DECODE_LIMIT_SECONDS`,
24 hours. The bound is not part of the decode policy, so it cannot change a pixel or a hash. The
loop in `inspect_media` checks a monotonic clock before each packet is decoded, before each frame
is written, after the consumer returns, and once the demux loop ends. A caller may pass another
clock. The default clock is read when the decode starts, so a test can replace
`deadline.decode_clock`. Landing on the limit is accepted; past it is `DECODE_TIME_EXCEEDED`,
naming `limit_seconds`, `elapsed_seconds` and `frames_decoded`. A whole number of seconds is stored
as an integer.

`commands/report.py` reports `KeyboardInterrupt` as `INTERRUPTED` (`interrupted by SIGINT`) and
exit 1, with no traceback. A second SIGINT while that line is written still exits 1. Import,
redecode and staging publish only after the decode returns, and their scratch context managers
remove the partial directory before that record is written. `corpus preview` now removes its
scratch PNG if the write itself is interrupted, because a clean refusal would otherwise hide that
file.

`result/command` 1.11.0 adds the two codes. No new dependency, environment variable or command
flag. Current page: [Decode time limit](../current/corpus.md#decode-time-limit). Specification
section 4.1 states the limit and the interrupt.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A fixture past its limit is refused and names the elapsed time | `tests/corpus/decoding/test_decode_limit.py::test_a_decode_past_its_limit_names_the_elapsed_time` | pass; `frames_decoded` 0; message names the elapsed seconds |
| Landing on the limit finishes; a delivered frame is named when the next check is past | `test_a_decode_that_lands_on_the_limit_finishes`, `test_a_frame_already_delivered_is_named_when_the_next_check_is_past` | pass; the second names `frames_decoded` 1 |
| Import and stage past the limit exit 1 and leave no scratch | `tests/corpus/test_interruption.py::test_an_import_past_its_limit_is_one_refusal_and_leaves_no_scratch`, `test_a_stage_past_its_limit_is_one_refusal_and_leaves_no_scratch` | pass; elapsed time is the limit plus 5 seconds |
| Redecode past the limit keeps the sealed bytes | `test_a_redecode_past_its_limit_keeps_the_imported_record` | pass; no `.incoming-` beside the source |
| SIGINT exits 1 with one JSON record, no traceback, and no scratch | `test_sigint_during_import_exits_with_one_refusal_and_no_scratch`, `test_sigint_during_stage_exits_with_one_refusal_and_no_scratch` | pass; real `SIGINT` in a child process; code `INTERRUPTED`; empty details |
| The command path reports one record, including a second SIGINT while logging | `tests/test_cli.py::test_sigint_is_one_json_refusal`, `test_a_second_sigint_while_reporting_still_exits` | pass; exit `EXIT_REFUSED` |
| An interrupt while writing a preview leaves no scratch PNG | `tests/corpus/cases/test_preview_limits.py::test_an_interrupt_while_writing_a_preview_leaves_no_scratch` | pass; `fsync` and `replace` |
| `make ci` | `make ci` | pass; 1803 tests |

## Audit handoff

`none identified`. Reviewed the decode loop, import, redecode, staging publication, the command
report path, the preview writer and `result/command` 1.11.0.

Dropped, each because it needs no work:

- A native decode call that never returns to Python is outside the check. The task states that
  limit. Staging removes that run's scratch the next time it takes the lock. Import has no lock, so
  a sweep could delete a live import; a process that dies inside the decoder can leave an
  `.incoming-` directory under `import/` for the operator to remove. Both are stated in
  [Decode time limit](../current/corpus.md#decode-time-limit).
- The 24-hour bound is the program constant. A per-run override was not part of the execution path.
- The preview scratch left by an interrupt is removed in this change.

## Close or resume

Gates passed. Current page, specification section 4.1, contracts page, product-core page, records
index, and the plan are updated. Plan counts after: 133 open (110 agent, 23 human). Statuses:
BLOCKED BY HUMAN=10, CLEAR=104, HUMAN-GATED=13, RUN NEEDED=6. Next agent
`compression-and-timing-cases (optional)`; next human `define-locked-test-policy (optional)`.
`corpus-provenance` stays `planned`.
