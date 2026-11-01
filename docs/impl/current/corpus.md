# Corpus

`ss-track import` turns one declared recording into an immutable, hashed source record.
`ss-track corpus build` groups imported sources into encounters and splits in one immutable corpus
version. `ss-track corpus stage` decodes each stream into one immutable frame bundle that every
module reads, plus one derived bundle for each declared generated case, and `ss-track corpus verify`
proves those frames are intact and that the source records they rest on still hold. Each command
produces a complete record or a structured refusal, and none invents a value it could not establish.
Annotation does not exist yet; the [plan](../plan.md) schedules it. The task records keep the accepted
tasks, their decisions and their acceptance evidence:
[import and corpus build](../records/0001-corpus-provenance-corpus-manifest-import.md),
[frame staging](../records/0002-corpus-provenance-frame-bundle-staging.md),
[split grouping](../records/0003-corpus-provenance-corpus-split-grouping.md),
[generated cases](../records/0004-corpus-provenance-generated-fixture-cases.md),
[source terms](../records/0006-corpus-provenance-source-terms-enforcement.md),
[rights verification](../records/0007-corpus-provenance-corpus-verify-rights.md) and
[version lineage](../records/0008-corpus-provenance-corpus-version-lineage.md).

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
cannot silently drop a fact. A recording is schema 2 and a corpus is schema 3. There are no defaults
for rights, sensitivity, split or scenario rights: a declaration without them is refused, and `basis`
has no `unknown` value.

```yaml
# recording.yaml
schema_version: 2
source:
  path: clip.mkv             # relative to this file
  sha256: "<64 hex>"         # optional; declare it at capture, see Integrity limits
rights:
  holder: Project Contributors
  basis: owned               # owned, licensed, consented or public_domain
  retention: project duration # descriptive terms
  retain_until: null          # required: YYYY-MM-DD or null for no end
  derived_frames: true        # required boolean: may generated cases use this source?
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
schema_version: 3
corpus_id: pilot-v1
decode_policy_sha256: "<64 hex>"   # optional pin on the installed decoder
supersedes: pilot-v0               # optional; see Version lineage
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
            generated_cases:       # optional; see Generated cases
              - case_id: enc01-cam0-shake
                transform: camera_shake
                seed: 7
                parameters: {amplitude: 3}
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
| `$DATA_DIR/corpus/<corpus-id>/frames/<case-id>/` | One read-only bundle of a generated case |

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
`group_id`, `split`, `width` and `height`, and a build result counts each split's groups, encounters
and streams, with generated cases on a line of their own:

```json
{"status": "built", "stream_count": 3, "generated_case_count": 2, "splits": {"calibration":
 {"group_count": 1, "encounter_count": 1, "stream_count": 1, "generated_case_count": 0},
 "development": {"group_count": 1, "encounter_count": 1, "stream_count": 2,
 "generated_case_count": 2}}}
```

`modality` is always `camera`, because import accepts only video. Streams of one encounter are not
declared synchronized: no clock relation between them is recorded.

`locked` records membership only. Nothing restricts who reads a locked stream, so no output may call
it held-out. Changing any membership needs a new corpus version, and
[version lineage](#version-lineage) compares a version with the ones it names.

The source rule compares bytes. An `ffmpeg -c copy` remux of one recording imports as a different
source: put into `development` and `locked`, it built and staged with 100 of 100 identical frames, so
keep every copy of a recording in one group. Their bundle hashes differ, because a bundle's identity
includes its source hash and time base, so comparing bundle hashes does not find them either.
Near-duplicate detection does not exist.

### Version lineage

A version may name the one it supersedes with `supersedes`. Material already evaluated has been seen,
so `corpus build` compares the new version with that version and with every older version linked
behind it. `src/ss_track/corpus/lineage.py` owns these rules, and reads only source hashes, groups and
splits:

| Across the declared chain | Result |
| --- | --- |
| A source in another split or another group | `SPLIT_LEAKAGE` |
| A group in another split, even holding only new sources | `SPLIT_LEAKAGE` |
| A new source, or a new group in any split | Accepted, and listed as `added` |
| A source a version dropped, back in the place it left | Accepted |
| A source a version dropped, back anywhere else | `SPLIT_LEAKAGE`, naming the version that held it |

A refusal names every move at once, with the nearest version that held each one:

```json
{"status": "refused", "code": "SPLIT_LEAKAGE", "message": "...", "details": {"corpus_id": "pilot-v2",
 "moved_sources": [{"source_sha256": "...",
  "from": {"corpus_id": "pilot-v1", "group_id": "site-a", "split": "development"},
  "to": {"corpus_id": "pilot-v2", "group_id": "held-out", "split": "locked"}}],
 "moved_groups": []}}
