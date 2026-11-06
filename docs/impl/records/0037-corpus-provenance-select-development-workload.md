# Select development workload

## Task and scope

- Id / capability: `select-development-workload` / `corpus-provenance`
- State: accepted; the owner accepted the selection and all required gates passed.
- Source: plan task; starting HEAD `d20d0e2`. Existing unrelated changes to corpus staging and
  tests were present; the record index also included the staging-single-pass record at preparation.
- Plan counts at start: 127 total, 105 agent and 22 human. Next agent:
  `bundle-frame-sharing`; next human: `select-development-workload`.
- Accepted task: original plan text, copied verbatim below.

```markdown
#### select-development-workload

Software development needs authorized footage with a declared task and useful negative cases.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: HUMAN-GATED
- Milestone: M1
- Dependencies: none.
- User-visible outcome: One candidate workload has recorded terms, and the owner knows how close it
  is to the small-target stress case.
- Scope boundary: Authorized private or public development sources, benchmarking rights, retention and
  access restrictions. Public redistribution is a separate permission, never a G0a prerequisite.
- Data and artifact paths: `$DATA_DIR/corpus/<corpus-id>/`, with source terms and hashes.
- Execution path: The owner checks source terms and selects positive/negative encounters; original
  controlled recordings are an alternative when no existing source fits.
- Acceptance gates: Every source has recorded rights, a retention date, a derived-frame permission and
  task suitability. With no authorized source,
  real-data claims remain unavailable while fixture implementation continues.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

The owner accepted the proposed workload and artifacts. The selected class is bird of prey, with a
candidate negative and positive window from one edited recording in a single development group.
The source is [Hawk attacks drone](https://commons.wikimedia.org/wiki/File:Hawk_attacks_drone.webm)
by Michael deAgonia; the file page states [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
Attribution, license link, and change indication are required. Source authority and terms were
presented for owner review. Retention has no stated calendar end; generated derived frames are
permitted and the project corpus is restricted. Species remains uncertain. The airborne scene and
approaching bird exercise tracking under camera motion, but the bird grows large and object extent,
range, optics, and control are unknown. This selection cannot establish small-target performance.

`make development-workload-prepare` downloads and checks the pinned source, copies checked-in
recording and corpus declarations, and creates a contact sheet at
`$DATA_DIR/workload-selection/hawk-drone-pilot/`. Existing source or declaration conflicts refuse
without overwriting. `src/ss_track/corpus/sources/pilot_workload.py` owns preparation;
`docs/impl/workloads/hawk-drone/` holds the declarations. The media SHA-256 is
`85534498c6a3422f13e17a02042e47ac3df414cbc8df58050a92bc62f3394e6c`.
The source has 855 decoded frames. Candidate negative frames `[0, 168)` and positive frames
`[432, 552)` are one development group. The initial contact-sheet survey sampled once per second;
it does not prove absence on every frame. Pilot labeling owns the full review, uncertainties, masks,
and frozen labels. [Current corpus documentation](../current/corpus.md#selected-development-workload)
covers usage and limits.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Owner approval and rights | Owner accepted review package; Commons source page and license above | Accepted candidate, restricted handling, retention date explicitly null, derived frames allowed |
| Task suitability | Original video and one-frame-per-second contact sheet | Positive and negative candidates selected; full-frame negative review belongs to labeling |
| Recreate after clone | `make development-workload-prepare` | Downloaded and pinned 28.5 MiB source; second run reused matching files; a custom `DATA_DIR` recreated the contact sheet |
| Refuse local conflicts | `.venv/bin/python -m pytest tests/corpus/sources/test_pilot_workload.py -q` | Four network-free cases passed, including mismatched bytes, declarations and interrupted sheet creation |
| Corpus identity | `.venv/bin/ss-track import --source .data/workload-selection/hawk-drone-pilot/recording.yaml` | Imported; source hash above, 855 frames |
| Corpus build | `.venv/bin/ss-track corpus build --manifest .data/workload-selection/hawk-drone-pilot/corpus.yaml` | Built `hawk-drone-pilot-v1`, one group and two streams |
| Frame staging | `.venv/bin/ss-track corpus stage --corpus hawk-drone-pilot-v1` | Staged 168 negative and 120 positive frames; frame set `209a49b4fd30deeaffe24ca46c446948bd1ba7fefb532f02f33182ed17bf8dd4` |
| Integrity and rights | `.venv/bin/ss-track corpus verify --corpus hawk-drone-pilot-v1` | Verified frame set and recorded terms |
| Documentation and planning | `make lint-doc-links lint-spec-plan` | Passed |
| Required CI | `make ci` | Passed: 1724 tests; four third-party deprecation warnings |

## Audit handoff

- Full-frame negative absence and uncertain labels: `label-pilot-encounters` explicitly owns frame
  review and unknown labels. A one-per-second survey cannot establish target absence.
- Species, range, camera parameters, and pixel extent are unknown. These facts limit the claims for
  this particular workload; the current corpus page states the limitation. There is no unsupported
  species or range claim and no new work is required for this pipeline pilot.
- The two encounters are not independent. The development-corpus labeling task already requires
  independent groups; this pilot makes no generalization or held-out claim.

## Close or resume

Owner accepted the candidate. Plan counts changed from 127 (105 agent, 22 human) to 126 (105 agent,
21 human); no capability status changed. The selection task was removed and its dependent tasks were
updated. Current corpus documentation and the records index link this record. `make ci` and the
required documentation and planning checks passed.
