# Mission alignment audit of the specification, plan and implementation

## Task and scope

- Id / capability: `mission-alignment-audit` / cross-capability
- State: accepted
- Source: user request; start commit `3c1ac6b79bc0c0ceda2bbc9304804b28a99a9ab1`; clean working tree.
- Plan counts at start: 102 agent and 21 human; next agent `corpus-selection-evaluation`, next human
  `define-locked-test-policy (optional)`.
- Accepted request: the owner restated the project goal and asked to "analyze the specification and
  tasks, audit the implementation, and make the necessary adjustments to the specification and task
  plan". The goal: a benchmark and framework for systems that detect and track small aerial
  objects, birds and drones, from autonomous drones. Phase 1 priorities are long-range detection,
  tracking and interaction with a human operator. Phase 2 is autonomous classification of specific
  species or drones with emphasis on the energy budgets of sensors and onboard computing, including
  analog equivalents. Bird safety is critical, and the reference implementation covers sensor
  fusion, data processing and drone control across varied hardware.
- Amendments: none.

## Implementation

Documentation only. No code, contract or sealed record changed.

Specification:

- Section 1 states the mission and the two phases, and maps each to capabilities.
- Section 2 and section 4.1 add the observer platform and make it and camera control closed
  vocabularies.
- Section 4.3 adds the scale-reduction case, and section 6.7 the small-target extent envelope.
- Section 7.3 makes the compute contract neutral about analog, in-sensor and neuromorphic stages.
- Section 7.7 is scheduled as `resource-aware-sensing`, and section 7.10 adds the platform energy
  budget.
- Section 11 adds the non-disturbance envelope and admits stand-off following, in simulation only,
  to the measurement-only scope.
- Sections 16.9 to 16.11 add the operator session, autonomous target recognition and stand-off
  following.
- Sections 12 to 15 and the registry follow: four capabilities added, `self-supervised-corpus`
  moved below the M1 pipeline, and the adapted paper cited.

Plan: 23 agent and 5 human tasks added, `self-supervised-corpus` moved after
`operator-session-evaluation`, and dependencies added to `annotation-contract`,
`generated-case-labels`, `run-bundle-store`, `local-comparison-report` and
`label-pilot-encounters`. The engine design gains milestones M7 and M8, the test plan gains the new
cases, the README names the mission, and the hardware shortlist no longer says its source PDFs are
in the repository.

Decisions:

- Phase 2 capabilities are `planned` with tasks, not section 12 candidates, because the plan
  already scheduled optional M4 to M6 extensions while the goal's own second phase had no task.
- The registry reorder is the one priority change. It is one row and one plan group, and moving
  them back restores the previous order.
- The offline benchmark reports target extent in pixels and never a range. A range needs an
  independent measurement.
- Drone control is a following law in simulation with no vehicle interface. A law that closes to
  contact or capture stays out of scope.

Rejected: a live operator console, a field-flight task, species behavior labels and a flight
endurance prediction. Each either needs evidence this repository does not produce or lies outside
both phases.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Baseline before the change | `make ci` at the start commit | pass: 2375 passed, 112 deselected |
| Specification and plan agree | `make lint-spec-plan` | pass: 0 findings |
| Links and anchors | `make lint-doc-links` | pass: 0 broken links |
| Markdown | `make lint-md` | pass |
| Existing plan text kept | Block comparison of the plan before and after | pass: only the amended fields differ |
| Full gate after the change | `make ci` | pass: 2375 passed, 112 deselected |

The audit read the specification, the plan, the design pages, the corpus current page outline, the
workload recipes and the package structure, sizes and import graph. It did not review corpus code
line by line: the earlier corpus-provenance audit and the open `self-supervised-corpus-audit` own
that.

## Audit handoff

- AUD-mission-alignment-audit-1, blocking for the goal: 27,900 source lines exist, about 23,100 of
  them in the corpus area, and none scores a detection or a track. The registry ranked corpus
  formation above the M1 pipeline. Fixed here by the registry order.
- AUD-mission-alignment-audit-2: the specification named no mission and no phases. Fixed here.
- AUD-mission-alignment-audit-3: sealing, sealed reads, atomic writes, locks and the clean-kind
  registry live under `src/ss_track/corpus/`, and the record reader imports a source module. Owner:
  `shared-evidence-primitives`.
- AUD-mission-alignment-audit-4: `capture.camera_control_mode` is free text although the
  specification gives it four values, and no recording states its observer platform. Owner:
  `recording-capture-vocabulary`.
- AUD-mission-alignment-audit-5: no format defines a scenario pack, so class IDs have no pinned
  meaning. Owners: `scenario-pack-contract` and `approve-mission-scenario-pack`.
- AUD-mission-alignment-audit-6: long-range detection had no measure. Owners:
  `scale-reduction-case` and `extent-envelope-view`.
- AUD-mission-alignment-audit-7: operator interaction ended at the first selection. Owners:
  `operator-session-contract` and `operator-workload-suite`.
- AUD-mission-alignment-audit-8: recognition of a species or drone type, the acquisition policy,
  the energy budget and drone control had no task. Owners: the `target-recognition`,
  `resource-aware-sensing` and `standoff-following-evaluation` groups.
- AUD-mission-alignment-audit-9, nonblocking: the corpus package holds two capabilities, source
  import takes helpers from review export in four places, and the discover command module and two
  interactive review modules exceed the size guideline. Owner: `discovery-package-split`.
- AUD-mission-alignment-audit-10, nonblocking: `current/corpus.md` has about 1,950 lines against
  the documented orientation-and-index shape. Owner: `current-corpus-page-split`.
- AUD-mission-alignment-audit-11: the hardware shortlist cited four PDFs as being in the repository
  root, and the adapted paper was uncited. Fixed here.
- Dropped, no work needed: `perception_worker.py` is long because it must run as one file in the
  sibling environment, and its docstring says so.
- Limitation: the pilot footage is mostly ground-observer video, and the reviewed pilot found no
  gain of model-assisted selection over uniform selection. `corpus-selection-evaluation` already
  states the second, and `recording-capture-vocabulary` makes the first visible in every build.

## Close or resume

Accepted. After planning, 125 agent and 26 human tasks remain. The next agent task is
`shared-evidence-primitives`; the next human task is `define-locked-test-policy (optional)`.
`operator-session-evaluation`, `target-recognition`, `resource-aware-sensing` and
`standoff-following-evaluation` are new `planned` capabilities. No capability changed to `shipped`.
