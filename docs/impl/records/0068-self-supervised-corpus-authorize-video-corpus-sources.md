# authorize-video-corpus-sources

## Task and scope

- Id / capability: `authorize-video-corpus-sources` / `self-supervised-corpus`
- State: accepted
- Source: plan task; start commit `21dae935e84a00431257617804114e65a4cb546d`;
  preexisting change: `docs/impl/records/0056-self-supervised-corpus-corpus-selection-evaluation.md`.
- Plan counts at start: 101 agent, 23 human; next agent `corpus-two-source-pilot`,
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### authorize-video-corpus-sources

A large candidate pool needs source permissions, available storage and a spending envelope a tool
cannot grant itself.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: HUMAN-GATED
- Dependencies: none.
- User-visible outcome: The owner approves a source list, corpus size and diversity targets, permitted
  processing, compute and storage budgets, a baseline review budget, and use of the sibling code and
  model weights the [integration plan](current/corpus/sibling-integration.md#model-and-data-rights)
  pins.
- Scope boundary: Authorized public or private sources, benchmarking, model processing and derived
  artifacts, retention and access; public redistribution is a separate permission.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`.
- Execution path: Record each source's terms, allowed uses, retention and handling, and select an
  explicit resource envelope before acquiring or running over the sources.
- Acceptance gates: Every selected source has verifiable rights and retention, a named owner of the
  approval, approved model use and cost limits, and target coverage and negative cases. ss-fusion
  carries no licence, so its pinned tag needs a licence or a recorded grant, and each weight needs
  an approved revision (a Hugging Face snapshot commit or a torch.hub tree digest, as
  [discovery plans](current/corpus/discovery-runs.md#plan) pin them) and use terms. The approval
  has a reference that every discovery plan names. No eligible
  source or inadequate budget is a recorded valid negative and authorizes no acquisition.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: the licensed `v0.2.1` tag makes the earlier statement that ss-fusion has no
  licence outdated. Revised task:

```markdown
#### authorize-video-corpus-sources

A large candidate pool needs source permissions, available storage and a spending envelope a tool
cannot grant itself.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: HUMAN-GATED
- Dependencies: none.
- User-visible outcome: The owner approves a source list, corpus size and diversity targets, permitted
  processing, compute and storage budgets, a baseline review budget, and use of the sibling code and
  model weights the [integration plan](current/corpus/sibling-integration.md#model-and-data-rights)
  pins.
- Scope boundary: Authorized public or private sources, benchmarking, model processing and derived
  artifacts, retention and access; public redistribution is a separate permission.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`.
- Execution path: Record each source's terms, allowed uses, retention and handling, and select an
  explicit resource envelope before acquiring or running over the sources.
- Acceptance gates: Every selected source has verifiable rights and retention, a named owner of the
  approval, approved model use and cost limits, and target coverage and negative cases. The pinned
  ss-fusion tag needs a licence or a recorded grant, and each weight needs
  an approved revision (a Hugging Face snapshot commit or a torch.hub tree digest, as
  [discovery plans](current/corpus/discovery-runs.md#plan) pin them) and use terms. The approval
  has a reference that every discovery plan names. No eligible
  source or inadequate budget is a recorded valid negative and authorizes no acquisition.
- Documentation target: [Corpus](current/corpus.md).
```

## Implementation

The owner authorized local internal use of the planned WetlandBirds and Drone Detection sources,
derived frames and model processing, restricted sharing and retention as long as needed. The owner
selected ss-fusion `v0.2.1` and the pinned CLIP and DINO weights. Total transfer is capped at
50 GB and additional pilot storage at 300 GB. The scope is at most 1000 videos or 60 minutes,
and up to 5000 review windows and 300 review groups. CPU and GPU are allowed; review independence
and reviewer availability remain unconfirmed. Ask before increasing the transfer cap.

The public `v0.2.1` commit `75debcfed31a3c148d2f194a8ae2345e4b7508f1` carries an MIT
licence. The Zenodo API states CC BY 4.0 for WetlandBirds v4; the Hugging Face card states MIT
but describes a collection of upstream sources. Per-video provenance and source terms require
further review before authorization can be closed. The pilot is not authorized for public
redistribution. The pinned API metadata is retained with the pilot artifacts.

On 2026-11-13 the owner completed the approval:

```yaml
approval_owner: vola
approval_reference: approval-2026-11-13
personal_drone_videos: accept
retention: no dated
sharing: no public redistribution
derived_frames: true
models_approved: clip-977e3dd0, dinov2-7764ea0f, ss-perception-75debcf
targets_ok: yes, plas add branches of trees and bushes, the line separating the sky from the landscape
reviewers: {links: vola, audit: vola, selection_pass: vola, hours: 8}
audit_independent: no
transfer_used_ok: yes
```

The per-video terms review that the first approval left open is resolved from the dataset's own
metadata: each selected drone video's license column names `cc-1.0`, `mit` or `personal`.
GitHub's license API reports CC0-1.0 for DroneDetectionThesis/Drone-detection-dataset, the
`cc-1.0` source, and MIT for ZhaoJ9014/Anti-UAV, the `mit` source. The owner accepted the
`personal` recordings under the MIT card. Each video's terms and terms reference are in the
pilot's inventory, and the pool records the joined license per video.

The approved targets gained moving branches of trees and bushes and the sky-landscape boundary.
The two-source pilot adds six drone-dataset videos that show them, chosen by inspecting frames,
and the spec's corpus section names these strata. Because the reference changed from the record
path to `approval-2026-11-13`, both pilot plans now name it, and the pilot runs are repeated under
new run ids. Review is by one reviewer who also operates the pilot, so no audit can declare
independence; the frozen protocol says so. The approval is stated under
[source authorization](../current/corpus.md#source-authorization).

## Acceptance evidence

| Gate | Evidence | Result |
| --- | --- | --- |
| Every selected source has verifiable rights and retention | Zenodo API CC BY 4.0; dataset CSV license per video; GitHub license API CC0-1.0 and MIT; owner acceptance of `personal`; retention with no dated end | pass |
| Named owner of the approval | vola, `approval-2026-11-13` | pass |
| Approved model use and cost limits | CLIP snapshot `977e3dd0`, dinov2 commit `7764ea0f` (tree `71fce3da...`), ss-perception `75debcf` (MIT); 50 GB transfer, 300 GB storage, CPU and GPU | pass |
| Target coverage and negative cases | owner-approved strata, including branches and the sky-landscape boundary | pass; the pilot selection implements them |
| The approval has a reference every discovery plan names | `docs/impl/workloads/two-source-pilot/plan-*.yaml` name `approval-2026-11-13` | pass |
| Documentation | `make lint-md`, `make lint-doc-links`, `make lint-spec-plan` | see close |

## Audit handoff

- `AUD-authorize-video-corpus-sources-1`: the audit cannot be independent, because one reviewer
  operates the pilot and reviews links, audit and selection pass. Owner:
  `corpus-selection-evaluation`, which reports independence as declared and leaves it
  `not_declared` here; the frozen pilot protocol states it.
- `AUD-authorize-video-corpus-sources-2`: the new targets need footage in the pilot. Owner:
  `corpus-two-source-pilot`, whose task now names them; six videos were added in this change.
- About 21 GB of the 50 GB transfer cap is used; reviewer-host recreation adds about 9.8 GB.
  Recorded; no work.

## Close or resume

Accepted. The task left the plan, and its dependents no longer wait on it. The capability remains
planned.
