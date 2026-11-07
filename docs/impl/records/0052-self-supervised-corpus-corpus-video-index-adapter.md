# Corpus video index adapter

## Task and scope

- Id / capability: `corpus-video-index-adapter` / `self-supervised-corpus`
- State: accepted.
- Source: plan task; starting HEAD `c68b8a3` on branch `st-06-self-supervised-corpus`, clean tree.
- Plan counts at start: 126 tasks, 103 agent and 23 human. Next agent
  `corpus-video-index-adapter`; next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-video-index-adapter

An operator needs sibling embeddings and indexed video hints without losing source or frame identity.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: Staged frames receive pinned, auditable sibling embeddings, and optional
  ss-video matches become candidate windows that name ss-track frames.
- Scope boundary: The [integration plan](current/corpus/sibling-integration.md#integration-plan): an
  out-of-process ss-perception embedding worker over staged bundles and an optional ss-video match
  reader. No in-process sibling import, running ss-video stack, unrestricted URL crawl, network
  requirement in tests, silent source or weight download, or conversion of predictions to labels.
  A run on real sources waits for authorize-video-corpus-sources.
- Data and artifact paths: `contracts/`, `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Run the worker in a pinned environment with an explicit process environment, send
  packed frames named by `FrameRef` and key each row by bundle hash, frame index and frame hash with
  full feature provenance; feature rows get their own record contract. Write runs through
  `seal_discovery` and `write_discovery` ([discovery records](current/corpus/discovery-records.md))
  from a command that also verifies a run and reports through a `result/command` minor. Map an
  ss-video match through the `file_hash` join and the `fps` slot rule under its recorded ffmpeg
  version and sampling rate; it carries no inclusion probability, so it never enters an audit
  sample. Make `verify_discovery` recompute each `sibling_time` window from the bundle's PTS by the
  slot rule, beyond its hint-source and bounds checks. Before a run over real sources, add the
  owner's source approval reference to `record/discovery-run` as a minor and refuse a real-source
  run without it. Wrap the sibling defects the study found: a loaded `.env` changing the
  environment, progress written to standard output, `DINO_CHECKPOINT` or
  `active_checkpoint.txt` loading silently, a missing checkpoint keeping base weights, a CUDA
  out-of-memory switch to the CPU, and weights resolved from `main`. Each wrapper has a test that
  fails once the pinned release no longer shows the defect.
- Acceptance gates: Fixture worker rows map exactly to frame references; slot-rule fixtures cover a
  start offset, a source slower than the sampling rate and variable frame rate; unpinned weights, a
  set checkpoint, a device change, a multi-stream source, a missing hash join, missing timestamps,
  revisions or rights, incompatible models and partial responses are refused or reported, never
  fabricated; a sibling window that disagrees with the slot rule and a real-source run without an
  approval reference are refused; concurrent writers of one run id leave one whole run or a
  refusal, as staging does; retries are deterministic and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

New commands `ss-track discover run --plan` and `ss-track discover verify --run-id`
(`commands/discover.py`). A run reads a staged corpus version, embeds each bundle's frames with
every pinned extractor in its own worker process, maps each ss-video hint file through the hash
join and the slot rule, tiles every bundle into pool windows and draws the audit sample per
encounter group, then seals and publishes the whole run. Current state:
[discovery runs](../current/corpus/discovery-runs.md), and the updated
[discovery records](../current/corpus/discovery-records.md) and
[sibling integration](../current/corpus/sibling-integration.md) pages.

New package `corpus/siblings/`: `slots.py` (the slot rule in exact rationals), `video_hints.py`
(hint files and their mapping), `embedding.py` (worker environment, pins, batches, row checks),
`worker_process.py` (process, framing, deadlines) and `perception_worker.py`, the standalone worker
that runs under the sibling interpreter with `-I` and imports nothing from ss-track. New in
`corpus/discovery/`: `plan.py`, `pool.py`, `features.py`, `sibling_check.py` and `run.py`;
`records.py` now seals feature records and publishes a run by one rename under a lock, `reader.py`
reads feature records and vector files, and `binding.py` recomputes sibling windows and binds rows
to bundle frames. `stored.py` gains `pinned_source_record`, which reads a replaced record by its
seal. Reused: `seal_discovery`, `write_discovery`, the sealed read path, `exclusive_lock`,
`scratch_directory`, `write_atomically`, `open_corpus_bundle` and `FrameBundle.read_frame`.

Contracts frozen: `declaration/discovery-plan` 1.0.0, `declaration/video-hints` 1.0.0,
`record/feature-rows` 1.0.0, `record/discovery-run` 1.1.0 (optional `source_approval`,
`feature_rows` and hint-source `matches`, each rule on its new node because a root `x-rules`
change is major) and `result/command` 1.15.0 (discovery fields and four codes). New refusal codes
`EXTRACTOR_UNPINNED`, `EXTRACTOR_INCOMPATIBLE`, `WORKER_FAILED` and `DISCOVERY_IN_PROGRESS`. New
environment variable `SST_PERCEPTION_PYTHON`. `pyproject.toml` lists `ss_track.corpus.siblings`; no
dependency changed, so `uv.lock` is unchanged. Specification section 4.1a now states that every
discovery run names the owner's approval record.

Decisions:

- Every plan requires `source_approval`, not only real-source plans: ss-track cannot tell fixture
  media from real sources, so a conditional rule could not be enforced.
- One worker process per extractor, because the sibling settings are class attributes read once at
  import. The worker gets an explicit environment and an empty working directory; the process
  boundary, not a wrapper around an in-process import, neutralises the settings side effects.
- Weights are pinned by what the worker observed it loaded: an audit hook on Python opens and a
  wrapper on safetensors record every weight file, and each must resolve to a Hugging Face snapshot
  commit or a torch.hub tree digest. The DINOv2 hub archive records no commit, so the digest of its
  code tree is the immutable revision. Network connections are refused in the worker, so a missing
  cache fails instead of downloading from a branch.
- Batches hold `batch_size` frames and never cross a stream, so rows that depend on batch
  composition are still reproducible from the plan.
- Vectors are a little-endian float32 file sealed by its record, not JSON numbers: a JSON row of 512
  values is about 6 KB.
- An empty slot is reported as `empty_slot`, not mapped to the frame it repeats: the contract says
  a sibling window holds the frames whose time falls in its slot, and the previous slot's window
  already covers that frame.
- The audit draw ranks pool windows by SHA-256 of seed, group, stream and candidate id, so it does
  not depend on a language's random generator.
- Rejected: reading weights from local paths through `OPENCLIP_PRETRAINED`. open_clip would lose
  the `openai` tag's QuickGELU setting and produce other rows.
- Rejected: skipping locked-split streams in the adapter. Selection owns that exclusion, where the
  contract already has `operator_excluded`.

The sealed-read static scan (`tests/corpus/records/test_sealed_reads.py`) now allowlists the two
worker modules: their JSON is the inter-process protocol, and the worker reads the sibling's
`direct_url.json`; neither holds a sealed record.

The worker file is longer than the usual module size because `python -I` runs it by path with no
package around it, so it cannot be split into importable modules.

## Acceptance evidence

Run: `$DATA_DIR/self-supervised-corpus/adapter-run-20261107/`. The four sibling-study `testsrc2`
clips were staged as one corpus each, sampled by ss-perception `extract_frames` (ffmpeg 8.0.1, five
per second) into hint files, and run with the pinned CLIP and DINOv2 extractors on CPU from a
scratch Python 3.12 environment holding ss-perception `v0.2.0` (`12cb086`), torch 2.15.0+cpu and
open_clip 4.2.1. Scripts are not kept; `results/` holds the JSON records.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Fixture worker rows map exactly to frame references | `test_worker.py::test_rows_map_exactly_to_the_frame_references_sent`; `discover verify` on the four real runs | pass: keys equal the sent `FrameRef` index and hash; real rows bind to bundle frames by hash |
| Slot-rule fixtures: start offset, slower source, variable rate | `test_slots.py`; `sibling-window-crosscheck.json` | pass: 76 of 76 real windows end on the frame the JPEG shows; the 4 empty slots of the 4 fps clip repeat the previous frame and are reported |
| Unpinned weights | `test_weights_other_than_the_pinned_ones_are_refused`, `test_a_weight_with_no_immutable_revision_is_refused`; `results/unpinned-refusal.json` | pass: `EXTRACTOR_UNPINNED` lists the found revision, hash and size |
| A set checkpoint | `test_a_set_checkpoint_is_refused_before_any_worker_starts`, `test_an_active_checkpoint_file_is_refused`, `dotenv_checkpoint` case | pass |
| A device change | `no_cuda` and `oom` cases of `test_each_sibling_defect_is_refused_never_recorded` | pass: `EXTRACTOR_INCOMPATIBLE` |
| Multi-stream source, missing hash join, missing timestamps | `test_video_hints.py::test_a_match_that_names_no_window_is_counted_under_its_reason` | pass: reported under its reason, never mapped |
| Missing revisions or rights | `test_a_package_without_a_commit_is_refused`; `test_plan.py` (branch revision, no approval) | pass |
| Incompatible models | `test_an_incompatible_model_is_refused` (row length, aliased architecture) | pass |
| Partial responses | `short`, `crash` cases; `test_a_worker_that_breaks_the_protocol_is_refused` (7 lies); `test_a_slow_worker_is_stopped_at_its_deadline` | pass: `WORKER_FAILED` |
| A sibling window that disagrees with the slot rule | `test_a_sibling_window_the_slot_rule_does_not_give_is_refused` | pass: `RECORD_INVALID`, `sibling` finding |
| A real-source run without an approval reference | `test_a_plan_without_the_owners_approval_is_refused` | pass: `MANIFEST_INVALID` for every plan without one |
| Concurrent writers leave one whole run or a refusal | `test_concurrent_writers_of_one_run_id_leave_one_whole_run`, `test_a_run_id_another_command_holds_is_refused` | pass |
| Deterministic retries | `test_a_retried_plan_writes_the_same_bytes_and_changes_nothing`, `test_retries_return_the_same_rows`; real 30 fps retry | pass: real CLIP and DINOv2 rows reproduced byte for byte, status `unchanged` |
| Each wrapper fails once the pinned release loses its defect | `SST_PERCEPTION_PYTHON=... pytest tests/corpus/siblings/test_sibling_defects.py` | pass: 7 of 7 against `v0.2.0`; skipped in CI without the environment |
| Resources | `results/run-*.time` | measured: 51, 51, 13 and 36 s wall; 1.56 GB peak resident memory; GPU not measured |
| Documentation | `make lint-doc-links`, `make lint-spec-plan`, `make lint-md` | pass, 0 findings each |
| Contract evolution | `make lint-contracts` | pass: 0 findings against `origin/main` |
| Final gate | `make quality` (CI checks, tests under coverage, Markdown lint, build) | pass: 2110 passed, 7 skipped (the real-release probes without `SST_PERCEPTION_PYTHON`); coverage 93.75%. `perception_worker.py` runs in a subprocess, so coverage does not count it; `test_worker.py` exercises it |

## Audit handoff

Reviewed scope: the new and changed modules, contracts, tests, fake sibling site and documentation
of this task, and the real run.

- `AUD-corpus-video-index-adapter-1`: the worker records float32 rows only and refuses mixed
  precision, and no GPU run was measured. Nonblocking. Owner: `corpus-scale-pilot`, whose execution
  path now states the float32 or float16 choice for a GPU run.
- `AUD-corpus-video-index-adapter-2`: the adapter reads locked-split streams like any other.
  Embedding is not training, but selecting from them for review needs the custodian policy.
  Nonblocking. Owner: `corpus-ssl-selection`, which now excludes them as `operator_excluded` unless
  that policy allows them.
- `AUD-corpus-video-index-adapter-3`: the DINOv2 weight's immutable revision is a torch.hub tree
  digest, since the archive records no commit. Owner: `authorize-video-corpus-sources`, whose gate
  now names both revision forms and the approval reference each plan carries.
- `AUD-corpus-video-index-adapter-4`: the adapter ranks nothing (`unranked`, budget 0). Owner:
  `corpus-ssl-selection`, whose execution path now builds on the run's feature rows.
- Dropped: ss-video has no export of query matches joined to `processed_files.file_hash`, so an
  operator builds the hint file. That is work in the ss-video repository, handed to the user as a
  requirement; ss-track's hint contract accepts any producer and needs no further work.
- Dropped, third-party defects fixed here: the sibling settings import's `.env` loading and added
  variables, torch.hub's download lines on standard output, unrecorded and silently missing DINO
  checkpoints, `resolve_device`'s CPU fallback, the out-of-memory move to the CPU, and weights from
  `main`. Each is guarded in `perception_worker.py` and probed by `test_sibling_defects.py`.
- Fixed in this change: the sibling study attributed standard-output pollution to model loading in
  general; with cached weights nothing reaches standard output, and the source is torch.hub's
  download line. The study page now says so. The `resolve_device` fallback was not listed; it is now.
- Fixed in this change: `AUD-corpus-discovery-contract-1` to `-4` (slot rule not recomputed, no
  approval, no write lock, no command or feature contract) are resolved; the discovery records page
  no longer lists them as limits.
- Dropped: each run id leaves a small `.run-<run-id>.lock` file, as imports and staging leave theirs;
  the fixed 900 s answer deadline has no consumer that needs another. Neither needs work.

## Close or resume

Every gate passed. The new [discovery runs](../current/corpus/discovery-runs.md) page is linked
from the corpus page and the current-state index; the discovery records, sibling integration,
contracts and corpus pages and specification section 4.1a are updated. The task is removed from the
plan; `corpus-ssl-selection` drops its dependency and `corpus-review-and-freeze` drops the adapter
from its dependencies. Plan counts moved from 126 (103 agent, 23 human) to 125 (102 agent, 23
human). The next agent task is `corpus-ssl-selection`; `self-supervised-corpus` stays planned.
