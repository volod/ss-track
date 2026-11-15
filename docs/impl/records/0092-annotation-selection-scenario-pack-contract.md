# Scenario pack contract

## Task and scope

- Id / capability: `scenario-pack-contract` / `annotation-selection`
- State: accepted
- Source: plan task at `42e2065`; no unrelated dirty files.
- Plan counts at start: 131 agent, 28 human; next agent `scenario-pack-contract`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### scenario-pack-contract

Labels, scenarios and reports all name a scenario pack, but no format defines one. A class ID has
no pinned meaning, and the mission's targets exist only in prose.

- Serves: `annotation-selection` -- [Evidence lanes](../design/spec.md#2-evidence-lanes-and-claims)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track contracts validate` accepts a scenario pack that states its
  classes, annotation vocabulary and limits, and a draft `aerial-small-objects` pack is the first.
- Scope boundary: A `declaration` contract for a pack: stable class IDs with scoring, distractor
  and ignore roles, a class hierarchy, minimum box, point and identifiable extents, extent bins,
  observer-platform strata, and named slots for the access policy, the non-disturbance envelope
  and the Phase 2 declarations of spec sections 19.3 and 19.7: target set, known non-targets,
  unknown set, declaration deadline and burden, declared target size and stand-off levels. The
  draft mission pack holds bird, bird of prey, drone, aircraft, insect and clutter classes. Its
  values are the owner's, through `approve-mission-scenario-pack`. No species list and no
  envelope value is invented here, and a Phase 2 slot stays empty until its human task fills it.
- Data and artifact paths: `contracts/declaration/scenario-pack/`, `scenarios/packs/`,
  `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add the contract and its registry entry, a loader that returns one pack hash,
  and positive and malformed fixtures.
- Acceptance gates: A duplicate class ID, a class with no role, an extent bin that overlaps
  another, and an envelope slot filled with no approval record are each refused with a reason.
  Changing any class, role, extent or bin changes the pack hash. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`declaration/scenario-pack` 1.0.0 is the pack format. `load_scenario_pack` returns one pack and the
SHA-256 of the canonical JSON of the validated document. Object key order and comments do not
change that hash. Array order does.

The draft `scenarios/packs/aerial-small-objects.yaml` names bird, bird of prey, drone, aircraft,
insect and clutter. Roles, the one parent link and the four observer platforms are unapproved
placeholders so the file can validate. Minimum extents are null, bins are empty, and the access
policy, envelopes and `phase2` object are absent. No species and no envelope value were invented.
Engineering defaults for deadline, burden and identifiable duration are not stored.

The schema requires a role and an approval object on any stated envelope. The loader enforces the
`x-rules` the dialect cannot state: unique class ids, parent links, a half-open extent partition,
extent order, envelope geometry, Phase 2 class lists, increasing stand-off levels, and unique
activity terms and strata. A zone has no coordinate field. An absent `unknown_set` stays unset.
The extent-envelope floor is not a pack field. Spec section 6.7 now states its shape: one floor
per primary measure on the scenario, each with a basis. A measure with no floor reports
`unavailable` for its smallest supported extent. The floor stays off the pack because it is one
suite's quality threshold, and the pack hash pins frozen labels. Section 15 lists it as its own
owner input.

See [Corpus](../current/corpus.md#scenario-pack). No new dependency, command, environment variable
or clean kind. The named approval is not opened.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Draft validates | `tests/annotate/test_scenario_pack.py::test_contracts_validate_accepts_the_draft` | pass |
| Duplicate class id | `test_a_duplicate_class_id_is_refused` | pass: `class-ids: duplicate class id bird` |
| Class with no role | `test_a_class_with_no_role_is_refused` | pass: schema requires `role` |
| Overlapping bins | `test_an_overlapping_extent_bin_is_refused` | pass: `bin small overlaps medium` |
| Envelope without approval | `test_an_envelope_without_an_approval_record_is_refused` | pass: refusal names `approval` |
| Hash moves | `test_class_role_extent_and_bin_each_change_the_pack_hash` | pass: class name, role, extent and bins each change it; key order does not |
| Owner slots stay empty | `test_the_draft_names_the_mission_classes_and_leaves_owner_values_unset` | pass: six classes; extents, bins, envelopes, phase2 and access policy unset |
| No floor on the pack | `test_an_extent_envelope_floor_on_the_pack_is_refused` | pass: a floor under `limits` or at the top level is refused |
| CI | `make ci` | pass: 2475 passed, 115 deselected |

## Audit handoff

- AUD-scenario-pack-contract-1, fixed: spec section 6.7 put the extent-envelope floor on the
  scenario, while `approve-mission-scenario-pack` listed floors as a pack value. Section 6.7 now
  settles this: the floor is on the scenario, one per measure, and the pack schema refuses it.
  `scenario-contract` owns the `extent_floors` field and its cohort-key gate.
  `extent-envelope-view` owns the measure-name check and the `unavailable` result. The new human
  task `approve-mission-extent-floors` owns the owner's values, which no task owned before.
- Dropped, no work needed: a named approval is not opened. No approval-record format exists, and
  the human tasks hold the signature. The same pattern is used by other declarations.
- Dropped, no work needed: array order is part of the pack hash. The owner approves one file, so a
  second normalization is not required.
- Limitation: the draft cannot feed a scale case or an extent envelope until minimum extents and
  bins are set. Owner: `approve-mission-scenario-pack`, which already says an unset value stays
  unset and each view that needs it is unavailable.

## Close or resume

Every gate passed. Current page [Corpus](../current/corpus.md#scenario-pack), records index and
plan updated. After the plan edit, 159 open tasks remain (130 agent, 29 human). The next agent
task is `annotation-contract`. The next human task is `define-locked-test-policy (optional)`.
`annotation-selection` stays `planned`.
