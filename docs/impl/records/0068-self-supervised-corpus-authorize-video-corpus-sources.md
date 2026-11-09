# authorize-video-corpus-sources

## Task and scope

- Id / capability: `authorize-video-corpus-sources` / `self-supervised-corpus`
- State: active
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

## Acceptance evidence

Pending.

## Audit handoff

Pending.

## Close or resume

In progress.
