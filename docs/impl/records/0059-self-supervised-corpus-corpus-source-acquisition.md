# corpus-source-acquisition

## Task and scope

- Id / capability: `corpus-source-acquisition` / `self-supervised-corpus`
- State: accepted
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

Added `discover acquire`, the `corpus/sources/acquisition*`, `provider_*` and `zenodo_splits`
modules, the ZIP safety helper and the frozen `record/source-acquisition` 1.0.0 through 1.3.0.
The operator selects one pinned collection, candidate video paths, optional Hugging Face metadata
files, two byte budgets and an explicit authorization assertion. The command enumerates provider
files, checks selected rights evidence and upstream identities, verifies the bytes and records their
local SHA-256, preserves selected metadata and terms, and counts unknown inventory facts. It joins
verified Zenodo split metadata, rejects mismatches, keeps scratch under the data root and verifies
or refuses existing files. A killed run's scratch is cleared by the next lock holder. `HF_TOKEN`
is not persisted and is stripped from cross-host redirects. Import remains the recording authority.
No dependency or sibling interface changed. See [current corpus](../current/corpus.md#source-acquisition).

The [Zenodo record](https://zenodo.org/records/15696105) lists `videos.zip` with MD5
`95eae83aceb2d12803f5f567c31060a9` and exposes video paths and split metadata. The
[Hugging Face dataset card](https://huggingface.co/datasets/wayneballard/drone-detection-dataset)
describes per-video metadata and source links. Provider media was not downloaded; pinned network
requests are tested with offline fixtures, not a real account or live source.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Providers, metadata, rights, budget, hashes, replay and security | `.venv/bin/pytest -q tests/corpus/sources/test_acquisition.py tests/corpus/sources/test_acquisition_edges.py tests/corpus/sources/test_archive.py` | pass: network-free fixtures |
| Fixture CLI runs and replay | `.venv/bin/python -m tests.corpus.sources._acquisition_fixture` | pass: fixture artifacts at `$DATA_DIR/self-supervised-corpus/acquisition-zenodo-fixture-v2-20261108/` and `$DATA_DIR/self-supervised-corpus/acquisition-hf-fixture-v2-20261108/` |
| Contract example and provider parsing guard | `.venv/bin/pytest -q tests/schema/registry/test_baseline.py tests/schema/registry/test_check.py tests/corpus/records/test_sealed_reads.py` | pass in focused runs |
| Required project gate | `make ci` | pass: 2309 passed, 7 skipped |
| Documentation | `make lint-md` | pass |

## Audit handoff

- `AUD-corpus-source-acquisition-1`: selected Hugging Face YAML and source-link files are stored
  and verified but not parsed or joined to videos. Their association and rights evidence can remain
  unresolved, so source-specific attribution may be incomplete. The dataset card describes these
  files; the network-free metadata fixture reproduces preservation. Owner: `corpus-combined-pool`,
  which now requires evidence-backed association and visible missing or mismatched links.
- Fixed: provider JSON parsing now rejects duplicate keys and non-finite values, with a restricted
  metadata-only exception to the sealed-record parsing guard.
- Fixed: interrupted runs now reserve their input and selection before network access, preventing
  a different selection from reusing partial artifacts.
- Fixed: fixture ZIPs originally included creation timestamps, causing a replay in a later process
  to appear conflicting. Fixture entries now use fixed timestamps.
- Dropped: no related repository change is needed for this acquisition boundary; no ss-video or
  ss-fusion interfaces are invoked.

## Close or resume

All acceptance gates passed. The task has been removed from the plan and the current corpus and
contracts pages describe the shipped behavior. The plan has 105 agent and 23 human tasks; the next
agent task is `corpus-combined-pool` and the next human task is `define-locked-test-policy (optional)`.
The `self-supervised-corpus` capability remains planned.
