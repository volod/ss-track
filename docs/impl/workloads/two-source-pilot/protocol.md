# Two-source pilot review protocol

Frozen before `discover blind`. It changes only in a new pilot run with a new protocol file.

## Runs compared

- `pilot-diverse-grouped-20261113` (`ssl-diverse` over `clip-b16-tiles.deviation` and `motion`)
  and `pilot-uniform-grouped-20261113` (`uniform`, seed 3), both over corpus
  `pilot-two-source-grouped-20261113`.
- Both runs use 16-frame pool windows, audit seed 7 with 8 windows per encounter group, and a
  budget of 100 selected windows. These settings are fixed across hosts. Device and batch size are
  per host and are recorded in the run.

## Preconditions

1. `discover verify` passes for both runs on the host that presents the audit.
2. The link review is applied. The owner delegated it to Claude, which decided 66 of the 148
   flagged pairs of `pilot-two-source-20261113` from frames and burned-in camera overlays:
   8 related and 58 unrelated (`link-decisions.yaml`). The 82 same-source pairs whose
   session the frames cannot establish stay undecided; the pool groups each such source as an
   operator choice, so the grouped version has 13 groups and no cross-group link is undecided.
   A different grouping is a new version and needs both runs again, because the audit is
   stratified by group.
3. Recordings whose provenance cannot be established are reported with the result; they are not
   treated as independent of the recordings their link review flagged.

## Audit

- One shared blinded audit: `discover blind --audit-id <id> --run-id pilot-diverse-grouped-20261113
  --run-id pilot-uniform-grouped-20261113`. The reviewer sees only the packet, not the queue templates,
  scores, methods or selection.
- The approved reviewer, vola, also operates the pilot and reviews links, audit and selection
  passes within 8 hours in total. The audit therefore states `independence: not_declared`.
- The reviewer records `reviewer_minutes`, and declares `blinding` only when it holds: the audit is
  reviewed before opening any queue template, selection or score of either run. Otherwise it states
  `blinding: not_declared`.
- Observations are `target_present`, `target_absent`, `confuser` or `unknown`. Uncertain windows
  are `unknown`; `target_absent` is not a verified absence.
- `discover unblind` maps the decisions to one review per run. The audit observations are the only
  input to the population estimate.

## Selection pass

- After the audit, a reviewer completes the selection pass of every selected window of each run,
  from the commented block `discover queue` writes, with minutes. Windows the audit already showed
  are reviewed again.
- Pass findings are reported as each run's review yield. They never enter the estimate, and a
  disagreement with the audit is listed, not resolved.

## Reporting

- Report each collection's estimates and the weighted combined population as `discover evaluate`
  computes them, with withheld exposure, unreviewed windows and missing evidence.
- An insufficient sample, incomplete pass or unresolved grouping is an inconclusive result, not a
  gain or a loss.
- No result is a field-prevalence, species or detection claim.
