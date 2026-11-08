# corpus-selection-evaluation

## Task and scope

- Id / capability: `corpus-selection-evaluation` / `self-supervised-corpus`
- State: active
- Source: plan task; start commit `e6623c7`; working tree clean.
- Plan counts at start: 99 agent, 23 human; next agent `corpus-selection-evaluation`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-selection-evaluation

A larger selected pool may conceal missed small birds or exclude hard negatives.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: A report compares model-assisted selection with a random or uniform
  baseline and exposes missed cases and resource cost at a matched review budget.
- Scope boundary: Independently reviewed audit samples and stratified uncertainty; no field accuracy,
  generalization or verified species claim from model proposals alone.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Define a reproducible evaluation protocol before running, score reviewed random
  samples including unselected material, and report diversity, negatives, recall, cost and exclusions.
  Read each window's reviewed observation from its `declaration/corpus-review` or freeze record
  ([review and freeze](current/corpus/review-and-freeze.md#decisions)); `unknown` and unreviewed
  windows count as unknown, never as absent.
  Compare `ssl-diverse` with the `uniform` run of the same pool and audit seed
  ([selection](current/corpus/discovery-runs.md#selection)), report misses by kind, including a
  target present for a whole stream, which background deviation compares against itself, and
  confusers that motion ranks high.
- Acceptance gates: Hand-calculated fixtures verify denominators, sampling weights, uncertainty and
  unavailable strata; empty or insufficient evidence produces an explicit inconclusive result.
  Negative gains remain valid and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendment: at the user's request, split prerequisite acquisition, blinded review and the two-source
  pilot into separate tasks; the remaining evaluation requires that pilot and independent review,
  and reports per-source as well as combined evidence. Revised task:

```markdown
#### corpus-selection-evaluation

A larger selected pool may conceal missed small birds or exclude hard negatives.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: RUN NEEDED
- Dependencies: corpus-two-source-pilot, review-video-corpus-sample, corpus-evaluation-by-source.
- User-visible outcome: A report compares model-assisted selection with a random or uniform
  baseline and exposes missed cases and resource cost at a matched review budget.
- Scope boundary: Independently reviewed audit samples and stratified uncertainty; no field accuracy,
  generalization or verified species claim from model proposals alone.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Define a reproducible evaluation protocol before running, score reviewed random
  samples including unselected material, and report diversity, negatives, recall, cost and exclusions.
  Read each window's reviewed observation from its `declaration/corpus-review` or freeze record
  ([review and freeze](current/corpus/review-and-freeze.md#decisions)); `unknown` and unreviewed
  windows count as unknown, never as absent.
  Compare `ssl-diverse` with the `uniform` run of the same pool and audit seed
  ([selection](current/corpus/discovery-runs.md#selection)), report misses by kind, including a
  target present for a whole stream, which background deviation compares against itself, and
  confusers that motion ranks high. Record whether the audit review was independent and blinded;
  the current review format does not record either. Capture measured compute cost alongside the
  comparison; discovery runs do not record it. Report per-source estimates and accounting as well
  as the explicitly weighted combined population, without implying field prevalence.
- Acceptance gates: Hand-calculated fixtures verify denominators, sampling weights, uncertainty and
  unavailable strata; empty or insufficient evidence produces an explicit inconclusive result.
  Negative gains remain valid and `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

## Protocol defined before evaluation

Compare verified `ssl-diverse` and `uniform` discovery runs of the same sealed pool and frame set,
window partition, audit seed and per-stratum draw, and requested selection budget. Require matching
actual selected counts for a matched budget; report unequal counts as inconclusive. Validate each
review against the offered queue and its run. Match observations by pool stream and window; refuse
conflicting reviewed observations rather than selecting one. Audit observations must come from the
independent audit draw, including windows selected by neither method. Reviewers should inspect
audit windows independently and without method or score information; record whether this was done.
Exclude sibling windows from population estimates; never assign them sampling weights. Report the
number of unique windows reviewed across both
queues as well as each method's selections, audit overlaps, exclusions and recorded run costs;
missing resource measurements remain unavailable, not zero.

For stratum h, population N_h and audit sample n_h, weight each observed audit window N_h/n_h.
Estimate totals of target-present, target-absent, confuser and unknown windows and target-present
selected by each method with those weights. Estimated recall is the weighted selected-target total
divided by the weighted target total; a zero denominator is inconclusive. Show the sample counts,
weights, and per-stratum totals. Unknown, unreviewed and withheld windows are unknown, not absent;
when any sampled observation is unknown, suppress population recall and gains rather than infer a
missingness mechanism. A stratum with no draw is unavailable. For complete strata with n_h >= 2,
estimate variance of a total using N_h squared times (1 - n_h/N_h) times sample variance divided
by n_h; census strata have zero variance even for n_h = 1. For recall and the paired recall
difference, use the delta method on the per-window numerator minus estimated ratio times target
indicator, summing independent stratum variance contributions. Report a normal 95% interval as an
approximation, bounded to the feasible range, and mark uncertainty unavailable for non-census
strata with fewer than two samples. Require enough evidence to estimate the interval before calling
the comparison conclusive. Negative gains remain valid. Report observations and misses by stream
and available declared kind, without inventing species or case classifications, and explicitly
show whole-stream target and high-motion confuser cases when the reviewed data identifies them.
Diversity is descriptive coverage of distinct streams and groups among selected and reviewed
windows, not a claim of ecological diversity.

## Implementation

Implemented `discover evaluate`, its validated review and freeze readers, paired selection report,
and stratified finite-population estimator under `corpus/evaluation/`. The command reports
observation-level selection and motion ranks, whole-stream observations, sampling weights, recall,
paired gain, uncertainty and incomplete evidence. See [discovery runs](../current/corpus/discovery-runs.md#evaluating-selection).
Review independence, blinding and compute cost are not captured by existing records and are
explicitly unavailable. Added the new package to the explicit wheel package list.
The task remains open pending the reviewed evaluation run and completion audit.

## Work remaining

Run the evaluator on independently reviewed samples, report results and resource measurements,
complete the per-change audit, and remove this task only after all acceptance gates pass.

## Acceptance evidence

Focused tests: `.venv/bin/pytest -q tests/corpus/evaluation tests/corpus/discovery/test_selection_run.py
 tests/corpus/review/test_freeze.py` passed (28 tests). These cover weighted estimates, paired
uncertainty, missing observations, negative gains, matched discovery reviews, conflicting observations,
locked material and freeze inputs. `make lint` and `make typecheck` passed. The reviewed real-footage
evaluation is not run. The first `make ci` found the missing wheel package, fixed in the same
change; `pytest tests/test_packaging.py` then passed. The full `make ci` rerun passed: 2265 passed
and 7 skipped.

## Audit handoff

The blinded review is owned by `corpus-blinded-audit-review`; resource measurements and paired
runs are owned by `corpus-two-source-pilot`. `corpus-evaluation-review-budget` owns the unequal
review workload bug, and `corpus-evaluation-by-source` owns source-specific metrics. The reviewed
analysis remains owned by `corpus-selection-evaluation`. No sibling-repository requirement
has been established.

## Close or resume

In progress. Run the reviewed evaluation after its pilot and human-review dependencies.
