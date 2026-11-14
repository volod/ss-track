# corpus-portable-link-review

## Task and scope

- Id / capability: `corpus-portable-link-review` / `self-supervised-corpus`
- State: accepted.
- Source: plan task; start commit `fee90ccc44c60f4aa3138cf9629186e14d9ec5bb`; clean
  tracked worktree.
- Plan counts at start: 105 agent and 24 human tasks; next agent
  `corpus-portable-link-review`, next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-portable-link-review

Reviewing on another computer currently requires manually assembling matching source media,
sealed records, software and checkpoint files. A missed file, changed byte or concurrent copy can
prevent review or silently replace a reviewer's decisions.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: An operator prepares a minimal verified review handoff, runs and resumes it
  on another host, and returns the decisions without silently overwriting work.
- Scope boundary: Local portable artifacts and explicit operator-controlled transfer; no remote
  credentials, unattended network transfer, rights grant, publication, distributed locking,
  automatic adjudication or changes to the blinded window audit.
- Data and artifact paths: `src/ss_track/corpus/links/`, `src/ss_track/commands/`, `contracts/`,
  `tests/corpus/links/` and `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Define and freeze any new interchange contract, export the required corpus and
  link records, source records and permitted media plus any existing checkpoint, and verify their
  identities and terms when importing into an isolated data root. Provide an explicit return path
  for reviewer decisions that detects stale, divergent or conflicting local checkpoints, retains
  uncertainty, and never silently merges or overwrites review work. Document installation, transfer,
  resume, return and recovery on two hosts.
- Acceptance gates: Network-free tests round-trip an interrupted review between two data roots and
  feed returned decisions to `discover links`; omitted, corrupted, expired, unauthorized and
  conflicting inputs are refused without changing existing decisions. The handoff excludes unrelated
  staged frames and model weights, exposes transfer size, and `make ci` passes.
- Documentation target: [Leakage review](current/corpus/leakage-review.md#review-on-another-host).
```

- Amendment: the owner required every host to create the dataset locally and independently, rather
  than reconstructing it by copying media from another host. The portable archive carries creation
  inputs, identity evidence and checkpoint state but excludes source media and staged frames. Local
  staged-hash records are compared before review work is accepted.

```markdown
#### corpus-portable-link-review

Reviewing on another computer currently requires manually copying matching media and records, while
locally reconstructed datasets can differ without an acceptance check and concurrent checkpoint
copies can silently replace decisions.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: Every authorized host independently creates the same pinned local dataset,
  compares it with another host's sealed identities, resumes review and returns decisions without
  silently overwriting work.
- Scope boundary: Media-free portable artifacts and explicit operator-controlled transfer; no remote
  credentials, dataset transfer, unattended network transfer, recipe execution, rights grant,
  publication, distributed locking, automatic adjudication or changes to the blinded window audit.
- Data and artifact paths: `src/ss_track/corpus/links/`, `src/ss_track/commands/`, `contracts/`,
  `tests/corpus/links/` and `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Freeze a media-free handoff contract; export operator-selected text creation
  inputs, the sealed link record, staged-hash evidence and any checkpoint. Each receiving host uses
  existing acquisition, pool, import, build and stage commands against its own data root, then
  compares its complete staged identities before accepting review state. Return reviewer decisions
  with their checkpoint branch point and refuse stale, divergent or conflicting local work.
- Acceptance gates: Network-free tests independently build the same corpus in two data roots,
  round-trip an interrupted review and feed returned decisions to `discover links`; omitted,
  corrupted, expired, unauthorized, different-dataset and conflicting inputs are refused without
  changing existing decisions. The handoff excludes source media, staged frames, feature rows and
  model weights, exposes transfer size, and `make ci` passes.
