# Corpus source architecture plan

## Task and scope

- Id / capability: `corpus-source-architecture-plan` / `self-supervised-corpus`
- State: accepted
- Source: user request to update specification and decompose the plan for Visual WetlandBirds v4
  and the Hugging Face Drone Detection Dataset; working tree contains the prior evaluation work.
- Plan counts at start: 99 agent and 23 human; next agent `corpus-selection-evaluation`, next
  human `define-locked-test-policy (optional)`.
- Accepted task: design and schedule small implementation tasks for the two-source architecture,
  preserving existing work and routing the reviewed evaluation to the resulting workflow.
- Amendments: none.

## Implementation

Specified a two-source, rights-preserving corpus architecture in
[video corpus formation](../../design/spec.md#41a-self-supervised-video-corpus-formation), using the
existing import, corpus, discovery, review and freeze authorities. The owner selected Visual
WetlandBirds v4 and the Hugging Face Drone Detection Dataset; acquisition and computation remain
bounded by the existing source authorization. Added small tasks for source inventory, acquisition,
combined-pool preparation, blinded audit, actual review-budget matching, source-specific metrics,
a bounded real-data pilot and optional isolated WetlandBirds evidence. Split the existing evaluation
and human review dependencies so the pilot precedes review and review precedes evaluation. Updated
[current corpus documentation](../current/corpus.md) and the active evaluation record. No production
code, remote resources or credentials were changed in this planning work.

The existing capability remains planned. No new capability or publication workflow is implied.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Plan structure and ordering | `make lint-spec-plan` | pass: 0 findings |
| Documentation links | `make lint-doc-links` | pass: 0 broken links |
| Markdown | `make lint-md` | pass |
| Required project gate | `make ci` | pass: 2265 passed, 7 skipped |
| Task and dependency review | inspect both plan lanes and `make plan-status` | pass: 107 agent and 23 human tasks |

## Audit handoff

- `AUD-corpus-source-architecture-plan-1`: `discover evaluate` checks equality of selection counts,
  but not total offered workload; different audit overlaps can lead to unequal review budgets and a
  misleading matched comparison. Owner: `corpus-evaluation-review-budget`.
- `AUD-corpus-source-architecture-plan-2`: combined estimates can hide missing source coverage, and
  a group can span sources. Owner: `corpus-evaluation-by-source`, including shared-stratum variance.
- `AUD-corpus-source-architecture-plan-3`: the queue exposes selection cues and review records do
  not assert independence and blinding. Owner: `corpus-blinded-audit-review`.
- `AUD-corpus-source-architecture-plan-4`: selected collections have no reproducible inventory of
  source terms and pins. Owner: `corpus-source-inventory`.
- `AUD-corpus-source-architecture-plan-5`: selected source downloads need a reproducible, bounded
  implementation. Owner: `corpus-source-acquisition`.
- `AUD-corpus-source-architecture-plan-6`: combined source grouping and source lineage need a
  reproducible implementation. Owner: `corpus-combined-pool`.
- `AUD-corpus-source-architecture-plan-7`: the chosen WetlandBirds software and annotations have
  not been assessed as an isolated, rights-pinned evidence adapter. Owner: `corpus-wetland-evidence`.
- No related-repository change was identified; the existing sibling worker boundary is retained.

## Close or resume

Gates passed. The next agent task is `corpus-source-inventory`; the two-source pilot and human
review precede the remaining evaluation. After planning, 107 agent and 23 human tasks remain; the
next human task is `define-locked-test-policy (optional)`. The `self-supervised-corpus` capability
remains planned.
