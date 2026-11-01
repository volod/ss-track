# Audit follow-up routing

## Task and scope

- Id / capability: `audit-follow-up-routing` / `documentation-integrity`
- State: accepted
- Source: owner request, on the uncommitted work of `generated-fixture-cases` at `78db68c`: treat the
  specification as living, add tasks for follow-ups, analyse earlier records, and fix the directive.
- Plan counts at start: 69 open (49 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=45`,
  `HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `annotation-contract` and
  `select-development-workload`.
- Accepted task: ad hoc, with no plan block.
- Amendments: none.

## Implementation

This change writes no code. It routes every audit item and limitation of records 0001 to 0004. Those
records stay as they were closed, and this table is the later routing that the
[planning workflow](../../guide/planning-workflow.md#task-records) calls for. Record 0004 was still
uncommitted, so its four stale owners were corrected in place.

Cause: an agent memory written for one template-rename request was applied as a general rule against
writing tasks. Audit entries therefore named owners or capabilities and stopped there, and nothing
required an owner task to state the item. At least nine items sat in owner tasks that did not
mention them.

Directive changes: `AGENTS.md`, the [planning workflow](../../guide/planning-workflow.md) and the
[record template](template.md) now say that discovery is part of implementation, that a record
schedules nothing, that an owner must be an open task whose text states the item, and that removing a
task updates its dependents. The wrong memory was deleted and replaced.

Specification changes: section 4.1 gains the duplicate-frame rule, version lineage, the frame set,
source terms and the guard on locked streams. Section 4.2 gains label orientation and derived case
labels. Section 4.3 gains track-following cases, severity sweeps and encounter-level fusion cases.
Section 5 gains refusal mapping, undelivered frames and hashing outside module latency. Section 10
gains two commands, the frame-set pin and a separate generated-case slice.

Three gaps had no record entry and came from reading the spec against the plan:

- The fusion fixtures of spec section 4.3 had no task, because the only mention was the exclusion in
  `generated-fixture-cases`. Task: `fusion-generated-fixtures`.
- The further cases of section 4.3 had no owner. Tasks: `compression-and-timing-cases`,
  `label-driven-cases`, `fusion-generated-fixtures`.
- Removing `generated-fixture-cases` left `g0a-pipeline-run` with no generated-case input. It now
  depends on `generated-case-labels`.

Two tasks are new product ideas from this work rather than repairs: `case-preview`, because the hand
contact sheet was the only way to see a region, and `robustness-severity-sweep`, which turns a
pass-or-fail case into a degradation curve.

### Audit items

| Item | Destination | How it is carried |
| --- | --- | --- |
| `AUD-corpus-manifest-import-1` | `sot-suite` | Gate amended: `missing` time-based scores on a real AVI |
| `AUD-corpus-manifest-import-2` | `import-stream-selection`, `g2-scenario-observation-bundles` | New task for video streams; sidecars in the amended bundle scope |
| `AUD-corpus-manifest-import-3` | `annotation-contract` | Scope and gate amended; spec section 4.2 |
| `AUD-corpus-manifest-import-4` | closed | Resolved by `frame-bundle-staging` |
| `AUD-corpus-manifest-import-5` | `module-image-recipes` | Scope amended with the notices |
| `AUD-frame-bundle-staging-1` | `event-schema-contract` | Gate amended |
| `AUD-frame-bundle-staging-2` | `staged-frame-set`, `scenario-contract` | New task, and scenario gate amended |
| `AUD-frame-bundle-staging-3` | `lockstep-runner` | Gate amended; spec section 5 |
| `AUD-frame-bundle-staging-4` | `paced-frame-release` | Scope and gate amended; spec section 5 |
| `AUD-frame-bundle-staging-5` | `container-module-sandbox` | Already stated: no mount of future frames |
| `AUD-frame-bundle-staging-6` | closed | Resolved by `corpus-split-grouping` |
| `AUD-frame-bundle-staging-7` | `camera-front-end` | Gate amended |
| `AUD-corpus-split-grouping-1` | closed | Resolved by `generated-fixture-cases` |
| `AUD-corpus-split-grouping-2` | `corpus-verify-rights` | New task; `scenario-contract` depends on it |
| `AUD-corpus-split-grouping-3` | `g2-scenario-observation-bundles` | Scope amended |
| `AUD-corpus-split-grouping-4` | `duplicate-frame-detection`, `near-duplicate-detection`, `corpus-version-lineage`, `locked-split-guard`, `define-locked-test-policy` | New tasks |
| `AUD-generated-fixture-cases-1`, `-2` | `generated-case-labels` | New task, and a `g0a-pipeline-run` dependency |
| `AUD-generated-fixture-cases-3` | `event-schema-contract` | Gate amended |
| `AUD-generated-fixture-cases-4` | `staged-frame-set` | New task |
| `AUD-generated-fixture-cases-5` | `lockstep-runner`, `local-comparison-report` | Gates amended; spec section 5 |
| `AUD-generated-fixture-cases-6` | `local-comparison-report` | Gate amended; spec section 10 |
| `AUD-generated-fixture-cases-7` | `source-terms-enforcement` | New task |

### Limitations

| Limitation | Destination |
| --- | --- |
| Decoding has no time limit, and Ctrl-C leaves a traceback | `decode-interruption-safety` |
| Arm64 has never been run | `arm64-reproducibility` |
| Empty `completeness_checks` means unverified | `scenario-contract`, `local-comparison-report` |
| Staging decodes the whole source per stream | `staging-single-pass` |
| An untagged color matrix converts as BT.601 | `declared-color-tags` |
| Retention is free text, and expiry goes unnoticed | `source-terms-enforcement` |
| A case holds a full copy of its raw frames | `bundle-frame-sharing` |
| One static rectangle, and an occluder that appears in one frame | `label-driven-cases` |
| A case perturbs one stream | `fusion-generated-fixtures` |
| A region can only be checked by eye before labels exist | `case-preview` |

Dropped, each because it needs no work:

- Frames are not fsynced one by one: `corpus verify` detects the damage and the rule is documented.
- Most bitstreams carry no checksum: only a capture-time hash can exclude this, and the field exists.
- Interlaced frames stay woven: they are counted, and deinterlacing would change the input.
- HDR keeps its curve in 8 bits: this is a stated decode-policy boundary.
- `holder` and `basis` stay uncompared: they are facts for a person, not ordered values.
- Two identical recipes under two names are allowed: they repeat a case, and add no evidence.
- A no-op case is found at staging: finding it needs pixels.
- Generated cases claim no realism: this is a stated boundary, not a gap.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Plan and spec stay coherent | `make lint-spec-plan` | pass, 0 findings |
| Documentation links | `make lint-doc-links`, `make lint-md` | pass |
| Dependency graph | One-off scan of every `Dependencies` field; its script was not kept | 89 tasks, no unknown id, no cycle, no required task on an optional one. Limit: `plan-dependency-integrity` is still the lasting check |
| `make ci` | `make ci` | pass, 446 tests. No code changed here |

## Audit handoff

None identified over records 0001 to 0004 and the plan. `make plan-status` still names
`select-development-workload` as the next human task although it now waits on an agent task, because
status reports priority rather than readiness; `plan-dependency-integrity` owns that.

## Close or resume

Complete; the commit is left to the project owner. Twenty tasks were added and 13 open tasks amended.
No capability changed status, and `corpus-provenance` stays `planned`, now with required work back in
the Agent lane.

Plan counts after: 89 open (68 agent, 21 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=62`,
`HUMAN-GATED=12`, `RUN NEEDED=6`; next eligible `source-terms-enforcement` and
`select-development-workload`, which depends on it.
