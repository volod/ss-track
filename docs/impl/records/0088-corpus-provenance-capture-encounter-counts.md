# Capture encounter counts

## Task and scope

- Id / capability: `capture-encounter-counts` / `corpus-provenance`
- State: accepted
- Source: plan task; start commit `88fc639`, clean worktree.
- Plan counts at start: 163 (135 agent, 28 human); next agent
  `capture-encounter-counts`, next human `define-locked-test-policy`.
- Accepted task:

```markdown
#### capture-encounter-counts

A build reports split counts but cannot expose how much of its evidence uses each camera-control
mode or observer platform, leaving ground footage indistinguishable from airborne evidence.

- Serves: `corpus-provenance` -- [Capture compatibility](../design/spec.md#capture-vocabulary-and-historical-source-records)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Build results report distinct encounter counts for every control-mode and
  observer-platform bin, including unknown and zero bins.
- Scope boundary: Count each encounter once in each applicable bin; mixed-stream encounters can
  enter several bins. Generated cases do not contribute. No score, joint histogram, inferred
  classification or claim that bin totals are additive.
- Data and artifact paths: `src/ss_track/corpus/versions/`, `tests/corpus/`, command-result contracts.
- Execution path: Reuse the verified source records used to build streams, retain capture data
  only as needed for the result, and avoid changing sealed corpus bytes for reporting alone.
  Document result field names and the multi-stream counting rule.
- Acceptance gates: Hand-counted fixtures cover every value, omission, repeated streams, mixed
  values in one encounter, multiple encounters and generated cases. A rerun has the same counts
  and manifest seal. Historical sources refuse with the migration remedy and count correctly
  after explicit amendment and successor build. Frozen contracts and `make ci` pass.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

A build result now carries `capture_encounters`. `camera_control_mode` and `observer_platform`
each list every closed value, including a value no encounter uses. Each encounter is counted once
in every bin its streams use. Generated cases are not part of the sequence that is counted.
`corpus/versions/capture_counts.py` owns the count. `corpus/versions/placement.py` reads the two
judgments from the verified source while it places the stream, and the sealed corpus manifest
does not store them. Frozen `result/command` 1.28.0 adds the optional result object. No
dependency, environment variable, or data artifact kind was added. See
[Corpus](../current/corpus.md).

Stream placement moved out of `builder.py` so the build module stays within the size aim. The
sealed stream fields are unchanged. The contracts index omitted the shipped recording and
source-manifest major 3; this change adds those rows because it was already editing that index.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Every value, omission, repeated streams, mixed encounter, several encounters, generated cases, zero bins, rerun seal | `tests/corpus/versions/test_capture_counts.py` | pass; local synthetic clips, no network |
| Historical refusal, migration remedy, explicit amendment, successor counts and seal | `tests/corpus/versions/test_capture_counts.py::test_a_historical_source_refuses_then_counts_after_amendment` | pass; schema 2 record resealed from a real import, original bytes retained |
| Vocabulary agreement and frozen command result | `test_count_bins_follow_the_closed_capture_vocabulary`; `make ci` contract evolution | pass |
| Required project gate | `make ci` | pass; 2408 passed, 115 deselected; format, lint, typing, complexity, shell, links, plan integrity and frozen contracts |

## Audit handoff

None identified. Reviewed the counting rule, sealed-manifest exclusion, historical refusal and
amendment, the command-result bump, and the vocabulary shared with the source contract. A joint
of split and capture bin is the histogram this task excludes; later score tasks already own
platform strata. The missing major 3 rows in the contracts index were corrected here.

## Close or resume

All acceptance gates passed. Updated the corpus and contracts pages and the records index,
removed the completed task from the plan, and retained `corpus-provenance` as shipped. Plan
counts after: 162 tasks (134 agent, 28 human); next agent `scale-reduction-case`, next human
`define-locked-test-policy`.
