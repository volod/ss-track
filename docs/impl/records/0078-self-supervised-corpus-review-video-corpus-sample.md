# review-video-corpus-sample

## Task and scope

- Id / capability: `review-video-corpus-sample` / `self-supervised-corpus`
- State: accepted
- Source: plan task, human lane; start commit `343ab81`, with the uncommitted review tooling of
  records 0076 and 0077 in the working tree.
- Plan counts at start: 102 agent and 22 human; next agent `corpus-selection-evaluation`, next
  human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### review-video-corpus-sample

The usefulness and missed cases of self-supervised selection require independent human judgment.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: HUMAN-GATED
- Dependencies: none.
- User-visible outcome: Reviewers adjudicate selected and independently sampled unselected material,
  including negative windows, confusers and small or uncertain birds.
- Scope boundary: A predeclared independent audit sample, grouping decisions and reviewer time; the
  existing annotation authority owns final labels and a locked set needs its custodian.
- Data and artifact paths: `$DATA_DIR/self-supervised-corpus/<run-id>/`, `$DATA_DIR/corpus/<corpus-id>/labels/`.
- Execution path: The [pilot recipe](workloads/two-source-pilot/README.md) holds the frozen
  protocol; the blinded audit packet of `pilot-audit-grouped-20261113` is presented and is reviewed
  with [`discover review-audit`](current/corpus/review-and-freeze.md#interactive-audit-review).
  Freeze the baseline and sampling plan before review; reviewers record source and
  frame decisions, uncertainty, disagreements and time, and settle them under named authority. The
  blinded audit presentation from `discover blind` records independence, blinding and effort.
  `discover unblind` maps its item decisions into one review file per run. After the audit,
  reviewers complete a [selection pass](current/corpus/review-and-freeze.md#selection-pass) of
  every selected window of each run, with minutes, using
  [`discover review-pass`](current/corpus/review-and-freeze.md#interactive-selection-pass), and
  those files are frozen with
  `corpus freeze` ([review and freeze](current/corpus/review-and-freeze.md)).
- Acceptance gates: Reviewed samples and exclusions are frozen and hashed; absent or uncertain labels
  stay unknown, unreviewed exposure is reported, and insufficient sample size is inconclusive.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: the execution path names `discover review-audit` and `discover review-pass`
  (records 0076 and 0077); nothing else changed.

## Implementation

The owner, vola, reviewed under the frozen [protocol](../workloads/two-source-pilot/protocol.md)
on 2026-11-13. The blinded audit packet of `pilot-audit-grouped-20261113` (104 windows, 13 groups,
none withheld) was reviewed with `discover review-audit`: 85 `target_present`, 15
`target_absent`, and 4 `confuser` windows excluded, 3 for `quality` and 1 as `sensitive`; no
`unknown`. The review declares `blinding: declared`, which the owner stated holds, and
`independence: not_declared`, as the protocol predeclared because the owner also operates the
pilot; 23 minutes were recorded. `discover unblind` matched every picture hash and wrote one
review per run. The owner then completed a selection pass of every selected window of each run
with `discover review-pass`: `ssl-diverse` 85 present, 5 absent, 10 confusers in 9 minutes;
`uniform` 53, 43 and 4 in 8 minutes. No pass disagrees with the audit. Total recorded review is 40
minutes of the protocol's 8-hour budget.

Each review was exported, built, staged, link-reviewed with the owner-confirmed
`link-decisions.yaml` and frozen. The reviews are committed as
`workloads/two-source-pilot/reviews/` so that another host replays the freeze, and the recipe
states the commands and the frozen identities. The current-state result is in
[Reviewed pilot](../current/corpus.md#reviewed-pilot).

| Measure | `ssl-diverse` | `uniform` |
| --- | --- | --- |
| Audit-weighted recall, 95% interval | 0.084 (0.011 to 0.157) | 0.173 (0.060 to 0.287) |
| Paired gain, 95% interval | -0.089 (-0.217 to 0.039) | |
| Drone dataset gain | -0.193 (-0.524 to 0.139) | |
| WetlandBirds gain | -0.031 (-0.120 to 0.057) | |
| Selected streams, groups | 19, 12 | 34, 11 |
| Selected windows the audit drew | 7 | 11 |
| Pass targets outside the audit | 80 | 42 |

The result is a valid negative: model-assisted selection shows no advantage over uniform
selection at a budget of 100, and its point estimate is lower. Its selection is richer in targets
per window but covers about half the streams.

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Reviewed samples and exclusions are frozen and hashed | `corpus freeze` of both versions; identities below | pass: 100 included, 4 excluded, 88 streams, 1,593 frames each; links clear, 37 unrelated |
| Absent or uncertain labels stay unknown | freeze records: `label_revision` null; observations are not labels; `target_absent` is not a verified absence | pass |
| Unreviewed exposure is reported | freeze `review.unreviewed`: 93 diverse, 89 uniform offered windows outside the audit; `discover evaluate` `review_budget` | pass |
| Insufficient sample size is inconclusive | `discover evaluate`: `estimated`, no reasons, 13 strata of 8 windows; the gain interval includes zero and is reported as no advantage, not a gain | pass |
| Freeze records reproduce the comparison | `discover evaluate --diverse-freeze --uniform-freeze`: audit and review-budget objects identical to the review-file run | pass |
| Repository gate | `make ci` | pass: 2375 passed |

Frozen identities: `pilot-frozen-diverse-20261113` manifest seal
`23c1661133058bfe986e245543d0d830b7a3cbf8eff0ac294fab0f2ea37be8a3`, frame set
`4a0f90d2e6deff401e58fe2ee603dd806bb0d5fa98419433312748f1deaba0b9`;
`pilot-frozen-uniform-20261113` seal
`bf9d9b38952abffc158b8be494e5bd93e55e698a1f434ab13fc7c204a8deccf6`, frame set
`7b1ef13e0053d3d73e6fb518d6ba06812d9a04f0fd9becafad0a807b80a1a51a`. Runtime evidence stays under
`$DATA_DIR/self-supervised-corpus/two-source-pilot-grouped-20261113/` (`reviews/`,
`reviews-audit-only/`, `frozen/`, `evaluate-reviewed.json`, `evaluate-frozen.json`) and
`$DATA_DIR/corpus/pilot-frozen-*/`. Staging each version took 45 s and 5.2 GB.

## Audit handoff

- `AUD-review-video-corpus-sample-1`: `ssl-diverse` recall is below `uniform`, and its selection
  covers 19 streams against 34. Nonblocking; owner `corpus-selection-evaluation`, whose execution
  path now names the reviewed pilot as its input and requires explaining the gap by stream and
  group coverage against ranking.
- `AUD-review-video-corpus-sample-2`: independence is not declared, because the owner both
  operates the pilot and reviews it. Dropped: the protocol predeclared it, every result states it,
  and no claim of independent review is made.
- `AUD-review-video-corpus-sample-3`: the two frozen versions hold the same membership under
  different frame-set identities, one per run. Dropped: an observation; each freeze binds its own
  run and pass, as designed.
- `AUD-review-video-corpus-sample-4`: the pool's 70 GB of staged frames remain. Dropped as work
  here: verification of both runs reads them, and `corpus-scale-pilot` already measures keeping a
  pool's frames until its versions are frozen; they are releasable with `data clean --kind
  staged-frames` when no later task reads the runs.

## Close or resume

Accepted. The task left the plan; `corpus-selection-evaluation` and `corpus-scale-pilot` drop the
dependency, and the empty human-lane group heading was removed. The capability stays planned with
those two tasks open. Plan counts after: 102 agent and 21 human; next agent
`corpus-selection-evaluation`, next human `define-locked-test-policy (optional)`.
