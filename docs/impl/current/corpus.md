# Corpus

`ss-track import` turns one declared recording into an immutable, hashed source record.
`ss-track corpus build` binds imported sources into one immutable corpus version. Either command
produces a complete record or a structured refusal, and neither invents a value it could not
establish. Frame staging, encounter grouping and splits, generated cases and annotation do not exist
yet; the [plan](../plan.md) schedules them. The
[task record](../records/0001-corpus-provenance-corpus-manifest-import.md) keeps the accepted task,
its decisions and its acceptance evidence.

## Commands

```bash
ss-track import --source recording.yaml
ss-track corpus build --manifest corpus.yaml
```

Each command logs one JSON record. A result has a `status`, its hashes and its manifest path, and
exits 0. A refusal exits 1 and has this form:

```json
{"status": "refused", "code": "PTS_NON_INCREASING", "message": "...", "details": {"frame_index": 3}}
```

`src/ss_track/paths.py` resolves the data root: `DATA_DIR` from the environment, then from `.env` at
the project root, then `.data`. Relative values resolve against the project root.

## Declarations

Both files reject unknown fields, repeated keys and any other schema version, so a misspelled key
cannot silently drop a fact. There are no defaults for rights or sensitivity: a recording without
them is refused, and `basis` has no `unknown` value.

```yaml
# recording.yaml
schema_version: 1
source:
  path: clip.mkv             # relative to this file
  sha256: "<64 hex>"         # optional; declare it at capture, see Integrity limits
rights:
  holder: Project Contributors
  basis: owned               # owned, licensed, consented or public_domain
  retention: project duration
  sharing: restricted        # restricted or public
sensitivity:
  level: low                 # low, moderate or high
  notes: optional text
timestamps:                  # optional
  capture_clock_evidence: hardware clock, PTP disciplined
capture:                     # optional; every absent fact is stored as unknown
  camera: bench camera       # also lens, exposure, focus, fov, camera_control_mode,
  range:                     # lighting, background, motion and object_pixel_extent
    status: measured         # measured, estimated or unknown
    value_m: 12.5
    method: laser rangefinder
```

```yaml
# corpus.yaml
schema_version: 1
corpus_id: pilot-v1
decode_policy_sha256: "<64 hex>"   # optional pin on the installed decoder
sequences:
  - sequence_id: enc01-cam0
    source_sha256: "<64 hex>"
    selection: {start_frame: 0, end_frame: 240}   # optional, half-open; absent means all frames
```

## Stored evidence

| Path | Content |
| --- | --- |
| `$DATA_DIR/import/<source-sha256>/source<ext>` | Read-only copy of the source bytes |
| `$DATA_DIR/import/<source-sha256>/manifest.json` | Sealed source manifest |
| `$DATA_DIR/corpus/<corpus-id>/manifest.json` | Sealed corpus manifest |

Import copies the source first, then hashes and decodes that copy, so the record describes exactly
the bytes retained. The finished directory is published by one rename, so a failure leaves nothing
that looks complete.

A sealed manifest carries `manifest_sha256`, a SHA-256 of its canonical JSON. It holds no clock time
or filesystem path, so the same source, declaration and decoder give identical bytes in any process.
Repeating an import or a build reports `unchanged`. Changing the declaration or the decoder for an
imported source is `IMPORT_CONFLICT`, and redefining a corpus is `CORPUS_CONFLICT`: a change needs a
new corpus version.

A source manifest records the hash and size, whether the hash was declared, rights, sensitivity,
capture facts, the decode policy and the sequence: container, codec, original and decoded dimensions,
source pixel format, display rotation, time base, one PTS per presented frame, discarded sample
count, video stream count, timestamp quality and completeness checks.

`corpus build` trusts nothing from import time. It re-reads every source manifest, re-hashes every
stored source, requires each source's decode policy to be the installed one, and checks each
selection against the decoded frame count. The corpus manifest copies each sequence's rights and
sensitivity, and lists sequences in sorted order so declaration order cannot change its hash.

## Canonical decode policy

`src/ss_track/corpus/decode.py` owns `DecodePolicy`. The decoder is PyAV, pinned exactly in
`pyproject.toml`, and its wheels bundle FFmpeg with no system dependency.
`tests/corpus/test_decoder_pin.py` keeps the exact pin and the arm64 Linux and macOS wheels true of
`uv.lock`. The output pixel format is `rgb24`. The policy hash covers all of these options:

| Option | Reason |
| --- | --- |
| `fflags=nofillin` | Without it the demuxer invents PTS from a guessed frame rate for files that store none |
| `err_detect=explode` | Without it decoders conceal damaged blocks and return a frame as if nothing happened |
| `flags=bitexact`, one thread | Removes decoder choices that can vary between runs |

Exit status alone is not enough evidence, so `inspect_media` also refuses on a demuxer corrupt-packet
flag, a decoder corrupt-frame flag, and any FFmpeg ERROR log. The log is the only signal for an FFV1
CRC mismatch and for most truncated Matroska files. FFmpeg's repeat filter stays off while reading,
because it would hide a second identical error.

