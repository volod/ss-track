# Corpus

`ss-track import` turns one declared recording into an immutable, hashed source record.
`ss-track corpus build` groups imported sources into encounters and splits in one immutable corpus
version. `ss-track corpus stage` decodes each stream into one immutable frame bundle that every
module reads, and `ss-track corpus verify` proves those frames are intact. Each command produces a
complete record or a structured refusal, and none invents a value it could not establish. Generated
cases and annotation do not exist yet; the [plan](../plan.md) schedules them. The task records keep
the accepted tasks, their decisions and their acceptance evidence:
[import and corpus build](../records/0001-corpus-provenance-corpus-manifest-import.md),
[frame staging](../records/0002-corpus-provenance-frame-bundle-staging.md) and
[split grouping](../records/0003-corpus-provenance-corpus-split-grouping.md).

## Commands

```bash
ss-track import --source recording.yaml
ss-track corpus build --manifest corpus.yaml
ss-track corpus stage --corpus pilot-v1
ss-track corpus verify --corpus pilot-v1
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
cannot silently drop a fact. A recording is schema 1 and a corpus is schema 2. There are no defaults
for rights, sensitivity, split or scenario rights: a declaration without them is refused, and `basis`
has no `unknown` value.

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
schema_version: 2
corpus_id: pilot-v1
decode_policy_sha256: "<64 hex>"   # optional pin on the installed decoder
scenario_rights:
  sharing: restricted              # widest use of this corpus: restricted or public
  max_sensitivity: moderate        # most sensitive source accepted: low, moderate or high
groups:
  - group_id: site-a-day1          # encounters that are not independent of each other
    split: development             # development, calibration or locked
    encounters:
      - encounter_id: enc01
        streams:
          - stream_id: enc01-cam0  # unique in the corpus
            source_sha256: "<64 hex>"
            selection: {start_frame: 0, end_frame: 240}   # optional, half-open; absent means all
          - stream_id: enc01-cam1
            source_sha256: "<64 hex>"
```

## Stored evidence

| Path | Content |
| --- | --- |
| `$DATA_DIR/import/<source-sha256>/source<ext>` | Read-only copy of the source bytes |
| `$DATA_DIR/import/<source-sha256>/manifest.json` | Sealed source manifest |
| `$DATA_DIR/corpus/<corpus-id>/manifest.json` | Sealed corpus manifest |
| `$DATA_DIR/corpus/<corpus-id>/frames/<stream-id>/` | One read-only frame bundle |

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
source pixel format and bit depth, stored color tags, display rotation, interlaced frame count, time
base, one PTS per presented frame, discarded sample count, video stream count, timestamp quality and
completeness checks.

`corpus build` trusts nothing from import time. It re-reads every source manifest, re-hashes every
stored source, requires each source's decode policy to be the installed one, and checks each
selection against the decoded frame count. The corpus manifest copies each stream's rights and
sensitivity, and lists streams in sorted order so declaration order at any level cannot change its
hash.

## Grouping and splits

| Level | Meaning |
| --- | --- |
| Group | Encounters that are not independent: one session, site, time, operator, camera trajectory or likely object. It is the only level that names a split |
| Encounter | One event in front of the sensors. Every stream of it stays together |
| Stream | One sensor's frames of one encounter, from one source and frame window. `stream_id` identifies it across the corpus, in its bundle path and in every `FrameRef` |

Grouping is the operator's judgment, and nothing detects that two groups are in fact related.
`src/ss_track/corpus/grouping.py` owns the rules that `corpus build` applies:

- A split is stated once, on a group, so every encounter and stream inherits it.
- An identifier declared in two splits is `SPLIT_LEAKAGE`. Repeated in one split it is
  `MANIFEST_INVALID`.
- A source used by two groups is `SPLIT_LEAKAGE` even inside one split, because groups that share a
  recording are not independent.
- One group may cut several encounters from one long recording, with adjacent windows. A source frame
  in two streams is `STREAM_OVERLAP`, because it would count twice in anything aggregated by
  encounter.

Each entry of the manifest's `streams` list carries `stream_id`, `modality`, `encounter_id`,
`group_id` and `split`, and a build result counts the groups, encounters and streams of each split:

```json
{"status": "built", "stream_count": 3, "splits": {"calibration": {"group_count": 1,
 "encounter_count": 1, "stream_count": 1}, "development": {"group_count": 1,
 "encounter_count": 1, "stream_count": 2}}}
```

`modality` is always `camera`, because import accepts only video. Streams of one encounter are not
declared synchronized: no clock relation between them is recorded.

`locked` records membership only. Nothing restricts who reads a locked stream, so no output may call
it held-out. Changing any membership needs a new corpus version, and nothing compares versions: a
source moved from `development` to `locked` by a later version is accepted.

The source rule compares bytes. An `ffmpeg -c copy` remux of one recording imports as a different
source: put into `development` and `locked`, it built and staged with 100 of 100 identical frames, so
keep every copy of a recording in one group. Their bundle hashes differ, because a bundle's identity
includes its source hash and time base, so comparing bundle hashes does not find them either.
Near-duplicate detection does not exist.

