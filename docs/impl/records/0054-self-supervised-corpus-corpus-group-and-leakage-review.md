# Corpus group and leakage review

## Task and scope

- Id / capability: `corpus-group-and-leakage-review` / `self-supervised-corpus`
- State: accepted.
- Source: plan task; starting HEAD `33ad4ae` on branch `st-06-self-supervised-corpus`, clean tree.
- Plan counts at start: 124 tasks, 101 agent and 23 human. Next agent
  `corpus-group-and-leakage-review`; next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### corpus-group-and-leakage-review

Related recordings and visually similar copies can leak across splits and exaggerate evidence.

- Serves: `self-supervised-corpus` -- [Video corpus formation](../design/spec.md#41a-self-supervised-video-corpus-formation)
- Agent status: CLEAR
- Dependencies: none.
- User-visible outcome: Reviewers see likely related video and keep related encounters together.
- Scope boundary: Source and exact frame checks plus flagged embedding or perceptual candidates;
  final grouping decisions remain human-owned, and a similarity threshold is not ground truth.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/self-supervised-corpus/<run-id>/`.
- Execution path: Reuse existing corpus grouping and duplicate checks, add reviewable candidate
  links and reject known cross-split leakage on export.
- Acceptance gates: Fixtures cover remuxed and related recordings, unrelated lookalikes and an
  unresolved conflict; known leakage is refused and uncertain matches are exposed, not silently
  merged. `make ci` passes.
- Documentation target: [Corpus](current/corpus.md).
```

- Amendments: none.

## Implementation

`ss-track discover links` writes one link review of a staged corpus version (current state:
[leakage review](../current/corpus/leakage-review.md)). It first reuses the checks that already
refuse known leakage: `require_separate_sources` (one source or file per group) and
`require_unshared_frames` (no run of identical frames across groups, over the version and its
chain), so a remux in another group is `SPLIT_LEAKAGE` here as at stage. It then flags pairs of
streams in different groups with the build's `luma-grid-16` fingerprint, restricted to the version,
and, given a discovery run over the same frame set, with `background-cosine`: per plan extractor,
the mean cosine over tile positions of each stream's unit-mean feature row. Flags and reviewer
decisions become links between pairs of recordings; a `related` decision across groups refuses the
version as `SPLIT_LEAKAGE`, an undecided link is written `unresolved`, and nothing merges a group.

New package `corpus/links/`: `decisions.py` (the decisions reader), `evidence.py` (both methods and
the threshold table), `review.py` (links and the related-pair refusal), `run.py` (checks, seal and
publish), `records.py` (`read_links` with the record's rules) and `result.py`. `near_duplicates.py`
gains `version_near_duplicates`, and its pair exposes its stream ids and rounded similarity, so the
review reuses the build's fingerprint instead of a second implementation. The discovery publish lock
name moved to `storage/layout.py`, which both writers now share, with the new `links_path`.

Contracts frozen: `declaration/link-decisions` 1.0.0, `record/corpus-links` 1.0.0 and
`result/command` 1.17.0 (`links`). `pyproject.toml` lists `ss_track.corpus.links`; no dependency
changed. Specification section 4.1a states the review's boundary.

Decisions:

- A decision names two source identities, not a corpus version, so it carries over to the version
  that fixes the grouping; a decision whose sources the version does not both hold, or whose group
  already holds both, is listed with its reason rather than dropped.
- A related decision refuses in one split or two, as the build does for one source in two groups:
  a group is the unit of independence, and two related groups also exaggerate group counts.
- An undecided link is written, not refused: the reviewer needs the record to decide, and refusing
  an unresolved link across splits is the freeze's rule, which its plan task now states.
- Thresholds are keyed by architecture and crop. One global value cannot work: CLIP placed every
  measured pair between 0.53 and 0.99 and DINOv2 between -0.01 and 0.96. An unmeasured backbone is
  `no_threshold`, never guessed. Each threshold sits at or below the least similarity of two windows
  of the real recording, so recall of related pairs is preferred over false flags, which cost a
  reviewer's decision.
- The review needs a finished stage; the shared-frame check runs before the frame-set check so that
  a version stage refused for leakage is refused for leakage here too.
- Rejected: merging groups automatically from a score, a ranked top-k per stream (always flags,
  however unrelated), and a model-agnostic rule relative to each stream's own split-half
  similarity, which flags nothing on a static camera.

## Acceptance evidence

Run: `$DATA_DIR/self-supervised-corpus/links-eval-20261107/`: 13 clips (four windows and an x264
copy of the real hawk-and-drone flight, four synthetic skies of one generator, four unrelated
synthetic scenes), staged as `links-eval-v1` with each clip its own group and one hawk window in the
locked split, embedded at every eighth frame by the pinned CLIP ViT-B/16 and DINOv2 ViT-B/14, each
centre-cropped and in a 4 by 2 grid. `results/scripts/` holds the media, corpus, pair-summary and
decision scripts; `results/background-pairs.json` the per-pair similarities.

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Fixtures cover remuxed recordings | `test_a_remux_in_another_group_is_refused_as_known_leakage` | pass: `SPLIT_LEAKAGE` with the shared run, after stage refused |
| Fixtures cover related recordings | `test_a_related_decision_across_groups_refuses_and_writes_nothing`, `test_a_related_decision_across_groups_refuses_in_one_split_or_two`; real run | pass: 9 of 9 related hawk pairs and the copy flagged by every extractor; the related decisions refused as `SPLIT_LEAKAGE` naming 10 links |
| Fixtures cover unrelated lookalikes | `test_a_lookalike_across_splits_is_written_unresolved_...`, `test_an_unrelated_decision_clears_the_review`; real run | pass: 6 of 6 sky lookalikes flagged and resolved `unrelated`; an unrelated scene is not linked in the fixture; 1 to 3 of 62 unrelated real-run pairs flagged per extractor, all test patterns |
| Fixtures cover an unresolved conflict | `test_an_undecided_flag_across_splits_is_an_unresolved_link_...`; real run | pass: undecided links written `unresolved`, 4 across splits counted in `unresolved_cross_split` |
| Known leakage is refused | remux and related-decision tests above, `test_a_version_never_staged_is_refused`, `test_a_version_whose_staging_never_finished_is_refused` | pass: nothing written on refusal |
| Uncertain matches exposed, not silently merged | `test_review.py`, `test_links_run.py`; real `links-eval-review` | pass: 19 links written, every group kept as declared |
| Regrouping clears the review | `links-eval-v2` (hawk windows in one group) with the full decisions file, with `--features links-eval-features-v2` and without | pass: `clear` both ways, 9 `unrelated` links, 10 decisions `same_group` |
| Reproducible record | `test_the_same_review_again_is_unchanged_...`; `read_links` tests | pass: retry `unchanged`; forged status and link fields `RECORD_INVALID` |
| Background cosine | `test_evidence.py` against hand-calculated rows | pass: tile averaging, unit mean, threshold boundary, `no_threshold`, `no_feature_rows` |
| Resources | `results/links-review.err`; `results/run-features.err` | measured: review 12 s, 92 MB peak; embedding 9 min 53 s, 1.56 GB peak on this host's CPU |
| Contract evolution | `make lint-contracts` | pass, run in the `corpus-review-and-freeze` change with this code unchanged |
| `make ci` passes | `make ci` | pass, run in the `corpus-review-and-freeze` change with this code unchanged |

## Audit handoff

Reviewed scope: the new package, the near-duplicate and layout changes, the three contracts, tests,
documentation and the real run.

- `AUD-corpus-group-and-leakage-review-1`: the `background-cosine` thresholds rest on one real
  recording and synthetic scenes, and CLIP's centre-crop margin was 0.002. A related pair below a
  threshold, such as two sessions of one site in other light, is not flagged. Nonblocking: a flag
  only asks. Owner: `corpus-scale-pilot`, whose execution path now measures the thresholds on
  reviewed pilot pairs and the grid it chooses, and revises the table under a new revision.
- `AUD-corpus-group-and-leakage-review-2`: a review covers one version, so a recording related to
  one held in another split of a superseded version is not seen. Owner: `corpus-review-and-freeze`,
  whose execution path now applies the decisions across the versions the frozen one supersedes.
- `AUD-corpus-group-and-leakage-review-3`: an unresolved link across splits is written, not refused.
  Owner: `corpus-review-and-freeze`, whose execution path now reads the review with `read_links`,
  binds it to the frozen manifest and frame set and refuses such a link.
- `AUD-corpus-group-and-leakage-review-4`: background cosine is a rounded matrix product, so a pair
  at a threshold could flip on another host, and the fingerprint's pairwise Python loop grows with
  the square of the stream count. Owner: `corpus-scale-pilot`, which now repeats the review on its
  second host and times both at its stream count.
- Dropped: ss-perception names its DINOv2 models `dinov3_*`, which the
  [sibling study](../current/corpus/sibling-integration.md) records. The table keys on the name a run
  records, and a renamed architecture becomes `no_threshold`, so no sibling change is needed.
- Dropped: no change in ss-video or ss-fusion is needed; the review reads feature rows ss-track
  already records.

## Close or resume

Every gate passed. This record was left open when its task left the plan; the
[review and freeze record](0055-self-supervised-corpus-corpus-review-and-freeze.md) closed it after
its `make ci`. The [leakage review](../current/corpus/leakage-review.md) page holds the behavior.