Decoded dimensions are the stored dimensions: the policy does not apply display rotation, so
`display_rotation_degrees` is a fact for label tools, not a transform that modules receive. A tool
that honors rotation must map its coordinates back to the stored orientation.

The decoder runs in process, not through the `ffmpeg` binary that `ss-video` and `ss-fusion` call.
This corpus needs a decoder version fixed by `uv.lock`, its behavior covered by `make ci`, and frame
and packet corruption flags; a system binary provides none of these. Their `-c copy` recordings
import normally, and an interrupted one is refused: a cut faststart MP4 as `SOURCE_DAMAGED`, and a
killed recording with no `moov` as `SOURCE_UNREADABLE`.

## Timestamp quality

`src/ss_track/corpus/timestamps.py` grades stored PTS and never fills one in.

| Quality | Meaning |
| --- | --- |
| `measured` | Every frame stores a PTS, and the operator declared capture-clock evidence |
| `derived` | Every frame stores a PTS, with no evidence of where it came from |
| `missing` | At least one frame stores no PTS. Stored values are kept and absent ones stay `null` |

Duplicate or decreasing PTS is `PTS_NON_INCREASING`, naming the first offending frame. Capture-clock
evidence for a stream with missing PTS is `TIMESTAMP_CLAIM_UNSUPPORTED`. Under `nofillin`, AVI and
MPEG program streams import as `missing`, because they do not store a presentation time per frame.

## Refusal codes

| Code | Raised when |
| --- | --- |
| `MANIFEST_INVALID` | A declaration is unreadable or does not match its schema |
| `SOURCE_NOT_FOUND` | The declared source does not exist |
| `SOURCE_UNREADABLE` | The source is not a readable file, cannot be opened, or has no usable video stream |
| `SOURCE_EMPTY` | The source has zero length |
| `SOURCE_HASH_MISMATCH` | Bytes differ from the declared or imported hash, or the stored source is gone |
| `SOURCE_DAMAGED` | Decoding or a completeness check shows truncation or corruption |
| `SOURCE_NO_FRAMES` | The media opened but decoded to no frames |
| `SOURCE_FORMAT_CHANGED` | Resolution, pixel format or display rotation changes within the stream |
| `PTS_NON_INCREASING` | Stored PTS repeats or goes backward |
| `TIMESTAMP_CLAIM_UNSUPPORTED` | Capture-clock evidence was declared without complete PTS |
| `SELECTION_OUT_OF_RANGE` | A selection runs past the end of its sequence |
| `SOURCE_NOT_IMPORTED` | A corpus names a source with no import record |
| `RECORD_TAMPERED` | A manifest is missing, malformed or fails its seal, or a re-import finds changed stored bytes |
| `DECODE_POLICY_MISMATCH` | A source or pin uses a decode policy other than the installed one |
| `IMPORT_CONFLICT` | The same source was imported with another declaration or decoder |
| `CORPUS_CONFLICT` | The `corpus_id` already exists with different content |
| `STORAGE_FAILED` | The data root cannot be written |

## Integrity limits

These measurements set the checks above. The truncation sweep inspected every byte-length prefix of
each file; an accepted prefix had to match the complete file's PTS and pixels.

| Container | Truncation result | `completeness_checks` |
| --- | --- | --- |
| Matroska and WebM of known size | Every cut refused | `matroska_segment_size` |
| MP4 with a sample table, AVI | Every cut refused unless all frames survive intact | `frame_count` |
| Fragmented MP4, MPEG-TS, MPEG-PS, raw streams, live Matroska | A short file can be accepted | empty |

A Matroska file cut just after a cluster header ends cleanly: FFmpeg logs nothing and returns fewer
frames, so `src/ss_track/corpus/integrity.py` compares the file with the segment size in its header.
An MP4 edit list can mark stored samples as never presented. They count toward the container total
as `discarded_frames` and are not frames of the sequence.

An empty `completeness_checks` means completeness is unverified, not that the file is short. Import
logs a warning and keeps the empty list in both manifests.

Decoding cannot detect all corruption, because most video bitstreams carry no checksum. Inverting
32-byte runs across small fixtures gave:

| Bitstream | Refused | Accepted, same pixels | Accepted, changed pixels |
| --- | --- | --- | --- |
| FFV1 with slice CRC | 297 | 0 | 0 |
| H.264 | 193 | 80 | 5 |
| MJPEG | 249 | 17 | 27 |

Only a hash taken at capture excludes this, so declare `source.sha256` when one exists. The manifest
records this as `sha256_declared`; without it the hash proves only what bytes were imported.

Import reads the first video stream, records how many there are and ignores audio. A strict decode
can refuse a healthy-looking file that logs an FFmpeg error, such as a capture that starts mid-GOP;
the refusal carries FFmpeg's message.

PyAV is BSD-3-Clause, but its wheels bundle FFmpeg libraries, including libx264 and libx265 whose
upstream license is GPL. ss-track decodes only; a task that redistributes these wheels in an image
carries their notices.

## Verification

`tests/corpus/` generates its media at test time through the pinned library, so no binary enters the
repository. `tests/corpus/test_decode.py` includes the truncation sweep over small H.264 Matroska and
MP4 clips, and tests that default decoding hides damage the policy refuses.

```bash
make test
```
