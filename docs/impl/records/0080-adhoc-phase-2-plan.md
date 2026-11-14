# Phase 2 plan, extended design candidates and Phase 1 updates

## Task and scope

- Id / capability: `phase-2-plan` / cross-capability
- State: accepted
- Source: user request; start commit `3c1ac6b79bc0c0ceda2bbc9304804b28a99a9ab1`; the working tree
  holds the uncommitted mission alignment audit.
- Plan counts at start: 125 agent and 26 human; next agent `shared-evidence-primitives`, next human
  `define-locked-test-policy (optional)`.
- Accepted request: "please update phase 1 if needed and plan Phase 2 with extended sections 12 +
  specific spec"
- Amendments: none.

## Implementation

Documentation only. No code, contract or sealed record changed.

The request was read as: keep Phase 2 scheduled, make its specification concrete, and extend
section 12 with the Phase 2 candidates that stay unscheduled.

Phase 1 updates:

- Section 3 gains phase exits, so Phase 1 closes on named evidence.
- The reference tracker's two G0a versions are stated: without and with global-motion
  compensation.
- An operator action names the frame it refers to and arrives one response delay later.
- `authorize-airborne-observer-sources` and `frame-sequence-source-import` address the lack of
  airborne-observer footage. `corpus-scale-pilot` reports by observer platform.

Phase 2:

- Section 19 is the normative Phase 2 specification: entry conditions and gates P2a to P2c,
  autonomy chain and levels, target recognition, compute variants, energy-budgeted acquisition,
  stand-off following, the autonomous mission evaluation and the Phase 2 exit. Recognition and
  following moved there from sections 16.10 and 16.11.
- Section 7.10 states the budget formulas.
- `tensor-compute-backends` moved from section 12 to the registry, and
  `autonomous-mission-evaluation` is new. Milestone M9 is added.
- Section 12 now states, for 16 candidates, the phase, the problem, the evaluation, and the
  prerequisite and trigger for scheduling.

Plan: 11 agent and 2 human tasks added, 19 fields of existing tasks restated to match the
specific specification, and `corpus-scale-pilot` amended. The engine design and the test plan
follow.

Decisions:

- The mission evaluation uses surrogate perception drawn from measured suite results. Rendering
  images was rejected: it would add a scene model nobody has validated.
- Energy evidence has three tiers. A replay priced with a measured mode profile is a model and
  supports no saving claim.
- A following law reads an estimated range, and violations are scored on the true range.
- Passive radio and acoustic cues, stereo range, low-light operation and any flight stay
  candidates. Each needs a selected sensor or an approval that Phase 2 does not have.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Specification and plan agree | `make lint-spec-plan` | pass: 0 findings |
| Links and anchors | `make lint-doc-links` | pass: 0 broken links |
| Markdown | `make lint-md` | pass |
| Full gate | `make ci` | pass: 2375 passed, 112 deselected |

The two public collections named as candidate airborne-observer sources were checked by web
search only. The Airborne Object Tracking listing states CDLA-Permissive-1.0 and image sequences
in which birds and drones are incidental. The license of Det-Fly was not confirmed.
`authorize-airborne-observer-sources` owns the check.

## Audit handoff

- AUD-phase-2-plan-1: the reviewed pilot holds almost no airborne-observer footage, so the
  Phase 1 mission claim has no evidence source. Owners: `authorize-airborne-observer-sources` and
  `frame-sequence-source-import`.
- AUD-phase-2-plan-2: the G0a comparison named two reference versions without saying how they
  differ. Owner: `reference-sot-tracker`.
- AUD-phase-2-plan-3: the scripted operator's selection had no stated age. Owner:
  `operator-session-contract`.
- AUD-phase-2-plan-4: no suite scored the autonomy chain as a whole, or the cost of distance.
  Owners: the `autonomous-mission-evaluation` group.
- AUD-phase-2-plan-5: energy of onboard computing had no scheduled measure. Owners: the
  `tensor-compute-backends` group and `measure-compute-variants`.
- Limitation: every Phase 2 default, such as the declaration burden and deadline, is an
  engineering value. The owner inputs of specification section 15 state what must be declared
  before a P2b or mission result.
- Limitation: the mission surrogate draws independently between epochs unless a table supplies a
  measured dependence. `mission-simulator` states this in every result.

## Close or resume

Accepted. After planning, 136 agent and 28 human tasks remain. The next agent task is
`shared-evidence-primitives`; the next human task is `define-locked-test-policy (optional)`.
`tensor-compute-backends` and `autonomous-mission-evaluation` are new `planned` capabilities. No
capability changed to `shipped`.
