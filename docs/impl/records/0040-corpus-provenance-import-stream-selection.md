# Import stream selection

## Task and scope

- Id / capability: `import-stream-selection` / `corpus-provenance`
- State: accepted
- Source: plan task; starting commit `4607feb`; clean worktree.
- Plan counts at start: 136 open (113 agent, 23 human). Statuses: BLOCKED BY HUMAN=10,
  CLEAR=107, HUMAN-GATED=13, RUN NEEDED=6. Next agent `import-stream-selection (optional)`;
  next human `define-locked-test-policy (optional)`.
- Accepted task:

```markdown
#### import-stream-selection (optional)

A container with two video streams imports only the first, and a dual-camera file loses a sensor
unnoticed.

- Serves: `corpus-provenance` -- [Corpus
  identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: A recording names the video stream it means, and an ambiguous container is
  refused.
- Scope boundary: One video stream per recording, with a stream index that the decode policy honors.
  Audio and sidecars belong to G2 bundles.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`.
- Execution path: Add an index to the recording declaration, required when `video_stream_count`
  exceeds one, with a two-stream fixture.
- Acceptance gates: A two-stream file with no index is refused with both streams listed, and each
  index imports its own frames.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none.

## Implementation

`source.video_stream_index` is optional on `declaration/recording` 2.2.0. It counts video streams
from zero, not every stream in the container. `src/ss_track/corpus/decoding/streams.py` selects that
stream inside `inspect_media`. A file with one video stream may omit the index. A file with more
than one, or an index that is not a video stream, is `VIDEO_STREAM_UNSPECIFIED` and lists each
stream's index, container index, codec, width and height. No source directory is published.

The source record stores `sequence.video_stream_index` only when the decoded stream is not the
first, on `record/source-manifest` 2.2.0. Index 0 stays absent, so a one-stream import keeps its
manifest bytes and still validates as 2.1.0. Staging reads the stored index. Redecode reads the
declaration. The index is not a decode-policy field: a corpus pins one policy for every source.

The same file hash can hold one video stream. A second index is `IMPORT_CONFLICT`, and the details
name `sequence.video_stream_index` when that is what changed. A declaration that omits the index on
an already imported later stream is refused as unspecified rather than as a changed fact, so the
operator sees the stream list.

`result/command` 1.9.0 adds the refusal code. All three contract changes are minor. Staging's
decode counters forward the index into the real inspection. No new
dependency, environment variable, or command flag. Current page:
[Video stream selection](../current/corpus.md#video-stream-selection).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Unnamed dual file refused, both streams listed, import empty | `tests/corpus/sources/test_stream_selection.py::test_an_unnamed_two_stream_file_is_refused_and_lists_both` and `test_the_import_command_lists_both_streams` | pass; `import/` stays empty |
| Each index imports and stages its own frames | `test_each_index_imports_and_stages_its_own_frames` | pass; 64x48 four frames and 32x24 six frames; index 1 fails 2.1.0 and validates as 2.2.0 |
| Index 0 omits the field and still validates as 2.1.0 | `test_naming_the_only_stream_keeps_the_previous_manifest` | pass; the two manifests are byte-identical |
| Other index of the same file is `IMPORT_CONFLICT` | `test_the_other_index_of_the_same_file_conflicts` | pass; the first manifest is not rewritten |
| Leading audio lists container indexes 1 and 2 | `test_the_index_counts_video_streams_when_audio_leads` | pass; video index 1 is the smaller stream |
| Redecode honors the stored index and does not rewrite on refusal | `test_redecode_keeps_the_named_stream` | pass; omission leaves frame count 6 and index 1 |
| `make ci` | `make ci` | pass; 1753 tests |

## Audit handoff

- AUD-import-stream-selection-1: the same file cannot be imported under two indexes, so both cameras
  of one container cannot sit in one data root. Nonblocking. Owner: `dual-camera-file-identity`.
  Evidence: `test_the_other_index_of_the_same_file_conflicts`.

Dropped, each because it needs no work:

- The index is not part of `DecodePolicy`. A corpus pins one policy hash, so a per-source index
  there would refuse every existing source or look like a new decoder. Stated in the specification
  and on the current page.
- Audio and sidecars. The accepted scope assigns them to G2 bundles, and `camera-telemetry-readers`
  already owns camera metadata sidecars.
- A damaged sibling stream was not given its own fixture. The healthy two-stream file decodes the
  named stream, and an FFmpeg ERROR log during that read is already `SOURCE_DAMAGED`.

## Close or resume

Gates passed. Current page, specification section 4.1, contracts page, records index, and the plan
are updated. Plan counts after: 136 open (113 agent, 23 human). Statuses unchanged. Next agent
`dual-camera-file-identity (optional)`; next human `define-locked-test-policy (optional)`.
`corpus-provenance` stays `planned`.