### Scenario rights

`scenario_rights` says what a corpus asks of its sources, and each stream is compared with the rights
in its verified source manifest:

| Field | Conflict when |
| --- | --- |
| `sharing` | The corpus is `public` and a source is `restricted` |
| `max_sensitivity` | A source is more sensitive than this level |

A conflict is `RIGHTS_CONFLICT`, and the refusal names all of them at once:

```json
{"status": "refused", "code": "RIGHTS_CONFLICT", "message": "...", "details": {"conflicts": [
 {"stream_id": "enc01-cam1", "source_sha256": "...", "field": "sharing",
  "source_value": "restricted", "scenario_value": "public"}]}}
```

A public source in a restricted corpus is no conflict: it stays recorded as public, and the corpus
stays restricted, so an encounter may mix both. `holder`, `basis` and `retention` are recorded terms
that are never compared, and an expired retention period goes unnoticed.

The manifest pins each source record. `corpus stage` first re-reads every source record, before
writing or skipping anything, and a re-imported source is `SOURCE_RECORD_CHANGED`, so withdrawn
rights cannot pass under the rights a corpus recorded earlier. `corpus verify` checks frames alone and
does not look at source records.

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
| `ACCURATE_RND`, `BITEXACT` conversion | Without them FFmpeg's SIMD and C paths round differently, so pixels depend on the CPU |
| `FULL_CHR_H_INT`, `FULL_CHR_H_INP` conversion | Without them chroma is repeated instead of interpolated and lands in the wrong place |

Exit status alone is not enough evidence, so `inspect_media` also refuses on a demuxer corrupt-packet
flag, a decoder corrupt-frame flag, and any FFmpeg ERROR log. The log is the only signal for an FFV1
CRC mismatch and for most truncated Matroska files. FFmpeg's repeat filter stays off while reading,
because it would hide a second identical error.

Decoded dimensions are the stored dimensions: the policy does not apply display rotation, so
`display_rotation_degrees` is a fact for label tools, not a transform that modules receive. A tool
that honors rotation must map its coordinates back to the stored orientation.

`src/ss_track/corpus/pixels.py` owns the conversion to `rgb24`. It honors the stored color matrix,
range and chroma location, and converts neither primaries nor transfer function, so an HDR source
keeps its gamut and curve in 8-bit values. A source with no matrix tag is converted as BT.601, which
misreads BT.709 content: a pure BT.709 red becomes `(233, 0, 2)`. Staging warns, and nothing guesses
a tag the source lacks. Unspecified chroma location means center. Sources deeper than 8 bits lose
precision and alpha is dropped. Interlaced frames stay woven and convert as progressive, so they are
counted in `interlaced_frames`. Changing any stored color tag within a stream is
`SOURCE_FORMAT_CHANGED`, which keeps one recorded description true of every frame.

The decoder runs in process, not through the `ffmpeg` binary that `ss-video` and `ss-fusion` call.
This corpus needs a decoder version fixed by `uv.lock`, its behavior covered by `make ci`, and frame
and packet corruption flags; a system binary provides none of these. Their `-c copy` recordings
import normally, and an interrupted one is refused: a cut faststart MP4 as `SOURCE_DAMAGED`, and a
killed recording with no `moov` as `SOURCE_UNREADABLE`.

## Frame bundles

`corpus stage` writes one bundle per stream of a built corpus, with the same strict decode as
import. `src/ss_track/corpus/bundle_writer.py` writes a bundle and `src/ss_track/corpus/staging.py`
runs the command.

| Path | Content |
| --- | --- |
| `00000012.rgb24` | One frame: tightly packed RGB rows, `width * height * 3` bytes, no padding |
| `manifest.json` | Sealed record with the frame index, per-frame SHA-256 and `bundle_sha256` |

Frame names and `frame_index` are positions in the source sequence, so a selection keeps them: a
window `[5, 9)` holds frames 5 to 8, and labels stay aligned with any window. A bundle holds only its
selection, even though staging decodes the whole source to prove it still matches its import.

`bundle_sha256` covers the `identity` block: source hash, decode policy hash, pixel format, width,
height, bytes per frame, time base, selection and the ordered index of frame index, PTS and frame
hash. Nothing else enters it, so two stagings of one source and window under one policy give one
hash, whatever the corpus or stream is called. The record separately holds the source pixel format
and bit depth, `precision_reduced`, stored color tags, display rotation, interlaced frame count,
timestamp quality, its `stream_id` and the links to its corpus and source manifests.

Staging trusts nothing from before it ran. It re-hashes the stored source, requires the installed
decode policy, requires the source record the corpus pinned, and refuses with `DECODE_DRIFT` if this
decode disagrees with the import record in any field. It checks free space first, because raw frames
dwarf their source: 14 MB of H.264 became 3.5 GB at 1080p. On the development host that clip staged
at 74 frames per second with an 87 MB peak.

