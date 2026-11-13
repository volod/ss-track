# review-pilot-recording-links

## Task and scope

- Id / capability: `review-pilot-recording-links` / `self-supervised-corpus`
- State: accepted
- Source: plan task, human lane; start commit `58ece78`; clean tracked worktree.
- Plan counts at start: 102 agent and 23 human; next agent `corpus-selection-evaluation`, next
  human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### review-pilot-recording-links (optional)

The pilot's link review was delegated to Claude; the owner may confirm it, and a second host has
not yet recreated the pinned dataset.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: HUMAN-GATED
- Dependencies: none.
- User-visible outcome: The owner confirms or revises the delegated link decisions, and a named
  reviewer independently creates the pinned pilot dataset on another host and compares its
  identities with the origin's.
- Scope boundary: Human decisions on flagged source relationships and an independent creation on a
  second host; uncertain pairs remain undecided, and this review does not replace the independent
  blinded window audit.
- Data and artifact paths: `docs/impl/workloads/two-source-pilot/link-decisions.yaml`,
  `$DATA_DIR/corpus/<corpus-id>/manifest.json`, `$DATA_DIR/self-supervised-corpus/<run-id>/links.json`
  and the media-free portable review tar.
- Execution path: Review the [delegated decisions](workloads/two-source-pilot/README.md#grouping)
  and their notes; a changed decision or grouping makes a new pool version whose runs are repeated.
  Use the [other-host review instructions](current/corpus/leakage-review.md#review-on-another-host)
  to create the dataset on a second host and compare its staged identities with the origin's, then
  release its frames and download cache with
  [data clean](current/corpus.md#cleaning-the-data-root) once the comparison is recorded.
- Acceptance gates: The second host's independently created dataset compares identical, or the
  difference is reported; a revised decision validates with `discover links` and its grouping is
  reconciled in a new version; the owner's confirmation or revision is recorded.
- Documentation target: [Leakage review](current/corpus/leakage-review.md#review-on-another-host).
```

- Amendments: none.

## Implementation

The owner, vola, reviewed the delegated link decisions of the two-source pilot,
`docs/impl/workloads/two-source-pilot/link-decisions.yaml` (8 related and 58 unrelated pairs, each
with its note), and the grouping by source of the 82 undecided same-source pairs, and confirmed
them without change on 2026-11-13: "Part 1: confirm or revise my link decisions - confirmed." No
decision or grouping changed, so `pilot-two-source-grouped-20261113`, its runs, its clear link
review and the blinded audit packet stand as they are.

The owner independently created the pinned pilot dataset on a second computer from the portable
archive `pilot-link-review.tar` of `pilot-links-grouped-20261113` and the recipe in
`docs/impl/workloads/two-source-pilot/`, and reported the comparison with the origin's staged
identities as identical: "Part 2: recreate the dataset on a second computer - datasets is
identical." The second host's `review-accept` output and comparison record stay on that host; this
record holds the owner's report of them, not their bytes. The origin's own fresh-data-root
recreation is independently recorded as `identical` under
`$DATA_DIR/run/pilot-fresh-compare-20261113/`. The
[leakage review](../current/corpus/leakage-review.md#review-on-another-host) states the outcome.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| The second host's independently created dataset compares identical, or the difference is reported | owner's `discover review-accept` on the second host | pass as reported by the owner; the second host's comparison record was not transferred |
| A revised decision validates with `discover links` and is reconciled in a new version | no decision revised | not applicable |
| The owner's confirmation or revision is recorded | owner's confirmation quoted above | pass |
| Plan integrity | `make lint-spec-plan`, `make lint-doc-links`, `make lint-md`, `make ci` | pass |

## Audit handoff

- `AUD-review-pilot-recording-links-1`: the second host's comparison record is not on the origin.
  Dropped: the origin's fresh-root comparison is recorded, the owner reported the second result,
  and no later task reads the second host's record.
- Reviewed scope: the owner's confirmation, the delegated decisions and the second-host report;
  nothing else identified.

## Close or resume

Accepted. The task left the plan. With `authorize-video-corpus-sources` accepted in record 0068,
the self-supervised corpus group's next human task is `review-video-corpus-sample`, the blinded
audit of `pilot-audit-grouped-20261113`. The capability remains planned.
