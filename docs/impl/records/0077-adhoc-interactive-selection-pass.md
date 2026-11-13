# Interactive selection pass

## Task and scope

- Id / capability: `interactive-selection-pass` / `self-supervised-corpus`
- State: accepted
- Source: user request following record 0076; start commit `343ab81` with the uncommitted
  `interactive-audit-review` change of record 0076 in the working tree.
- Plan counts at start: 102 agent and 22 human; next agent `corpus-selection-evaluation`, next
  human `define-locked-test-policy (optional)`.
- Accepted request: "extend the command to handle the selection pass as well"
- Amendments: none.

## Implementation

Added `ss-track discover review-pass` for the selection pass of the human task
`review-video-corpus-sample`; the specification's selection-pass paragraph in section 4.1a states
it and what it does not do. `corpus/review/pass_session.py` verifies the run, lists its selected
offered windows through the existing `expected_windows`, reads the run's review under
`declaration/corpus-review` with `read_declaration`, resumes a pass by the same reviewer, and
rewrites the review atomically with its decisions unchanged and the pass so far.
`render_window` reuses the packet's `render_frames` and `picture_name`, now public.
`corpus/review/pass_interactive.py` holds the loop and renders one window at a time into a
temporary folder outside the data root that is removed on the next window, so no data-root kind is
added and `data clean` needs no registration.

What the two terminal reviews share moved into `corpus/review/review_terminal.py`: prompts, the
capped effort clock, whole-minute rounding, help text and navigation. `discover review-audit` now
uses it with unchanged behavior, and the viewer type aliases live in `audit_viewer.py`. The result
is the existing `recorded` status with `record_path`; no contract, dependency or environment
variable changed.

Decisions: the pass is written into the review in place, which is the documented workflow for the
commented block, rather than into a second file that freeze would not read. The session shows no
audit observation of a window, so the pass cannot copy the audit's answer. Rejected: rendering all
200 windows up front, about 20 GB in the pilot.

Limitations: the pass is not blinded, and nothing checks that its reviewer worked apart from the
audit reviewer; both are already stated under
[Limits](../current/corpus/review-and-freeze.md#limits) and are declarations by design. Re-running
`discover unblind` into the same directory after a pass is `CORPUS_CONFLICT`, as for any edited
review, and is stated in the current page. Current state:
[interactive selection pass](../current/corpus/review-and-freeze.md#interactive-selection-pass).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| A pass saves, resumes and clears with the review's decisions unchanged, and export accepts it | `tests/corpus/review/test_pass_interactive.py` | pass |
| Another reviewer, a stray window and another run's review are refused | same file | pass |
| Pictures render one window at a time | `test_windows_render_one_at_a_time` | pass |
| The audit review is unchanged by the shared base | `tests/corpus/review/test_audit_interactive.py` | pass |
| Real runs | `pass_target` on `pilot-diverse-grouped-20261113` and `pilot-uniform-grouped-20261113`: 100 windows each; one window rendered to a scratch folder, 16 frames, 99 MB, then removed | pass; no picture shown |
| Repository gate | `make ci` | pass: 2374 passed |

## Audit handoff

None identified. Reviewed scope: the two new modules, the shared terminal base, the audit-review
refactor, the CLI wiring and the documentation; the session reads no private mapping and writes
nothing in the data root.

## Close or resume

Accepted. The human task `review-video-corpus-sample` stays in the plan, and its execution path
now names both commands. Plan counts after: 102 agent and 22 human, unchanged.
