# Frame bundle staging

## Task and scope

- Id / capability: `frame-bundle-staging` / `corpus-provenance`
- State: accepted
- Source: plan task at `0238d55` on branch `st-corpus-provenance`. The working tree was clean.
- Plan counts at start: 72 open (52 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=48`,
  `HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `frame-bundle-staging` and
  `select-development-workload`.
- Accepted task:

```markdown
#### frame-bundle-staging

Every module must see exactly the same decoded frames.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator stages one immutable decoded-frame bundle with a frame index and
  per-frame hashes.
- Scope boundary: Staged raw frames, `FrameRef` data and random access by frame index. Network
  delivery and later packet paths are out of scope.
- Data and artifact paths: `src/ss_track/corpus/`, `$DATA_DIR/corpus/<corpus-id>/frames/`.
- Execution path: Add staging that records pixel format, dimensions and bundle hash, with fixtures
  for a clean decode and a corrupted frame.
- Acceptance gates: Two stagings of one source give one bundle hash. A corrupted frame fails
  verification by name.
- Documentation target: [Current implementation](current.md#areas), page `current/corpus.md`.
```

- Amendments: none to the task text. The command names `ss-track corpus stage` and
  `ss-track corpus verify` were not in the task; spec section 10 now lists them.

## Implementation

`ss-track corpus stage --corpus <id>` and `ss-track corpus verify --corpus <id>` are new.
`src/ss_track/cli.py` only parses and reports. Behavior is in `src/ss_track/corpus/`:

- `pixels.py`: conversion to `rgb24`, row packing and color facts.
- `bundle_writer.py`: writes one bundle from a strict decode.
- `frames.py`: bundle layout, `FrameRef`, verified random access and damage reporting.
- `staging.py`: the two commands, the lock and the corpus-level results.

Reused rather than repeated: `inspect_media` gained an `on_frame` consumer, so staging runs the same
strict decode as import; `load_verified_source`, `require_policy` and `decoded_facts` came out of the
builder and importer; `sealed.py` still owns hashing and records.

Decisions and rejected alternatives:

- **Layout:** one read-only file per frame. A corrupted frame is then a named file, as the gate asks,
  and a later paced release can hand over one frame at a time. A single indexed file was rejected:
  it needs less disk metadata, but damage is an offset rather than a name and one truncation reaches
  every later frame.
- **Bundle hash:** covers an `identity` block only, so corpus and sequence names cannot change it.
  The seal still covers the whole record. Source manifest hash stays out, because rights facts do not
  change frames.
- **Per sequence, not per corpus:** the same source and window give the same hash anywhere. The
  frames sit under the corpus as the task declares, so a source used by two corpora is stored twice.
  A content-addressed store was rejected as more than the task asked.
- **Staging is a separate command:** `corpus build` stays fast and its manifest unchanged. The cost
  is that a corpus manifest does not name its bundle hashes; each bundle names its corpus instead.
- **`rgb24` for every source (`AUD-corpus-manifest-import-4`):** 10-bit and 16-bit sources are staged
  at 8 bits with `precision_reduced` and a warning. Refusing them would reject valid recordings, and
  a native output format would give modules a different input per source. The audit item ends here.
- **Bit-exact, full-chroma conversion:** `ACCURATE_RND` and `BITEXACT` because the default rounds
  differently with and without SIMD, and full chroma because the default repeats chroma samples.
  Full chroma costs about 2.5 times the conversion time at 720p, which staging can afford.
- **Policy revision 2:** the conversion now decides pixels, so it is part of the policy hash.
- **Color tags are recorded and never guessed:** an untagged matrix converts as BT.601 even for HD
  content. A resolution heuristic was rejected, because it would invent a fact the source lacks.
- **A kernel lock:** it solves both a killed run's scratch and concurrent runs. Scratch cannot be
  cleared safely without knowing no other run owns it.

Findings from running real media, each with a regression test:

| Finding | Regression test |
| --- | --- |
| PyAV's default conversion gave different pixels with SIMD off on 6 of 21 sources | `test_pixels_do_not_depend_on_the_cpu_code_path` |
| Row padding reached the pixels at odd widths, including native `rgb24` with no conversion | `test_row_padding_never_reaches_the_pixels`, `test_an_odd_width_stages_with_no_row_padding` |
| Chroma location changes pixels and was not recorded | `test_color_tags_record_every_input_of_the_conversion`, `test_the_stored_chroma_location_steers_the_conversion` |
| The matrix warning fired on RGB, gray and rgba sources that use no matrix | `test_an_untagged_matrix_is_reported_only_when_conversion_used_one` |
| The same warning missed 4:4:4 YUV: PyAV's `is_chroma` means subsampled chroma | `test_only_chroma_formats_use_a_color_matrix` |
| A killed run left 1.4 GB of hidden scratch that nothing removed | `test_a_killed_run_leaves_no_scratch_after_the_next_run` |
| A concurrent run failed as `STORAGE_FAILED: Directory not empty` | `test_a_concurrent_run_is_refused` |
| Interlaced frames convert as progressive with no record of it | `test_interlaced_frames_are_counted` |

Compatibility: decode policy revision 2 and new source manifest fields (`source_bits_per_component`,
`color`, `interlaced_frames`) mean records from revision 1 are refused with `DECODE_POLICY_MISMATCH`.
Re-importing one is `IMPORT_CONFLICT` until its import directory is removed, and its corpus must be
rebuilt. A stored color tag that changes within a stream is now `SOURCE_FORMAT_CHANGED`, which import
accepted before. `pyproject.toml` and `uv.lock` are unchanged. `ss-track info`, `import` and
`corpus build` keep their arguments. `fcntl` makes staging POSIX-only, which matches the supported
Linux and macOS hosts.

Limitations:

- Staging decodes the whole source even for a short selection, to compare it with the import record.
- Frames are not fsynced one by one, so power loss after staging can damage a frame. `corpus verify`
  detects that; nothing prevents it.
- Ctrl-C removes scratch but prints a Python traceback, not a refusal record, as import does.
- A frame's hash proves it has not changed since staging, not that the source was undamaged. The
  bitstream limits under [Integrity limits](../current/corpus.md#integrity-limits) still apply.

Current-state page: [Corpus](../current/corpus.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Two stagings of one source give one bundle hash | `test_two_stagings_of_one_source_give_one_bundle_hash`, `test_a_second_process_stages_identical_bytes` | pass, across data roots, corpus ids, sequence ids and processes |
| A corrupted frame fails verification by name | `test_a_corrupted_frame_fails_verification_by_name`, `test_a_corrupted_frame_is_named_with_a_failing_status` | pass for flipped, truncated, extended and deleted frames |
| One immutable bundle with a frame index and per-frame hashes | `test_stage_writes_every_frame_with_an_index_and_per_frame_hashes`, `test_a_bundle_is_read_only` | pass |
| Records pixel format, dimensions and bundle hash | `test_stage_writes_every_frame_with_an_index_and_per_frame_hashes`, `test_a_bundle_records_how_its_pixels_were_made` | pass |
| Clean decode fixture | `test_a_clean_decode_reproduces_the_original_pixels_exactly` | pass, byte-exact through a lossless source |
| `FrameRef` data and random access | `test_a_frame_ref_identifies_the_frame_and_how_to_reach_it`, `test_reading_a_frame_returns_exactly_the_indexed_bytes`, `test_a_frame_outside_the_bundle_is_refused` | pass. Limit: an in-process dataclass until the schema task |
| `make ci` | `make ci` | pass on Python 3.12, 284 tests |
| Fuller local gate | `make quality` | pass, coverage 98.37% |
| Second CI version | `pytest` in a locked Python 3.13 environment | pass, 284 tests. Limit: tests only, not the lint gates |

The rest was a one-off investigation on the final code. Its scripts lived in session scratch space
and were not kept; the regression tests above are the lasting form.

| Investigation | Method | Result and limit |
| --- | --- | --- |
| Real encoders through the CLI | 33 files from system `ffmpeg` 8.0.1: H.264, HEVC, VP9, MJPEG, FFV1, PNG, raw and others, in Matroska, MP4, WebM, NUT, AVI and MOV | 32 staged, verified and re-staged as `unchanged`. One ZMBV file was refused at import by the strict decode, which is existing behavior |
| Reproducibility | The same matrix in a second data root | All 32 bundle hashes identical |
| CPU independence | The same matrix with `av_force_cpu_flags(0)` | All 32 bundle hashes identical. Limit: a proxy; never run on arm64 hardware |
| Independent pixels | Staged frames against system `ffmpeg` raw output, frame by frame | 26 of 32 byte-exact, including every lossless source. The other six are left-sited H.264 and HEVC; all six decode to identical YUV |
| Chroma siting | A ramp sampled at known positions, tagged true and false | Pinned path within 0.02 px when the tag is true and 0.5 px off when false, so it uses the tag. System `ffmpeg` 8.0.1 is 0.48 px off because it treats `left` as `center` |
| Frame order and windows | Lossless H.264 with B-frames, three selections | 50 of 50 frames in presentation order against `ffmpeg`; window frames equal the whole sequence at the same index |
| Operational failures | `kill -9`, SIGINT, a file size limit, two concurrent runs and traversal ids, on 1080p | No bundle from any failure, scratch cleared, structured refusals. SIGINT leaves a traceback |
| Throughput | 600 frames of 1080p H.264 | 8.11 s, 74 frames per second, 87 MB peak, 3.5 GB from 14 MB. Verify 1.73 s. One host, on tmpfs |
| Test strength | 42 safeguards undone one at a time in a scratch copy | 41 failed a test, each the one meant to catch it. The survivor is an equivalent mutant: the revision constant, because `conversion_flags` already changes the policy hash |

## Audit handoff

Every entry is nonblocking and belongs to an open plan task.
`AUD-corpus-manifest-import-4` is resolved above.

- `AUD-frame-bundle-staging-1`: `FrameRef` is a Python dataclass, and spec section 5 makes it a
  versioned record family. Evidence: `src/ss_track/corpus/frames.py`. Impact: its fields must reach
  the `.proto` definition with these meanings. Owner: `event-schema-contract`.
- `AUD-frame-bundle-staging-2`: nothing pins a bundle hash yet, and a corpus manifest does not name
  its bundles. Evidence: staging is a separate step. Impact: a run could read a bundle that no
  scenario declared. Owner: `scenario-contract`.
- `AUD-frame-bundle-staging-3`: `FRAME_CORRUPTED`, `RECORD_TAMPERED` and `BUNDLE_NOT_STAGED` are
  corpus refusals, while spec section 5 calls a broken bundle `RUNNER_INVALID`. Impact: the runner
  must map them and not report a module fault. Owner: `lockstep-runner`.
- `AUD-frame-bundle-staging-4`: `read_frame` hashes on every read, about 3 ms per 1080p frame on the
  development host. Impact: inside a paced loop this is runner time to account for. Owner:
  `paced-frame-release`.
- `AUD-frame-bundle-staging-5`: a bundle directory exposes every frame at once. Impact: mounting one
  into a module would break the rule that no future frame is readable. Owner:
  `container-module-sandbox`.
- `AUD-frame-bundle-staging-6`: `stream_id` is the sequence id. Impact: multi-stream encounters need
  a real stream identity. Owner: `corpus-split-grouping`.
- `AUD-frame-bundle-staging-7`: `ss-video` and `ss-fusion` convert with a system `ffmpeg` binary that
  misplaces left-sited chroma by half a pixel. Evidence: the chroma siting measurement. Impact: live
  frames could differ from bundles on H.264 and HEVC. Owner: `camera-front-end`.

## Close or resume

Every declared gate passed; the commit is left to the project owner. The task left the plan, and
three dependents dropped it: `generated-fixture-cases`, `lockstep-runner` and
`label-pilot-encounters`. [Corpus](../current/corpus.md) is updated and its index entry extended, and
this record is indexed in the [records README](README.md). The spec gained the two commands and the
bundle hash rule, and the test plan lists this case as existing behavior.

Plan counts after: 71 open (51 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=47`,
`HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `corpus-split-grouping` and
`select-development-workload`. Capability `corpus-provenance` stays `planned`.
