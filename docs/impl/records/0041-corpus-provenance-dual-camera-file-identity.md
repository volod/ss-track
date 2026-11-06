# Dual-camera file identity

## Task and scope

- Id / capability: `dual-camera-file-identity` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `18f5ba4`; clean worktree.
- Plan counts at start: 136 open (113 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=107, HUMAN-GATED=13, RUN NEEDED=6. Next agent `dual-camera-file-identity (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### dual-camera-file-identity (optional)

A dual-camera file can name one video stream, and the other camera of those same bytes is
`IMPORT_CONFLICT`, so one container still cannot feed two sensors of one encounter.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: Two recordings of one file, each naming a video stream, import beside each
  other and can sit in one encounter.
- Scope boundary: A one-stream import keeps its source hash and manifest bytes. Audio and sidecars
  stay with G2 bundles. A second index is a second source record, not a second window of the first
  decode.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/import/`.
- Execution path: Give a non-zero video stream its own source identity that a one-stream import does
  not use, and let one encounter name both.
- Acceptance gates: One two-stream fixture imports both indexes into one data root. Their frame
  bundles differ, one encounter holds both, and a one-stream import keeps its source hash and
  manifest bytes. Repeating either index reports unchanged.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

A non-zero video stream has its own source identity in `src/ss_track/corpus/sources/identity.py`.
Index 0 is the file hash, so a one-stream import keeps that hash, its directory name and its
manifest bytes, and still validates as source-manifest 2.1.0. A later stream's identity is the
SHA-256 of the canonical JSON object with `content_sha256`, `kind` `video-stream` and
`video_stream_index`. Import reports that identity as `source_sha256`. The source manifest still
stores the file hash as `source.sha256`. Each identity is its own directory and its own decode.
Repeating either index reports `unchanged`.

`require_stored_source` accepts the stored file when the directory is that identity. It also
accepts index 0 when the directory name is the file hash even if the record states another hash.
A kept schema-1 record does that, and redecode still reaches the schema gate.

A corpus stream stores `content_sha256` only when the identity is not the file hash and that hash
plus the stored index derive the identity. `record/corpus-manifest` 3.2.0 adds the optional field.
`schema_version` stays 3. A one-stream corpus omits the field. Grouping still requires one group
per source identity and disjoint windows of that identity. It also requires one group for the file
hash, so the two cameras cannot sit in two groups. Lineage reports a move under the file hash when
a later version places the other camera elsewhere, and does not report that hash again when an
identity move already named it. An unlinked listing uses the same comparison.

An amendment addresses the declared index and does not open the container. After the file is gone,
a declared hash plus the index still finds a later stream. A redecode with an omitted index opens
the container while the file is present, so a dual-camera file stays `VIDEO_STREAM_UNSPECIFIED`
instead of rewriting one camera. Naming index 0 when only index 1 is imported is
`IMPORT_CONFLICT`.

`result/command` 1.9.1 names `source_sha256` as the source identity. The change is a description,
so command JSON is unchanged. The source-manifest contract stays 2.2.0, because describing the
identity there would be a major and would change one-stream manifest bytes. No new dependency,
environment variable, or command flag. Current page:
[Two cameras of one file](../current/corpus.md#two-cameras-of-one-file).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Both indexes import; index 0 keeps the file hash and validates as 2.1.0 | `tests/corpus/sources/test_dual_camera_identity.py::test_both_indexes_import_and_the_first_keeps_a_one_stream_manifest` | pass; both stored files hash to the file hash; index 1 stores that hash and `video_stream_index` 1 |
| Repeating either index reports unchanged | `test_repeating_either_index_reports_unchanged` | pass; index 1 keeps its manifest seal and identity |
| One encounter holds both and the bundles differ | `test_one_encounter_holds_both_cameras_and_their_bundles_differ` | pass; 64x48 and 32x24; only the later stream stores `content_sha256` |
| A one-stream corpus omits `content_sha256` | `test_a_one_stream_corpus_omits_the_separate_file_hash` | pass |
| Two groups cannot share the file | `test_two_groups_cannot_share_one_files_cameras` | pass; `SPLIT_LEAKAGE` names the file hash |
| Adding the other camera in the same group is not a move | `test_a_later_camera_added_in_the_same_group_is_not_a_move` | pass; camera 1 is `added`, camera 0 is `kept` |
| Placing the other camera elsewhere is `SPLIT_LEAKAGE` | `test_moving_the_other_camera_of_a_file_is_split_leakage` and `test_an_unlinked_version_lists_the_other_camera_of_the_same_file` | pass; the move and the unlinked listing name the file hash |
| Amending or redecoding one camera leaves the other record | `test_amending_one_camera_leaves_the_other_record` | pass; a declared hash finds index 1 after the file is gone |
| A one-stream import and an explicit index 0 stay the previous record | `tests/corpus/sources/test_stream_selection.py::test_naming_the_only_stream_keeps_the_previous_manifest` and `test_redecode_keeps_the_named_stream` | pass; omitted index on a dual file lists both streams and does not rewrite index 1 |
| `make ci` | `make ci` | pass; 1764 tests |

## Audit handoff

`none identified`. Reviewed the identity, import, stored-byte check, corpus field, grouping,
lineage, amendment and redecode paths, and the two contract versions.

Dropped, each because it needs no work:

- Each identity directory keeps its own copy of the file. Removing one camera's directory must
  leave the other record checkable, and a shared copy would not be a second source record.
- The source-manifest contract was not edited. An `x-rules` change would be a major and would
  change one-stream manifest bytes, which the gate forbids. `source.sha256` stays the file hash.
- An amendment with an omitted index addresses stream 0 and does not list streams, because an
  amendment does not open the container. Redecode lists them while the file is present. Stated on
  the current page.

## Close or resume

Gates passed. Current page, specification section 4.1, contracts page, records index, and the plan
are updated. Plan counts after: 135 open (112 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
CLEAR=106, HUMAN-GATED=13, RUN NEEDED=6. Next agent `declared-color-tags (optional)`; next human
`define-locked-test-policy (optional)`. `corpus-provenance` stays `planned`.
