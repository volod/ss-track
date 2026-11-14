# corpus-interactive-link-review

## Task and scope

- Id / capability: `corpus-interactive-link-review` / `self-supervised-corpus`
- State: accepted
- Source: user request; start commit `21dae935e84a00431257617804114e65a4cb546d`. The working
  tree contains the preceding pilot, adaptive motion and budget research work.
- Plan counts at start: 105 agent, 23 human; next agent `corpus-interactive-link-review`, next
  human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-interactive-link-review

Reviewing flagged recording relationships in a spreadsheet is cumbersome and interruption can
lose work or leave decisions unusable by the existing link checker.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A reviewer can inspect flagged recording pairs, navigate forward and back,
  record or revise decisions, and resume safely after an interruption or power loss.
- Scope boundary: Local interactive review of a verified link record; uncertain pairs stay
  undecided, and the existing link-decisions declaration remains authoritative.
- Data and artifact paths: `src/ss_track/corpus/links/`, `src/ss_track/commands/`,
  `tests/corpus/links/`, and `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Explain controls and semantics before review, show source evidence and paths,
  support replayable navigation and an explicit uncertain decision, checkpoint each change with
  durable atomic writes and locking, and emit decisions accepted by `discover links`.
- Acceptance gates: Deterministic tests cover navigation, edits, skipped pairs, restart, malformed
  or conflicting checkpoints, concurrent writers, interruption and durable writes; a real pilot
  link record can initialize without inventing decisions, and `make ci` passes.
- Documentation target: [Leakage review](current/corpus/leakage-review.md).
```

- Amendments: none.

## Implementation

Added `discover review-links`: the controlling terminal provides instructions, playback, evidence,
forward/back/jump navigation, editing, and optional notes. The checkpoint uses the reviewer and
source-pair decisions already accepted by `discover links`; unknown pairs remain unknown. A lock
prevents concurrent writers. Each checkpoint replacement synchronizes file and directory, and a
restart returns to the first unresolved pair. Existing decisions and outside pairs are retained.
Locked footage is not displayed or played. The 1.1.0 minor versions of the link-decisions and
corpus-links contracts allow an empty checkpoint and zero recorded decisions, preserving 1.0.0.

## Acceptance evidence

Deterministic tests exercise navigation, edits, locked-source handling, playback stream selection,
restart, interruptions, durable checkpoint writes, malformed and conflicting checkpoints, a real
pseudo-terminal, concurrent writers, and integration with the link checker. The real pilot link
record supplied 136 pairs to a temporary review checkpoint, which round-tripped empty without any
invented decisions. The local `ffplay` executable is available. `make ci` passed: 2309 tests passed
and 112 deselected; format, lint, typing, complexity, documentation links, plan integrity, and
frozen contracts passed.

## Audit handoff

No new unresolved finding: a skipped or unreviewable link stays unresolved; this is a relationship
review and does not replace the independently sampled blinded window audit already covered by the
open `review-video-corpus-sample` task. The pilot's remaining human adjudication and budget work
remain in their existing plan tasks.

## Close or resume

Accepted. Plan counts at close: 104 agent, 23 human; next agent `corpus-two-source-pilot`, next
human `define-locked-test-policy (optional)`. The completed task was removed and its pilot
dependency cleared.