Frames are written to a scratch directory and published by one rename, so a failure leaves no bundle.
One staging runs per corpus, under a lock the kernel releases however a run ends. A second run gets
`STAGING_IN_PROGRESS`, and the next run to take the lock removes what a killed run left behind.
Streams finished before a refusal stay staged, and repeating the command skips them.

Repeating `corpus stage` re-hashes each existing bundle and reports `unchanged`. A bundle staged from
another corpus version, or one sitting under another stream's path, is `BUNDLE_CONFLICT`, so moving a
bundle cannot carry frames into another split. A bundle is immutable: frames are mode `0444`, the
directory is `0555`, and a damaged one is never repaired in place. Remove it with
`chmod -R u+w <bundle> && rm -rf <bundle>`, then stage again; the hash comes back the same.

### Reading frames

```python
from ss_track.corpus import open_frame_bundle

bundle = open_frame_bundle(data_root / "corpus" / "pilot-v1" / "frames" / "enc01-cam0")
ref = bundle.frame_ref(12)         # FrameRef for frame 12 of the source sequence
pixels = bundle.read_frame(12)     # packed RGB bytes, compared with the sealed hash on every read
```

`src/ss_track/corpus/frames.py` owns this access. `frame_refs()` yields every reference in
presentation order. A `FrameRef` carries stream, source hash, frame index, PTS, time base, timestamp
quality and capture-clock evidence, dimensions, pixel format, transform, bundle hash, frame name and
frame hash. `transform` is always `identity`: pixels are as stored, and display rotation stays a
record fact. An absent PTS stays `null`. An index outside the bundle is `FRAME_NOT_IN_BUNDLE`.

### Verification

`corpus verify` re-hashes every frame of every stream and names each damaged file with its stream:

```json
{"status": "refused", "code": "FRAME_CORRUPTED", "message": "...", "details": {"damaged_count": 1,
 "frames": [{"stream_id": "enc01-cam0", "frame": "00000003.rgb24", "reason": "hash_mismatch"}]}}
```

The reason is `hash_mismatch`, `missing` or `unexpected_file`. `damaged_count` is always complete; the
list names the first 32. A stage over a damaged bundle and a read of a damaged frame refuse the same
way, so a changed frame cannot reach a module.

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
| `SOURCE_RECORD_CHANGED` | A source was re-imported after the corpus that pins its record was built |
| `SPLIT_LEAKAGE` | A group, encounter or stream is declared in two splits, or two groups share a source |
| `STREAM_OVERLAP` | Two streams use the same frames of one source |
| `RIGHTS_CONFLICT` | A source's recorded rights do not cover the corpus's scenario rights |
| `RECORD_TAMPERED` | A manifest is missing, malformed or fails its seal, or a re-import finds changed stored bytes |
| `RECORD_SCHEMA_UNSUPPORTED` | An intact corpus or bundle record was written under another schema |
| `DECODE_POLICY_MISMATCH` | A source or pin uses a decode policy other than the installed one |
| `IMPORT_CONFLICT` | The same source was imported with another declaration or decoder |
| `CORPUS_CONFLICT` | The `corpus_id` already exists with different content |
| `CORPUS_NOT_BUILT` | The named corpus version does not exist, or the identifier cannot name one |
| `DECODE_DRIFT` | A staging decode disagrees with the import record of its source |
| `BUNDLE_NOT_STAGED` | A stream has no staged frame bundle |
| `BUNDLE_CONFLICT` | A bundle was staged from a different corpus version, or for a different stream |
| `STAGING_IN_PROGRESS` | Another run is staging this corpus version |
| `FRAME_CORRUPTED` | A staged file differs from the sealed index, is gone, or is not in it |
| `FRAME_NOT_IN_BUNDLE` | A frame index lies outside a bundle |
| `STORAGE_FAILED` | The data root cannot be written, or lacks the space for raw frames |

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

A bundle's per-frame hashes prove that frames have not changed since staging. They cannot show that
a frame was right when staged, because that rests on the source hash and the limits above.

Two pixel comparisons bound the conversion. Staged frames matched system `ffmpeg` 8.0.1 exactly on 26
of 32 real-encoder files, including every lossless source. The other six are H.264 and HEVC with
left-sited chroma, where decoded YUV matched and only conversion differed. A measured chroma ramp
settles which is right: the pinned path lands within 0.02 pixels when the tag is true, and system
`ffmpeg` lands 0.48 pixels off because it treats `left` as `center`. Software that converts with that
binary therefore sees different pixels from a bundle on those sources.

Bundle hashes matched on all 32 files with FFmpeg's SIMD disabled, and the bit-exact flags are what
make that true. That is the only cross-CPU evidence: it has not been run on arm64 hardware, and
bundles are not claimed to be identical across decoders.

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
`tests/corpus/test_bundle_writer.py`, `test_staging.py`, `test_frames.py` and `test_pixels.py` cover
staging, and `test_pixels.py` includes the comparison with FFmpeg's SIMD disabled.
`tests/corpus/test_grouping.py`, `test_scenario_rights.py` and `test_stream_identity.py` cover
membership, rights and each stream's identity from build to `FrameRef`.

```bash
make test
```