```

`moved_groups` entries have the same `from` and `to`. Renaming a group moves its sources, so a group
keeps its `group_id` across linked versions. A group whose name was reused for unrelated material
needs a new name. Encounter and stream names are not compared, and a kept source may change its
frame window, its streams or its source record, whose terms are not a place.

A build result always has `lineage`. `added`, `removed` and `kept` compare sources with the named
version only, so a source returning after two versions is `added`, while `compared_versions` lists
everything the rules read, nearest first:

```json
{"status": "built", "lineage": {"status": "linked", "supersedes": "pilot-v1",
 "supersedes_manifest_sha256": "...", "compared_versions": ["pilot-v1"],
 "added": [{"source_sha256": "...", "group_id": "site-c", "split": "locked"}],
 "removed": [], "kept": [{"source_sha256": "...", "group_id": "site-a", "split": "development"}]}}
```

A version that names nothing reports `{"status": "no_lineage"}`, and nothing compared it with anything:
the same source can sit in `locked` there, and so can it in a sibling that branches from one
predecessor. `unlinked-version-report` in the [plan](../plan.md) schedules a listing of those.

The manifest seals `supersedes` as `{"corpus_id", "manifest_sha256"}`, and only when one was named, so
a version that names none keeps its hash and corpus manifests stay schema 3. Naming a predecessor on
an existing version is `CORPUS_CONFLICT`, as any change is. A named version that does not exist is
`CORPUS_NOT_BUILT` before any source is read, and so is one missing further back. A version rebuilt
differently under its old name no longer matches the seal its successor pinned, which is
`CORPUS_CONFLICT`. A superseded version therefore stays useful only while its `manifest.json` exists:
remove its frames, not its manifest. Only `corpus build` reads the chain, so `corpus stage` and
`corpus verify` work on a version whose predecessors are gone.

The comparison is by source hash, so it does not see a remux placed elsewhere by a later version.
`duplicate-frame-detection` in the [plan](../plan.md) covers that.

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
that are never compared. `rights.retain_until` supplies the enforceable deadline independently of
the descriptive retention text. A date is inclusive: build, stage and verify refuse with
`RETENTION_EXPIRED` starting the next UTC day, including when bundles already exist. Explicit
`null` means no end. Refusal deletes nothing; removing expired material is an operator action.

`src/ss_track/corpus/terms.py` owns the shared check. The Python build, stage and verify functions
accept keyword-only `today: date | None` for deterministic evaluation; commands use the UTC day
captured once at operation start. This evaluation day is never sealed, so valid reruns keep the same
bytes and hashes. The declared deadline is retained in source and corpus records.

`rights.derived_frames: false` permits ordinary stream staging but refuses any generated-case recipe
with `RIGHTS_CONFLICT`, naming its parent stream and source. `grouping.py` checks this before recipe
execution or corpus publication. Both new fields are required. Quoted and unquoted YAML dates
normalize to the same ISO string. Numbers, timestamps, invalid dates and string booleans are refused.

Source manifests now use schema 2. Old source manifests and corpus records missing the new terms
are refused with `RECORD_SCHEMA_UNSUPPORTED`; their terms are never guessed. Existing imports are
immutable, so migration requires explicitly declaring the terms and importing into a fresh data root
(or operator-managed replacement), then building a new corpus version. No automatic migration runs.

The manifest pins each source record. `corpus stage` and `corpus verify` re-read every source record
before writing, skipping or hashing anything, and a record that differs is `SOURCE_RECORD_CHANGED`,
so withdrawn rights cannot pass under the rights a corpus recorded earlier:

```json
{"status": "refused", "code": "SOURCE_RECORD_CHANGED", "message": "...", "details": {
 "stream_id": "enc01-cam0", "source_sha256": "...", "corpus_source_manifest_sha256": "...",
 "source_manifest_sha256": "...", "changed_terms": ["rights.sharing"]}}
