# Plan self-supervised video corpus formation

## Task and scope

- Id / capability: `self-supervised-corpus-plan` / `adhoc`
- State: accepted.
- Source: user request to create a task group for forming a large video corpus using
  [ss-fusion](https://github.com/volod/ss-fusion) and [ss-video](https://github.com/volod/ss-video).
  Starting HEAD `d20d0e2`; unrelated corpus staging and workload selection changes were already in
  the worktree.
- Plan counts at start: 126 tasks, 105 agent and 21 human. Next agent `bundle-frame-sharing`;
  next human `define-locked-test-policy`.
- Accepted task: ad hoc planning request; no existing plan task was started or removed.
- Amendments: none.

## Implementation

Added specification section 4.1a and registered `self-supervised-corpus` as planned. Its agent
lane covers an integration study, interchange contracts, video index adapter, self-supervised
selection and unbiased audit samples, duplicate/group handling, reviewed export, evaluation, a
resource-bounded pilot and the group audit. Its human lane covers source rights and resource
approval, followed by independent review. The plan defines a valid negative and leaves real source
acquisition, model runs and human approval for their respective tasks.

Repository inspection used temporary shallow clones: ss-fusion commit
`12cb0861af8f6ae6562d2cf5211547e284c5b40d` describes perception, CLIP/DINO embedding and
SSL adaptation in `docs/impl/current/local-pipeline.md`. ss-video commit
`703e3c943dbc960a16cbc859680172c5a7ba5255` describes video ingest, sampling and retrieval in
`docs/impl/current/production-server.md`; its `pyproject.toml` pins ss-fusion tag `v0.2.0` while
the inspected ss-fusion tree reports `0.2.1`. This is an interface and version compatibility
question, not proof that the versions interoperate. `corpus-sibling-integration-study` owns pin and
interface evaluation before adapter implementation.

The current corpus page describes the boundary of the available pilot. Neither sibling was installed,
modified or run, and no large corpus or labels were created. Network-dependent work remains in the
plan; deterministic tests there must be network-free.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Product need, boundary, evaluation and valid negative | `docs/design/spec.md`, section 4.1a and registry | Specified before the new task group |
| Task and registry integrity | `make lint-spec-plan` | Passed with the registered group and lane structure |
| Document links | `make lint-doc-links` | Passed |
| Final gate | `make ci` | Passed: 1724 tests and four third-party deprecation warnings |
| Counts | `make plan-status` | 137 tasks: 114 agent and 23 human; no capability shipped |

## Audit handoff

- Sibling integration and pin mismatch: owned by `corpus-sibling-integration-study`, whose scope
  requires exact revisions, licenses and compatibility before implementation.
- Model selection bias, uncertain negatives, and missed small birds: owned by
  `corpus-ssl-selection`, `corpus-selection-evaluation` and the human
  `review-video-corpus-sample` task, each covering its distinct sampling, reporting or review step.
- Rights and resource authority: owned by `authorize-video-corpus-sources`; the pilot task explicitly
  cannot acquire or process beyond the approved sources and budget.
- No model or dataset result was produced. This is a planning observation, so no implementation
  finding or performance claim is implied.

## Close or resume

Specification, registry and both plan lanes are updated; current corpus documentation links this
record. The required gate passed. Plan counts moved
from 126 (105 agent, 21 human) to 137 (114 agent, 23 human). No capability changed to shipped.