- Documentation target: [Leakage review](current/corpus/leakage-review.md#review-on-another-host).
```

## Implementation

Added `discover review-pack`, `review-unpack` and `review-accept`. A pack verifies the local corpus,
writes a standard staged-hash record, and creates a deterministic tar containing only the sealed
link record, staged-hash evidence, optional checkpoint and operator-selected text recipe inputs.
Known media and weight file extensions are refused as recipes. The command reports the exact tar
size. Unpack verifies the archive seal, member hashes, fixed paths and expiry before extracting only
recipe inputs; it requires `--authorized` and never executes a recipe.

Accept verifies the archive's link and staged-hash records, verifies the complete independently
created local corpus, and uses the existing host-hash comparator. It installs link and checkpoint
state only after an identical result. The accepted manifest retains the checkpoint branch point;
returning work replaces a local checkpoint only when it is unchanged from that point or already
equals the return. Divergence is `IMPORT_CONFLICT` and leaves decisions untouched. Missing, damaged,
expired, unauthorized, different-corpus and occupied-run inputs refuse before review state changes.

The implementation is split across `corpus/links/portable_archive.py`, `portable_state.py`,
`portable.py` and `portable_accept.py`; CLI routing remains in `commands/discover.py`. The new frozen
`record/link-review-handoff` 1.0.0 contract seals the archive inventory and identities. No dependency,
environment variable, result-command contract or package API changed. The specification and
[leakage review](../current/corpus/leakage-review.md#review-on-another-host) now require independent
local acquisition instead of media transfer. The historical manual-transfer record remains history.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Independent two-root round trip and returned decisions | `tests/corpus/links/test_portable.py::test_interrupted_review_round_trips_between_independent_data_roots` | pass: both roots imported and staged the same source bytes independently; returned checkpoint produced a clear new link run |
| Omitted, corrupted, expired and unauthorized inputs | `tests/corpus/links/test_portable.py::test_unauthorized_expired_and_corrupt_archives_are_refused` | pass; no review run was created by the unauthorized attempt |
| Different local dataset and conflicting checkpoint | `test_different_local_dataset_is_refused_before_review_state_changes`, `test_divergent_return_never_changes_existing_decisions` | pass: frame corruption and checkpoint divergence refused; existing decision bytes stayed unchanged |
| Media-free contents and transfer size | `$DATA_DIR/self-supervised-corpus/portable-hawk-review.tar`; `discover review-pack` and `review-unpack` | pass: 51,200 bytes; two YAML recipes plus link and staged-hash records; no media, frames, feature rows or weights |
| Real local comparison | `discover review-accept --archive $DATA_DIR/self-supervised-corpus/portable-hawk-review.tar --identity-run portable-hawk-local --comparison-run portable-hawk-compare --reviewer Reviewer --authorized` | pass: `identical`, comparison record under `$DATA_DIR/run/portable-hawk-compare/` |
| Frozen contract and example | `make lint-contracts`; `tests/schema/registry/test_baseline.py`, `test_agreement.py` | pass: 0 contract-evolution findings; real manifest example validates |
| Required project gate | `make ci` | pass: 2,319 tests passed, 112 deselected; format, lint, typing, complexity, shell, docs, plan and contracts passed |
| Documentation | `make lint-md`, `make lint-doc-links`, `make lint-spec-plan` | pass: no findings |

## Audit handoff

- `AUD-corpus-portable-link-review-1`: the exact 31-video pilot inventory and acquisition command
  recipe lived only under the former host's data root, so this checkout cannot independently
  reacquire that historical selection yet. The generic media-free flow and fixture evidence are
  complete, but the real pilot still needs its public recipe. Owner: `corpus-two-source-pilot`, whose
  task now explicitly requires publishing the pinned inventory, selections, commands, byte limits
  and pool declaration and recreating the identities from a fresh authorized data root.

## Close or resume

Accepted. All gates passed. The task left the plan; 104 agent and 24 human tasks remain. The next
agent task is `corpus-two-source-pilot`; the next human task is
`define-locked-test-policy (optional)`. The capability remains planned.
