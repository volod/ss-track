# corpus-source-acquisition

## Task and scope

- Id / capability: `corpus-source-acquisition` / `self-supervised-corpus`
- State: active
- Source: plan task, start commit `58b2f88`; working tree clean.
- Plan counts at start: 106 agent, 23 human; next agent `corpus-source-acquisition`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-source-acquisition

An approved source selection needs bounded, reproducible downloads without losing upstream identity.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: An operator can acquire selected authorized Zenodo and Hugging Face video
  inputs and reproduce their verified local source inventory.
- Scope boundary: Network-free fixture implementation; no real download, cloud publication, secret
  logging, unattended spending or source authorization.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `contracts/`,
  `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/import/`.
- Execution path: Support the pinned WetlandBirds v4 archive and selective Hugging Face dataset files
  at a resolved commit, preserving upstream checksums and local SHA-256, per-video terms, metadata
  and an explicit selection. Inspect pinned provider metadata to enumerate video paths and populate
  the source inventory, reporting incomplete or mismatched metadata instead of inventing it. Check
  budgets, safely extract archives, resume or refuse conflicts, and
  use optional `HF_TOKEN` from the environment without persisting it. Place scratch and cache under
  `DATA_DIR`; import remains the existing source authority. Add only justified dependencies and
  frozen contracts for new interchangeable formats.
- Acceptance gates: Offline fixtures cover both providers, metadata enumeration and mismatches,
  hashes, unsafe archive entries, interrupted and repeated acquisition, insufficient budget,
  conflicting bytes, unresolved rights, anonymous and
  authenticated access without secrets in outputs; `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

Added the internal `corpus/sources/archive.py` helper for selecting files from ZIP archives. It
checks all entry names and types, enforces a selected uncompressed-byte budget, hashes extracted
bytes and refuses conflicting destinations. Matching files can be reused. It is not connected to
an acquisition command and does not verify an upstream archive checksum itself.

The [Zenodo record](https://zenodo.org/records/15696105) lists `videos.zip` with MD5
`95eae83aceb2d12803f5f567c31060a9`. The [Hugging Face dataset card](https://huggingface.co/datasets/wayneballard/drone-detection-dataset)
describes video metadata and source links. The pinned provider API responses could not be inspected
in this session. No media was downloaded.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| ZIP extraction | `.venv/bin/pytest -q tests/corpus/sources/test_archive.py` | pass: 8 offline tests; helper only |
| Project checks | `make ci` | pass: 2285 passed, 7 skipped; does not cover the missing workflow |
| Documentation | `make lint-md` | pass |
| Acquisition and inventory | Task acceptance gates | not run: provider integrations and workflow remain unimplemented |

## Audit handoff

Pending completion of the acquisition workflow and its audit.

## Close or resume

Active. Implement provider metadata enumeration, authorization and selection, bounded downloads,
checksum verification, inventory and acquisition contracts, CLI integration, and the remaining
fixture gates. Then run the full project gate, update current documentation, audit and close this
record, and remove the completed task from the plan.
