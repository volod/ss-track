# Corpus manifest import

## Task and scope

- Id / capability: `corpus-manifest-import` / `corpus-provenance`
- State: accepted
- Source: plan task at `3fa8e0a` on branch `st-corpus-provenance`. The working tree was clean.
- Plan counts at start: 73 open (53 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=49`,
  `HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `corpus-manifest-import` and
  `select-development-workload`.
- Accepted task:

```markdown
#### corpus-manifest-import

Recordings need stable identity before anything can be replayed or compared.

- Serves: `corpus-provenance` -- [Corpus identity](../design/spec.md#41-corpus-identity-and-input-handling)
- Agent status: CLEAR
- Milestone: M1
- Dependencies: none.
- User-visible outcome: An operator imports a source and gets a hashed manifest with rights,
  sensitivity and timestamp-quality fields, or a structured refusal.
- Scope boundary: Import, hashing and the canonical decode policy. One pinned decoder is chosen here
  and must have arm64 wheels. Staging and annotation are later tasks.
- Data and artifact paths: `src/ss_track/corpus/`, `tests/corpus/`, `$DATA_DIR/corpus/<corpus-id>/`.
- Execution path: Add `ss-track import` and `ss-track corpus build` in `src/ss_track/cli.py`, keeping
  logic in `src/ss_track/corpus/`, with small synthetic media fixtures and the smallest justified
  decoder dependency in `uv.lock`.
- Acceptance gates: Truncated, zero-length, wrong-hash, non-increasing PTS and selection-past-end
  fixtures yield a structured failure and never a fabricated value. `make ci` passes.
- Documentation target: [Current implementation](current.md#areas), new page `current/corpus.md`.
```

- Amendments: none to the task text. One artifact path falls outside the declared list and is
  explained under Implementation: `$DATA_DIR/import/<source-sha256>/`.

## Implementation

`ss-track import --source recording.yaml` and `ss-track corpus build --manifest corpus.yaml` are new.
`src/ss_track/cli.py` only parses and reports; behavior is in `src/ss_track/corpus/`:

- `declaration.py` and `fields.py`: strict YAML reading with no defaults for rights or sensitivity.
- `decode.py`: `DecodePolicy` and `inspect_media`, one full strict decode of a source.
- `integrity.py`: the Matroska segment size check.
- `timestamps.py`: `measured`, `derived` and `missing` grading.
- `importer.py` and `builder.py`: the two commands.
- `sealed.py`: canonical JSON, hashing and self-verifying records.
- `refusal.py`: `CorpusRefusal` and the stable refusal codes.

`src/ss_track/paths.py` resolves the data root and reuses `quality/project_root.py`.

Decisions and rejected alternatives:

- **Decoder:** PyAV 19.0.2, exact pin. It has arm64 wheels, bundles FFmpeg and needs no NumPy. The
  system `ffmpeg` binary used by `ss-video` and `ss-fusion` was rejected: it is not pinned by
  `uv.lock`, those repositories keep it out of GitHub CI, and it does not expose per-frame corruption
  flags. On the development host the system binary is 8.0.1 and the pinned FFmpeg is 9.0.2.
- **Strict decoding:** default FFmpeg conceals damage and invents timestamps, so the policy sets
  `fflags=nofillin` and `err_detect=explode`, and any FFmpeg ERROR log refuses the source.
- **Source storage:** import copies the source, then hashes and decodes the copy, so one read covers
  both and manifests need no machine path. Referencing the original file in place was rejected for
  that reason. The copy lives under `$DATA_DIR/import/<source-sha256>/`, because
  `ss-track import` runs before any corpus exists and has no `<corpus-id>` to use.
- **Selection:** a half-open frame window in `corpus.yaml`, checked at build time. Operator seeds
  arrive with `annotation-contract`.
- **Timestamp grades:** stored PTS alone is `derived`; `measured` needs declared capture-clock
  evidence. Spec section 4.1 now states this and the strict decode rule.
- **Conflicts:** repeating an import or build reports `unchanged`. New rights for the same bytes are
  `IMPORT_CONFLICT`; a new corpus definition needs a new `corpus_id`.

Bugs found by running real media, each with a regression test:

| Bug | Regression test |
| --- | --- |
| Matroska cut just after a cluster header was accepted with fewer frames and no error | `test_cut_just_after_a_matroska_cluster_header_is_refused` |
| Truncated MP4 header crashed on a stream with no codec context | `test_no_truncation_point_yields_a_different_accepted_sequence` |
| MP4 edit-list samples were reported as damage | `test_edit_list_samples_are_accounted_for_and_not_called_damage` |
| FFmpeg's repeat filter hid a second identical error in one process | `test_truncation_known_only_from_the_error_log_is_seen_every_time` |
| `schema_version: true`, `.nan` and unhashable keys passed or crashed | `test_malformed_recordings_are_refused`, `test_bad_additions_are_refused` |
| Display rotation was not recorded | `test_display_rotation_is_recorded_and_pixels_stay_as_stored` |

Compatibility: `pyproject.toml` adds `av==19.0.2`, `pyyaml` and the dev dependency `types-pyyaml`,
with `uv.lock` updated. `ss-track info` is unchanged. No public API existed before this task.

Limitations are listed under
[Integrity limits](../current/corpus.md#integrity-limits). One more: decoding runs in process, so
unlike the subprocess wrapper in `ss-video` and `ss-fusion` it has no timeout. A pathological local
file can run until the operator stops the command.

Current-state page: [Corpus](../current/corpus.md).

## Acceptance evidence

| Gate | Exact command, test or artifact | Result and limit |
| --- | --- | --- |
| Truncated | `test_truncated_source_is_refused`, `test_no_truncation_point_yields_a_different_accepted_sequence` | pass. The sweep covers every prefix of small H.264 Matroska and MP4 clips |
| Zero-length | `test_zero_length_source_is_refused` | pass |
| Wrong hash | `test_wrong_hash_is_refused_with_both_values`, `test_changed_stored_bytes_are_refused` | pass, at import and at corpus build |
| Non-increasing PTS | `test_non_increasing_pts_is_refused` | pass for duplicate and backward PTS, each a real Matroska file |
| Selection past end | `test_selection_past_the_end_is_refused` | pass |
| Never a fabricated value | `test_missing_pts_imports_as_missing_with_no_invented_values`, `test_stored_absence_of_pts_is_kept_instead_of_guessing_from_frame_rate` | pass |
| One pinned decoder with arm64 wheels | `tests/corpus/test_decoder_pin.py` | pass against `uv.lock`. Limit: never run on arm64 hardware |
| Hashed manifest with rights, sensitivity and timestamp quality | `test_import_writes_a_hashed_manifest_with_every_required_field` | pass |
| Identical bytes in a second process | `test_a_second_process_writes_identical_bytes` | pass |
| `make ci` | `make ci` | pass on Python 3.12, 190 tests |
| Fuller local gate | `make quality` | pass, coverage 97.89% |
| Second CI version | `pytest` in a locked Python 3.13 environment | pass, 190 tests. Limit: tests only, not the lint gates |

The rest was a one-off investigation. Its scripts lived in session scratch space and were not kept;
the regression tests above are the lasting form.

| Investigation | Method | Result and limit |
| --- | --- | --- |
| Full truncation sweep | Every prefix of 17 files across Matroska, WebM, MP4, AVI, MPEG-TS, MPEG-PS and raw streams | No crash, and every accepted cut matched the full file or had empty `completeness_checks`. Run before display rotation was added |
| Corruption detection | Inverted 32-byte runs across small fixtures | Table under [Integrity limits](../current/corpus.md#integrity-limits) |
| Real encoders | 19 files from system `ffmpeg` 8.0.1, including AAC longer than video and an `-ss -c copy` cut | 18 accepted, and one resolution change refused as intended. No false refusal |
| `ss-video` recording shapes | Complete, late-join, cut and killed `-c copy` MP4 files from a local MPEG-TS feed | Complete and late-join imported, the other two refused. Limit: emulated, not a real RTSP stream |
| Test strength | 23 safeguards undone one at a time in a scratch copy | All 23 failed at least one test |

## Audit handoff

Every entry is nonblocking and belongs to an open plan task.

- `AUD-corpus-manifest-import-1`: AVI and MPEG-PS import as `missing`, so spec section 6.1 makes their
  time-based scores unavailable. Evidence: the real-encoder matrix, where `mjpeg.avi` and `raw.avi`
  stored no PTS. Impact: such sources cannot produce a time-weighted score until corrected. Owner:
  `sot-suite`.
- `AUD-corpus-manifest-import-2`: import reads only the first video stream and ignores audio and
  sidecars, and `ss-video` bundles carry GPS and sensor sidecars. Evidence: `video_stream_count` in
  the manifest. Impact: a multi-stream encounter is not yet represented. Owner:
  `corpus-split-grouping`.
- `AUD-corpus-manifest-import-3`: display rotation is recorded and not applied. Evidence:
  `test_display_rotation_is_recorded_and_pixels_stay_as_stored`. Impact: a label tool that honors
  rotation could disagree with module pixels. Owner: `annotation-contract`.
- `AUD-corpus-manifest-import-4`: the policy declares `rgb24` output, which is lossy for sources such
  as `yuv420p10le`, and no frame is converted yet. Impact: staged pixels lose precision on those
  sources. Owner: `frame-bundle-staging`.
- `AUD-corpus-manifest-import-5`: the PyAV wheels bundle libx264 and libx265, which are GPL upstream.
  Impact: redistributing the wheels in an image needs their notices. Owner: `module-image-recipes`.

## Close or resume

Every declared gate passed; the commit is left to the project owner. The task left the plan and
three dependents now show `none.`: `frame-bundle-staging`, `corpus-split-grouping` and
`annotation-contract`. [Corpus](../current/corpus.md) is indexed in
[current implementation](../current.md#areas), and this record is indexed in the
[records README](README.md).

Plan counts after: 72 open (52 agent, 20 human); statuses `BLOCKED BY HUMAN=9`, `CLEAR=48`,
`HUMAN-GATED=11`, `RUN NEEDED=4`; next eligible `frame-bundle-staging` and
`select-development-workload`. Capability `corpus-provenance` stays `planned`.
