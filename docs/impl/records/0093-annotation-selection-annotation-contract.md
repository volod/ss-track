# Annotation contract

## Task and scope

- Id / capability: `annotation-contract` / `annotation-selection`
- State: accepted
- Source: plan task at `081675f`; no unrelated dirty files.
- Plan counts at start: 130 agent, 29 human; next agent `annotation-contract`, next human
  `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### annotation-contract

Labels need stable identity and a frozen mask before scores can mean anything.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator validates visibility status, geometry, instance identity, motion
  events, operator seeds and masks against a versioned contract.
- Scope boundary: Label, seed and mask contracts, validation and frozen seed replay, in the stored
  orientation modules receive. Class names stay data in a scenario pack, so a label contract states
  the shape of a class ID and the pinned pack states its values. Labelling itself is human work.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Add `ss-track annotate validate` with positive and malformed fixtures, including a
  source with display rotation.
- Acceptance gates: Identical seeds replay identically, and invalid labels are rejected with a reason.
  An unverifiable label stays unscorable and is never scored as zero. A label in any orientation other
  than the stored one is refused.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`declaration/annotation-label`, `declaration/annotation-seed` and `declaration/annotation-mask`
are 1.0.0. `result/command` 1.30.0 adds optional `annotation`. The object has no `score` field.

`ss-track annotate validate` reads one video file. Decoded pixels stay unrotated, so the stored
orientation is 0 degrees and display rotation is copied, sign included. The document hash is the
SHA-256 of the canonical JSON, shared with the pack hash. Seed replay is a pure function of the
seed document: the selection modules receive, then each perturbation. The annotator id stays off
that replay. A frame is `scorable`, `unscorable` or `not_denominator` in the order spec section 4.2
states. Class values come from the pinned pack.

A directory is refused. An image sequence uses `sequence_identity`, which this command does not
read. `annotation-sequence-source` owns that gap.

The contract reference check compares each enum member with its JSON token. A null member is
`null` on the page.

Current page: [Corpus](../current/corpus.md#annotation-contract).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Identical seed replay | `test_identical_seeds_replay_identically`, `test_the_annotator_is_not_part_of_the_replay`, CLI replay hash compared twice in `test_validate_reports_a_label_a_seed_and_a_mask` | pass: key order and comments keep one replay hash; a changed annotator id keeps it; a second command logs the same hash |
| Invalid labels refused | `test_invalid_labels_are_refused` | pass: bad class, role mark, box, visibility, duplicate id, orientation, display rotation, pack hash and schema each raise `MANIFEST_INVALID` |
| Unverifiable is not a zero | `test_frame_status_follows_the_rule_order`, `test_unverifiable_and_withheld_frames_are_not_zeros`, `test_an_unscorable_frame_cannot_become_a_score` | pass: rows are `unscorable` or `not_denominator`; the command object has no `score` key |
| Stored orientation | `test_a_rotated_source_is_labelled_in_stored_pixels`, `test_validate_refuses_a_label_drawn_in_the_display_orientation` | pass: a 90-degree display rotation keeps stored width and height; orientation 90 and swapped width are refused |
| CI | `make ci` | pass: 2532 passed, 115 deselected |

No runtime artifact was written under `$DATA_DIR`.

## Audit handoff

- AUD-annotation-contract-1, nonblocking: `ss-track annotate validate --source` refuses a directory
  with `SOURCE_NOT_FOUND`. An ordered image sequence is a source modules can receive, and its
  identity is `sequence_identity`, not the file hash. Labels on a sequence cannot be validated.
  Owner: `annotation-sequence-source`, whose text states the sequence identity, the refusal of any
  other hash, and that a video file keeps the file hash.
- Dropped, no work needed: minimum extents on the draft pack stay unset. `approve-mission-scenario-pack`
  already says an unset value stays unset, and this command does not score extent.
- Dropped, no work needed: `activity` stays an empty pack list. It is not a label field.
- Dropped, fixed here: the contract reference test compared Python `None` with the JSON `null`
  the page already writes. The check now uses the JSON token.
- Dropped, no work needed: numeric scoring of these dispositions belongs to `sot-suite` and
  `motion-suite`, which remain open. Two-annotator review belongs to `annotation-review-tools`.

## Close or resume

Every gate passed. Current page [Corpus](../current/corpus.md#annotation-contract), records index
and plan updated. After the plan edit, 159 open tasks remain (130 agent, 29 human). The next
agent task is `annotation-review-tools`. The next human task is
`define-locked-test-policy (optional)`. `annotation-selection` stays `planned`.