```

`changed_terms` names each `rights` and `sensitivity` field that differs. An empty list means the
terms match and something else in the record changed, such as a capture fact or the decoder. That
refuses all the same, because the pin covers the whole record, and so does a wider right. A
re-import of the original declaration gives the original seal, so the corpus verifies again.

`_require_sources_hold` in `src/ss_track/corpus/staging.py` is this one check for both commands, and
each stream is checked, which covers every generated case because a case holds its parent's rights.
Retention comes first and reads only the corpus, so an expired source stays `RETENTION_EXPIRED` after
its directory is removed. Otherwise a missing record is `SOURCE_NOT_IMPORTED`, an unreadable one is
`RECORD_TAMPERED`, and one of another schema is `RECORD_SCHEMA_UNSUPPORTED`.

### Withdrawing rights

`ss-track import` cannot change an imported record. Declaring other terms for an imported source is
`IMPORT_CONFLICT`, which records nothing, so the corpus goes on verifying. Recording a withdrawal
today means replacing the record by hand. That also deletes the stored source, so copy it out first
when it is the only copy:

```bash
cp "$DATA_DIR/import/<source-sha256>/source.mkv" clip.mkv  # only when no other copy exists
rm -rf "$DATA_DIR/import/<source-sha256>"
ss-track import --source recording.yaml                    # now declaring the new terms
```

Every corpus version that pinned the old record then refuses at `corpus stage` and `corpus verify`.
Rebuilding it is `RIGHTS_CONFLICT` if its scenario now asks too much, or `CORPUS_CONFLICT`, so
continuing needs a new corpus version. Its frames stay on disk until an operator removes them.
`source-terms-amendment` in the [plan](../plan.md#source-terms-amendment-optional) schedules a command
for this.

Verification compares records. It does not establish that a declaration is true, and a withdrawal
nobody recorded stays invisible to it.

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
frame hash, plus `content_frame_index`, the parent frame whose pixels it shows. `transform` is
`identity` for a stream, whose pixels are as stored, with display rotation staying a record fact, and
the transform name for a generated case. An absent PTS stays `null`. An index the bundle does not
hold is `FRAME_NOT_IN_BUNDLE`.

### Verification

`corpus verify` first checks the [source terms](#withdrawing-rights), then re-hashes every frame of
every stream and names each damaged file with its stream:

```json
{"status": "refused", "code": "FRAME_CORRUPTED", "message": "...", "details": {"damaged_count": 1,
 "frames": [{"stream_id": "enc01-cam0", "frame": "00000003.rgb24", "reason": "hash_mismatch"}]}}
