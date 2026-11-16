# Image-sequence annotation source

## Task and scope

- Id / capability: `annotation-sequence-source` / `annotation-selection`
- State: accepted
- Source: plan task at `e088344ba54efd8a7d9c1a3f9ccf672b7412c3e0`; the tree was clean.
- Plan counts at start: 156 open tasks (127 agent, 29 human). Next agent
  `annotation-sequence-source`. Next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### annotation-sequence-source

An ordered image sequence is a source modules can receive, and a label drawn on it cannot be
validated.

- Serves: `annotation-selection` -- [Annotation contract](../design/spec.md#42-annotation-contract)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: `ss-track annotate validate`, `compare` and `freeze` accept an ordered
  image sequence. Validate checks a label, a seed and a mask. Compare and freeze check two label
  documents. Each check uses that sequence's identity and stored pixels.
- Scope boundary: Sequence identity and frame geometry for a declared image sequence. A video file
  keeps the file hash as its source identity. A directory that is not a sequence stays refused.
  Labelling the sequence is human work.
- Data and artifact paths: `src/ss_track/annotate/`, `tests/annotate/`.
- Execution path: Read one image-sequence directory through the existing sequence identity and reuse
  the label, seed and mask checks.
- Acceptance gates: A label whose source hash is the sequence identity validates. A label that uses
  a video-file hash, or any hash other than the sequence identity, is refused with a reason. Compare
  and freeze use that same identity. A video file still validates, compares and freezes as it does
  now. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`read_frame_space` accepts a video file or the retained image-sequence directory import writes:
`index.json` plus the ordered images. A video file's identity stays its file hash. A sequence's
identity is `sequence_identity` of those ordered image hashes. The check hashes every retained
image, then decodes the directory through `inspect_stored`, so width, height, display rotation,
frame count and timing come from the stored pixels. A directory with no inventory stays
`SOURCE_NOT_FOUND`. Order is not taken from filenames.

`match_retained_images` is the one membership check. `verify_sequence` uses it, and so does
annotation. A missing image is named by its retained basename. A changed image or an extra name is
`SOURCE_HASH_MISMATCH`. A sealed inventory that is not intact is `RECORD_TAMPERED`. Images whose
decoded shape disagrees are `SOURCE_FORMAT_CHANGED`. A sequence with no declared rate keeps null
PTS and time base.

Validate, compare and freeze call that same read. A label or seed whose `source_sha256` is a file
hash, or any other hash, is `MANIFEST_INVALID` and the reason names both hashes. Compare and freeze
write the sequence identity into the frozen label and the revision. The label, seed and mask checks
are unchanged.

`declaration/annotation-label` 1.0.1, `declaration/annotation-seed` 1.0.1 and
`record/annotation-revision` 1.0.1 correct the `source_sha256` description. Documents stay at
schema major 1. No environment variable, dependency or command-result field changed.

Current page: [Corpus](../current/corpus.md#annotation-contract).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Sequence identity validates a label, a seed and a mask | `pytest tests/annotate/test_annotation_sequence.py::test_validate_accepts_a_sequence_label_seed_and_mask` | pass: identity differs from the video file hash and from one image hash; seed pts is the sequence frame |
| A video-file hash or any other hash is refused with a reason | `test_a_label_hash_other_than_the_sequence_identity_is_refused` | pass: `MANIFEST_INVALID` names `source_sha256`, the rejected hash and the sequence identity |
| A seed that uses a video-file hash is refused | `test_a_seed_with_a_video_file_hash_is_refused` | pass |
| Compare and freeze use the sequence identity | `test_compare_and_freeze_use_the_sequence_identity` | pass: frozen label and revision `source_sha256` are the sequence identity |
| Compare and freeze refuse a video-file hash and write nothing | `test_compare_and_freeze_refuse_a_video_file_hash` | pass |
| A directory that is not a sequence stays refused | `test_a_directory_of_images_without_an_inventory_is_refused`, `test_validate_refuses_a_directory` | pass: numbered PNGs without an inventory are `SOURCE_NOT_FOUND` |
| Stored pixels | `test_a_label_must_match_the_decoded_frame`, `test_mixed_image_geometry_is_refused`, `test_a_changed_image_or_extra_file_is_refused` | pass: wrong width, mixed geometry, changed bytes and an extra file are refused |
| A video file keeps its file hash | `test_a_video_file_keeps_its_file_hash` plus `tests/annotate/test_annotate_command.py` and `test_annotate_review_command.py` | pass: a sequence identity on a video file is refused; existing video validate, compare and freeze tests pass |
| No invented timing | `test_a_sequence_without_a_rate_keeps_missing_timestamps` | pass: null time base and null PTS |
| Full gate | `make ci` | pass: 2653 passed, 120 deselected |

No runtime artifact was written under `$DATA_DIR`. Sequence fixtures stay in the test temporary
directory.

## Audit handoff

- Dropped, no work needed: labelling a sequence stays human work. The task says so.
- Dropped, no work needed: a directory of original images, without the retained inventory, is
  refused. Filename order is not a sequence. The identity modules use is the retained directory
  import already writes.
- Dropped, no work needed: the label, seed and revision `x-rules` sentences still say "video".
  The dialect classifies an `x-rules` text edit as a major, which would mint schema major 2 with
  no change to a stored byte. The 1.0.1 field descriptions, the specification and the current page
  state the identity.

## Close or resume

Every gate passed. Current page [Corpus](../current/corpus.md#annotation-contract), records index
and plan updated. After the plan edit, 155 open tasks remain (126 agent, 29 human). The next
agent task is `annotation-selection-audit (optional)`. The next human task is
`define-locked-test-policy (optional)`. `annotation-selection` stays `planned`.
