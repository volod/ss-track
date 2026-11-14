# Capture Vocabulary Decomposition

## Task and scope

- Id / capability: `capture-vocabulary-decomposition` / `corpus-provenance`.
- State: accepted (decomposition only).
- Source: ad hoc user request at `9c55a20`. Existing dirty work was the active vocabulary
  task record and its index entry; both are preserved with a corrected unused sequence.
- Plan counts at start: 135 agent, 28 human. Next agent `recording-capture-vocabulary`;
  next human `define-locked-test-policy`.
- Accepted task:

```text
please finalize the task, if theres a difficalties please decompose task and update specs
and plan.md first, to have reasonable implementation path
```

- Amendments: This record covers the requested prerequisite decomposition only. The original
  implementation remains active in record 0084, and is not represented as completed here.

## Implementation

The specification states historical inspection, a facts disposition, explicit capture amendment,
composition with terms and decode operations, preserved records and pins, and encounter counting.
The plan gives each part a required task with deterministic acceptance gates. The original
vocabulary task keeps its stable id and now depends on inspection; encounter reporting follows it.
Existing consumers depending on the vocabulary keep that dependency. No contract or runtime code
was changed, no new capability was registered, and no new data artifact kind was introduced.

The duplicate active-record sequence is corrected to 0084; the already closed 0054 is untouched.
[Governance](../current/governance.md) describes how remaining scope stays tracked.

## Acceptance evidence

- `make ci`: passed, 2385 tests passed and 112 deselected. This verifies the documentation
  change against the existing implementation; it does not prove the planned feature.
- `make lint-doc-links` and `make lint-spec-plan`: passed with zero findings.
- Targeted `pymarkdown scan` of all six changed Markdown files: passed.
- `git diff --check`: passed. Scope review found only the intended documentation changes;
  no production code, dependency, contract or runtime evidence was changed.

## Audit handoff

- Historical text, numeric and null values: `source-capture-inspection` owns exact inspection.
- A major bump would strand sources without a usable migration: `recording-capture-vocabulary`
  owns the explicit replacement path, composite operations and successor-build regression.
- Ambiguous mixed-stream counting: `capture-encounter-counts` owns distinct encounters per bin,
  zero/unknown bins and exclusion of generated cases.
- Duplicate active-record number: fixed here; no remaining work and no closed history changed.

## Close or resume

The decomposition gates passed. Original implementation remains unaccepted. After decomposition,
137 agent and 28 human tasks remain.
Next agent is `source-capture-inspection`; next human is unchanged. Capability status is unchanged.