```

The reason is `hash_mismatch`, `missing` or `unexpected_file`. `damaged_count` is always complete; the
list names the first 32. A stage over a damaged bundle and a read of a damaged frame refuse the same
way, so a changed frame cannot reach a module.

A `verified` result covers source records and frames, not stored source bytes. Only `corpus build`
and staging a new bundle read those, so `corpus verify` and a repeated `corpus stage` do not notice a
damaged or removed stored source. No module reads one, and the frames that modules do read are the
ones hashed here.

## Generated cases

A generated case tests one failure mechanism with frames derived from a staged stream. It is
synthetic: nothing here claims realism, and a case is never field evidence. A recipe sits under its
parent stream and has no other home:

| Field | Meaning |
| --- | --- |
| `case_id` | Unique across every stream and case of the corpus, because it names a bundle |
| `transform` | One of the table below |
| `seed` | Required, from 0 to 2^63 - 1 |
| `window` | Optional half-open frame window inside the parent's selection; absent means all of it |
| `parameters` | Exactly the keys of that transform, with no defaults |

| Transform | Parameters | The seed decides | Label transform |
| --- | --- | --- | --- |
| `target_absence` | `region`, `plate_frame`, `noise` (0 to 255) | Per-frame noise | `region_status`: `absent` inside, `unknown` overlapping |
| `moving_background` | `region`, `sprite_count` (up to 256), `sprite_size`, `max_speed` | Each sprite's start, direction, speed and color | `region_status`: `unknown`, and `added_objects: distractor` |
| `camera_shake` | `amplitude` | Each frame's whole-pixel offset | `translate`, with `camera_motion: shake` and every offset |
| `blur` | `max_radius` | Each frame's radius, from 1 | `identity` |
| `dropped_frames` | `count` | Which frames | `frame_map`, listing `removed` |
| `duplicated_frames` | `count` | Which frames | `frame_map`, listing `repeated` |
| `short_occlusion` | `region` | One rigid noise texture | `region_status`: `fully_occluded` inside, `partially_occluded` overlapping |

`region` is `{x, y, width, height}` in stored orientation, and each `region_status` also carries
`frames`, `region` and `overlap_geometry: unlocalizable`. Pixels outside a case's window keep their
parent's exact bytes. `short_occlusion` needs parent frames on both sides of its window, so a window
is required in practice. One `blur` draw is an edge-repeating box filter of `2 * radius + 1`, applied
per axis. `camera_shake` repeats the nearest pixel at an exposed edge.

Nothing here knows where a target is. A `region` must cover the target for the whole window, and for
`target_absence` the plate frame must not show it there. Both are the operator's claims, and a wrong
one makes a false negative interval. A moving target needs a rectangle covering its whole path.

### Membership

`corpus build` copies a case's `encounter_id`, `group_id` and `split` from its parent, into a sorted
`generated_cases` list beside `streams`. The recipe has no such keys, and declaring one is
`MANIFEST_INVALID`. A case therefore cannot leave its parent's split, and because split and rights
rules and every group, encounter and stream count read only `streams`, a case is never a new
encounter. A case holds its parent's rights by reference: `parent_stream_id` names them.

Each record also stores `source_sha256`, `transform`, `transform_revision`, `seed`, the resolved
`window`, `parameters` and `label_transform`. `src/ss_track/corpus/recipes.py` reads recipes and
builds these records. A build runs every transform without pixels, so a recipe its parent cannot
satisfy is refused before anything is staged, and `corpus build` needs no staged frames.

### Staging

`corpus stage` stages the streams, then each case from its parent's verified frames, under the same
lock, scratch and publish steps. `src/ss_track/corpus/generated.py` writes a case, and a repeated
stage reports it `unchanged`. A case is an ordinary bundle, read through `open_frame_bundle`, and
`corpus verify` covers it. Its record is the parent's with these differences:

| Field | Value |
| --- | --- |
| `stream_id` | The `case_id` |
| `generated` | Its `parent_stream_id`, `encounter_id`, `group_id` and `split`. `null` on a stream |
| `identity` | The parent's, plus `parent_bundle_sha256`, `recipe` and `label_transform`, with its own frames |

`bundle_sha256` covers that identity, so one recipe over one parent gives one hash whatever the
corpus or case is called. A case whose `parent_bundle_sha256` is not its parent's current bundle is
`BUNDLE_CONFLICT`. A case that changes no frame, such as a blur over a uniform clip, is `CASE_INVALID`
at staging, and that corpus version then needs replacing. Streams and cases finished before a refusal
stay staged.

A case keeps each frame's source index and PTS. `dropped_frames` leaves a gap in both, and reading a
removed frame is `FRAME_NOT_IN_BUNDLE`, so a removed operator seed frame needs a window that avoids
it. `duplicated_frames` repeats the previous frame's pixels at a frame's own index and PTS, with
`content_frame_index` naming the frame shown; a run of repeats all show the last real frame, and the
first frame of a selection is never repeated. Labels follow pixels, so a repeated frame takes the
labels of the frame it shows. Such a frame's PTS is no longer a capture time, so a `measured` parent
gives a `derived` case with no capture-clock evidence. A `missing` parent stays `missing`.

On the development host, on tmpfs, four cases of 300 1080p frames took 37 s on top of staging their
parent, about 33 frames per second, with a 227 MB peak. A blur of radius 9 costs about 65 ms per
frame. Each case holds a full copy of its raw frames: 1.8 GB here, the same as its parent.

### Reproducibility

`src/ss_track/corpus/transforms.py` and `region_transforms.py` hold the transforms. Each is a pure
function of frames, parameters and seed, in integer arithmetic only, and `seeded.py` derives every
random value with SHAKE-256 rather than a library generator whose stream may change.

`TRANSFORM_REVISIONS` versions each transform. A change to what one produces must raise its revision,
and `tests/corpus/test_transform_golden.py` fails until it does. The installed revision is stored in
each case, and a stored case of another revision, or of a transform that no longer exists, is
`TRANSFORM_REVISION_MISMATCH` before anything is written. A case is never silently regenerated as
different evidence.

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
| `SOURCE_RECORD_CHANGED` | A source's record differs from the one its corpus pinned, at stage or verify |
| `SPLIT_LEAKAGE` | A group, encounter, stream or case name is declared in two splits, two groups share a source, or a source or group sits elsewhere than a declared predecessor placed it |
| `STREAM_OVERLAP` | Two streams use the same frames of one source |
| `RIGHTS_CONFLICT` | Scenario sharing/sensitivity conflicts or a generated case lacks derivation permission |
| `RETENTION_EXPIRED` | The evaluation day is after a source's inclusive retention deadline |
| `CASE_INVALID` | A generated case does not fit its parent, or changes no frame of it |
| `TRANSFORM_REVISION_MISMATCH` | A stored case needs a transform revision this code does not provide |
| `RECORD_TAMPERED` | A manifest is missing, malformed or fails its seal, or a re-import finds changed stored bytes |
| `RECORD_SCHEMA_UNSUPPORTED` | A source, corpus or bundle uses an unsupported schema, or corpus source terms are absent |
| `DECODE_POLICY_MISMATCH` | A source or pin uses a decode policy other than the installed one |
| `IMPORT_CONFLICT` | The same source was imported with another declaration or decoder |
| `CORPUS_CONFLICT` | The `corpus_id` already exists with different content, or a superseded version differs from the seal its successor pinned |
| `CORPUS_NOT_BUILT` | The named corpus version or a version of its declared chain does not exist, or the identifier cannot name one |
| `DECODE_DRIFT` | A staging decode disagrees with the import record of its source |
| `BUNDLE_NOT_STAGED` | A stream has no staged frame bundle |
| `BUNDLE_CONFLICT` | A bundle was staged from a different corpus version, for a different stream, or from other parent frames |
| `STAGING_IN_PROGRESS` | Another run is staging this corpus version |
| `FRAME_CORRUPTED` | A staged file differs from the sealed index, is gone, or is not in it |
| `FRAME_NOT_IN_BUNDLE` | A bundle does not hold a frame index, including a frame a case dropped |
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
membership, rights and each stream's identity from build to `FrameRef`. `tests/corpus/test_lineage.py`
compares hand-built versions, and `test_lineage_build.py` covers linked builds from the declaration
to the exit status.
`tests/corpus/test_source_terms.py` covers retention boundaries at every entrypoint, unchanged
evidence across evaluation dates, explicit permission, strict declarations and legacy records.
`tests/corpus/test_verify_rights.py` replaces source records through the real importer and covers
verification from the command's exit status to the terms each refusal names.
`tests/corpus/test_transforms.py`, `test_transform_recipes.py` and `test_transform_golden.py` cover
each transform on hand-checkable frames and pin its bytes, and `test_recipes.py`,
`test_generated_cases.py`, `test_case_membership.py` and `test_case_frames.py` cover recipes and
cases from declaration to staged frames.

```bash
make test
```
