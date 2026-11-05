# Corpus

`ss-track import` turns one declared recording into an immutable, hashed source record.
`ss-track corpus build` groups imported sources into encounters and splits in one immutable corpus
version. `ss-track corpus stage` decodes each source once into one immutable frame bundle per
stream that every module reads, plus one derived bundle for each declared generated case, and seals
them into one frame set whose hash a scenario can pin. `ss-track corpus verify` proves those
frames are intact, are the ones the frame set names, and that the source records they rest on still
hold. Both refuse one recording held by two groups, or twice in one group, under different source
hashes.
`ss-track corpus hashes` and `ss-track corpus compare` show whether two hosts staged the same
bytes. Each command produces a complete record or a structured refusal, and none invents a value
it could not establish.
Annotation does not exist yet; the [plan](../plan.md) schedules it. The task records keep the accepted
tasks, their decisions and their acceptance evidence:
[import and corpus build](../records/0001-corpus-provenance-corpus-manifest-import.md),
[frame staging](../records/0002-corpus-provenance-frame-bundle-staging.md),
[split grouping](../records/0003-corpus-provenance-corpus-split-grouping.md),
[generated cases](../records/0004-corpus-provenance-generated-fixture-cases.md),
[source terms](../records/0006-corpus-provenance-source-terms-enforcement.md),
[rights verification](../records/0007-corpus-provenance-corpus-verify-rights.md),
[version lineage](../records/0008-corpus-provenance-corpus-version-lineage.md),
[unlinked versions](../records/0033-corpus-provenance-unlinked-version-report.md),
[frame sets](../records/0009-corpus-provenance-staged-frame-set.md),
[shared frames](../records/0010-corpus-provenance-duplicate-frame-detection.md),
[repeated frames in one group](../records/0032-corpus-provenance-group-repeated-frames.md),
[arm64 reproducibility](../records/0011-corpus-provenance-arm64-reproducibility.md),
[source terms amendment](../records/0014-corpus-provenance-source-terms-amendment.md),
[amendment impact](../records/0034-corpus-provenance-amendment-impact-report.md) and
[record read gate](../records/0016-data-contracts-record-read-gate.md).

The available corpus path imports declared sources and stages reviewed selections; it does not yet
form a large corpus from sibling video indexes or self-supervised selection. The specification and
plan define that future work, including source permissions and independent review. See the
[corpus formation planning record](../records/0038-adhoc-self-supervised-corpus-plan.md).

## Selected development workload

The owner-selected pilot is [Hawk attacks drone](https://commons.wikimedia.org/wiki/File:Hawk_attacks_drone.webm),
by Michael deAgonia, under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Credit the
creator, link the license and identify any changes when using the footage. The source description
suggests Swainson's hawk but marks the species uncertain; the task class is bird of prey. This edited,
aerial video has a moving landscape and an approaching bird that grows large in frame. Its unknown
range and target extent mean it does not establish sustained small-target performance.

After `make bootstrap`, run `make development-workload-prepare`. It downloads the pinned source,
checks its SHA-256, and prepares the source, contact sheet and declarations under
`$DATA_DIR/workload-selection/hawk-drone-pilot/`. The command needs network access and `ffmpeg`,
uses the configured data root, and refuses to replace a conflicting source or declaration. Re-running
it reuses matching files. Source terms, including no fixed retention end and permission for derived
frames, are in the recording declaration. Corpus sharing is restricted.

Import, build, stage and verify the prepared corpus from the project root:

```bash
SST_WORKLOAD_ROOT="$(.venv/bin/python -c 'from ss_track.core.paths import resolve_data_root; print(resolve_data_root())')/workload-selection/hawk-drone-pilot"
.venv/bin/ss-track import --source "$SST_WORKLOAD_ROOT/recording.yaml"
.venv/bin/ss-track corpus build --manifest "$SST_WORKLOAD_ROOT/corpus.yaml"
.venv/bin/ss-track corpus stage --corpus hawk-drone-pilot-v1
.venv/bin/ss-track corpus verify --corpus hawk-drone-pilot-v1
```

The half-open source windows are
`[0, 168)` for the candidate negative and `[432, 552)` for the positive. They belong to one
`development` group because they come from the same recording. The one-frame-per-second survey does
not prove negative absence in every frame: the pilot-labeling task reviews all frames and keeps
uncertainty visible. These are not frozen labels or held-out evidence. See the
[selection record](../records/0037-corpus-provenance-select-development-workload.md).

## Commands

```bash
ss-track import --source recording.yaml
ss-track import --source recording.yaml --amend-terms
ss-track corpus build --manifest corpus.yaml
ss-track corpus stage --corpus pilot-v1
ss-track corpus verify --corpus pilot-v1
ss-track corpus hashes --corpus pilot-v1 --run-id host-a
ss-track corpus compare --left a/staged-hashes.json --right b/staged-hashes.json --run-id compare-1
ss-track corpus preview --corpus pilot-v1 --stream enc01-cam0 --frame 0 --out sheet.png
```

Each command logs one JSON record and exits 0. A refusal exits 1 and has this form:

```json
{"status": "refused", "code": "PTS_NON_INCREASING", "message": "...", "details": {"frame_index": 3}}
```

`src/ss_track/core/paths.py` resolves the data root: `DATA_DIR` from the environment, then from
`.env` at the project root, then `.data`. Relative values resolve against the project root.

## Declarations

Each file is checked in full against its contract on read, `declaration/recording` 2.2.0 and
`declaration/corpus` 3.0.0, before any reader takes a value from it. Both reject unknown fields,
repeated keys, non-finite numbers and any other schema version, so a misspelled key cannot silently
drop a fact. A recording is schema 2 and a corpus is schema 3. There are no defaults for rights,
sensitivity, split or scenario rights: a declaration without them is refused, and `basis` has no
`unknown` value. A refusal names the contract version and the first violation by JSON pointer, a wrong
`schema_version` before anything else, and its details list up to 20 violations, as
[`contracts validate`](contracts.md#commands) reports them.

`src/ss_track/schema/validation/enforce.py` parses and validates;
`src/ss_track/corpus/declarations/fields.py` then gives the readers typed access. The readers keep
only rules the contract states as `x-rules`: a range status needs its value and method, a corpus
cannot supersede itself, a frame window must be non-empty, an absent range status means `unknown`,
and free text that is only whitespace is refused (`text`). The video-stream rule is not one of
these: it needs the file, so import enforces it. A value YAML read as a date is refused
where text belongs, such as an unquoted `holder: 2024-01-05` or `lens: 2024-01-05`, by the validator
itself, so `contracts validate` refuses it too. A date field such as `retain_until` takes an
unquoted date as its ISO text.

```yaml
# recording.yaml
schema_version: 2
source:
  path: clip.mkv             # relative to this file
  sha256: "<64 hex>"         # optional; declare it at capture, see Integrity limits
  # video_stream_index: 1    # video streams only; required when more than one
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

### Video stream selection

`source.video_stream_index` is the zero-based position among video streams, not among every stream
in the container. Omit it when the file has one video stream. A file with more than one is
`VIDEO_STREAM_UNSPECIFIED` until the declaration names one, and the refusal lists each stream's
index, container index, codec, width and height before any frame is decoded. An index that is not
one of those streams is refused the same way. Naming index 0 selects the first video stream and
leaves the field off the source record, so a one-stream import keeps its previous manifest bytes.
A later stream stores `sequence.video_stream_index`. Staging and redecode read that stream. The
index is not part of the shared decode policy, because a corpus pins one policy for every source.
The same file under another index is `IMPORT_CONFLICT`, and the details name
`sequence.video_stream_index`, because one source record holds one video stream. Audio is not
imported. `src/ss_track/corpus/decoding/streams.py` chooses the stream, and
`tests/corpus/sources/test_stream_selection.py` covers the refusal, each index and staging. The
[task record](../records/0040-corpus-provenance-import-stream-selection.md) holds the acceptance.

## Stored evidence

| Path | Content |
| --- | --- |
| `$DATA_DIR/import/<source-sha256>/source<ext>` | Read-only copy of the source bytes |
| `$DATA_DIR/import/<source-sha256>/manifest.json` | Sealed source manifest |
| `$DATA_DIR/import/<source-sha256>/replaced/<manifest-sha256>.json` | Each record an amendment replaced, under its own seal |
| `$DATA_DIR/import/.amendment.lock` | Empty lock that serializes amendments |
| `$DATA_DIR/corpus/<corpus-id>/manifest.json` | Sealed corpus manifest |
| `$DATA_DIR/corpus/<corpus-id>/frame-set.json` | Sealed record of every staged bundle |
| `$DATA_DIR/corpus/<corpus-id>/frames/<stream-id>/` | One read-only frame bundle |
| `$DATA_DIR/corpus/<corpus-id>/frames/<case-id>/` | One read-only bundle of a generated case |
| `$DATA_DIR/run/<run-id>/staged-hashes.json` | Sealed record of what one host staged |
| `$DATA_DIR/run/<run-id>/hash-comparison.json` | Sealed comparison of two hosts' records |

Import copies the source first, then hashes and decodes that copy, so the record describes exactly
the bytes retained. The finished directory is published by one rename, so a failure leaves nothing
that looks complete.

A sealed manifest carries `manifest_sha256`, a SHA-256 of its canonical JSON. It holds no clock time
or filesystem path, so the same source, declaration and decoder give identical bytes in any process.
Repeating an import or a build reports `unchanged`. Changing the declaration or the decoder for an
imported source is `IMPORT_CONFLICT`, and redefining a corpus is `CORPUS_CONFLICT`: a change needs a
new corpus version. Changed terms alone are [recorded by an amendment](#withdrawing-rights).

A source manifest records the hash and size, whether the hash was declared, rights, sensitivity,
capture facts, the decode policy and the sequence: container, codec, original and decoded dimensions,
source pixel format and bit depth, stored color tags, display rotation, interlaced frame count, time
base, one PTS per presented frame, discarded sample count, video stream count, the video stream
index when it is not the first, timestamp quality and completeness checks.

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

Grouping is the operator's judgment. Only [shared frames](#shared-frames) can show that two groups
are in fact related. `src/ss_track/corpus/versions/grouping.py` owns the rules that `corpus build` applies:

- A split is stated once, on a group, so every encounter and stream inherits it.
- An identifier declared in two splits is `SPLIT_LEAKAGE`. Repeated in one split it is
  `MANIFEST_INVALID`.
- A source used by two groups is `SPLIT_LEAKAGE` even inside one split, because groups that share a
  recording are not independent.
- One group may cut several encounters from one long recording, with adjacent windows. A source frame
  in two streams is `STREAM_OVERLAP`, because it would count twice in anything aggregated by
  encounter. A remux is a different source, so build cannot see it; stage and verify refuse that
  run inside the group with the same code.

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

### Version lineage

A version may name the one it supersedes with `supersedes`. Material already evaluated has been seen,
so `corpus build` compares the new version with that version and with every older version linked
behind it. `src/ss_track/corpus/versions/lineage.py` owns these rules, `predecessors.py` reads the declared
chain link by pinned link, and both read only source hashes, groups and splits:

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

A predecessor is read through its major's [comparison projection](#reading-sealed-records), so a
version may name one of any major, whatever its disposition: a `facts` or `retired` version still
guards its splits, and a move out of it is `SPLIT_LEAKAGE`, not a schema refusal. One whose major has
no projection, such as corpus major 1 or a newer major, still has its seal pinned in `supersedes`,
ends the chain, and is listed rather than failing the build. `compared_versions` may then be empty,
and `added`, `removed` and `kept` are empty when it is the named version:

```json
{"status": "built", "lineage": {"status": "linked", "supersedes": "pilot-v1",
 "supersedes_manifest_sha256": "...", "compared_versions": [], "added": [], "removed": [],
 "kept": [], "not_compared": [{"corpus_id": "pilot-v1", "reason": "other_schema", "stream_ids": []}]}}
```

`not_compared` appears only when a version in the chain was not compared, so a fully compared
chain reports what it did before.

A version that names nothing reports `{"status": "no_lineage"}`. That status is only the declared
chain. Another version on the same data root can place one of its sources in another group or split,
including `locked`, and the build still succeeds. The result then carries `unlinked`. `from` is the
other version and `to` is the one being built, the same shape as a move, and it is not a refusal:

```json
{"status": "built", "lineage": {"status": "no_lineage"}, "unlinked": {"placements": [
 {"source_sha256": "...",
  "from": {"corpus_id": "pilot-v1", "group_id": "site-a", "split": "development"},
  "to": {"corpus_id": "pilot-v2", "group_id": "held-out", "split": "locked"}}]}}
```

Placements are ordered by source hash, then by the other version's directory name. A manifest that
cannot be read, or whose major keeps no projection, is named under `not_compared` with reason
`unreadable` or `other_schema`, ordered by directory name. A version directory that cannot be read
is `unreadable` as well, and a name with a leading dot is not a version. When the corpus directory
itself cannot be listed, the result carries `{"scan": "unreadable"}` and the build still succeeds.
A version in the declared chain is never
listed: a move against that chain is still `SPLIT_LEAKAGE`, and an unprojected predecessor stays in
`lineage.not_compared`. The same source in the same group and split is not listed. A group's split
is not applied to an undeclared version, because this listing compares source hashes only.

The field is absent when there is nothing to report. It is not sealed, so a corpus hash does not
change when another version appears, and `unchanged` can still carry a new listing. Repeating the
build reports the data root as it is. `src/ss_track/corpus/versions/unlinked.py` reads
`$DATA_DIR/corpus/*/manifest.json` through `read_comparable`, and `lineage.py` compares placements.
One data root only. Versions outside `corpus/` are not listed. The
[unlinked-versions record](../records/0033-corpus-provenance-unlinked-version-report.md) holds the
accepted task.

The manifest seals `supersedes` as `{"corpus_id", "manifest_sha256"}`, and only when one was named, so
a version that names none keeps its hash and corpus manifests stay schema 3. Naming a predecessor on
an existing version is `CORPUS_CONFLICT`, as any change is. A named version that does not exist is
`CORPUS_NOT_BUILT` before any source is read, and so is one missing further back. A version rebuilt
differently under its old name no longer matches the seal its successor pinned, which is
`CORPUS_CONFLICT`. A superseded version therefore stays useful only while its `manifest.json` exists:
remove its frames, not its manifest. Only `corpus build` needs the chain whole: `corpus stage` and
`corpus verify` work on a version whose predecessors are gone, and say what that left unknown.

The comparison here is by source hash, so it does not see a remux placed elsewhere by a later version.
[Shared frames](#shared-frames) do.

### Shared frames

An `ffmpeg -c copy` remux of one recording imports as a different source with every decoded frame
identical. Bundle hashes do not find it either, because a bundle's identity includes its source hash
and time base. `corpus stage` and `corpus verify` therefore compare the frame hashes in sealed
indexes, which needs no decode. `src/ss_track/corpus/bundles/shared_runs.py` owns the rule, and
`src/ss_track/corpus/bundles/duplicate_frames.py` reads the indexes.

| Two streams | Result |
| --- | --- |
| In two groups, sharing a run, in any splits | `SPLIT_LEAKAGE` |
| In one group of one version, sharing a run, in one encounter or two | `STREAM_OVERLAP` |
| In one group across linked versions, a copy replacing its original | Accepted. No version counts the frame twice |
| Sharing a shorter or uniform stretch, in one group or two | Accepted |

A run is `MIN_SHARED_FRAMES`, eight, different frames in a row and in the same order. A frame held in
place counts once, so a clip that repeats each frame still matches, and a copy holding frames for
longer matches too. Eight different frames rule out what independent clips really share: one black
frame, a long black lead-in, black cutting to white, or a blinking screen. Only streams are read. A
generated case stays in its parent's group and holds its parent's frames or new ones, so it is never
compared with its parent.

Every stream is compared with the rest of its version and with every stream of the versions linked
behind it. The same group is reported only inside the version being checked, so a copy that replaces
its original there is accepted. A different group is reported either way, so a version that keeps
only the copy, in another group, is refused by the version behind it. Predecessors are not compared
with each other: a version answers for itself. A version that both repeats a recording inside a
group and shares it with another group is `SPLIT_LEAKAGE`, and that refusal names only the pairs in
different groups. A refusal names every pair of one kind at once, widened to all the two streams
share from the first run found:

```json
{"status": "refused", "code": "SPLIT_LEAKAGE", "message": "...", "details": {"corpus_id": "pilot-v2",
 "min_shared_frames": 8, "shared_runs": [{"frame_sha256": "...", "frame_count": 100, "streams": [
  {"corpus_id": "pilot-v1", "stream_id": "enc01-cam0", "group_id": "site-a", "split": "development",
   "first_shared_frame": 0},
  {"corpus_id": "pilot-v2", "stream_id": "enc09-cam0", "group_id": "held-out", "split": "locked",
   "first_shared_frame": 0}]}]}}
```

The same details name a run held twice inside one group. Each stream carries the frame it shows
first:

```json
{"status": "refused", "code": "STREAM_OVERLAP", "message": "...",
 "details": {"corpus_id": "pilot-v2", "min_shared_frames": 8,
 "shared_runs": [{"frame_sha256": "...", "frame_count": 100, "streams": [
  {"corpus_id": "pilot-v2", "stream_id": "enc01-cam0", "group_id": "site-a", "split": "development",
   "first_shared_frame": 0},
  {"corpus_id": "pilot-v2", "stream_id": "enc02-cam0", "group_id": "site-a", "split": "development",
   "first_shared_frame": 9}]}]}}
```

`frame_sha256` is the first shared frame, and `frame_count` counts a held frame once. Frame hashes
exist only after staging, so a stage checks them once its streams are staged and before its cases.
A refusal leaves those streams staged, with no case and no frame set, and that version needs
replacing: keep one copy of the recording. A later version may put the other copy in that group in
its place, and adjacent windows of one recording still share no frame. Independent clips that truly
share eight frames, such as a camera's start-up animation, are refused the same way, and a
`selection` that starts after them is the way past it. No flag overrides the rule.

Both commands report what they compared, because a version not compared is unknown, not clear:

```json
{"status": "staged", "shared_frames": {"min_shared_frames": 8, "compared_versions": ["pilot-v1"],
 "not_compared": [{"corpus_id": "pilot-v0", "reason": "bundles_removed", "stream_ids": ["enc01-cam0"]}]}}
```

| `reason` | Meaning |
| --- | --- |
| `no_frame_set` | The version never finished staging, so nothing compared it. A refused version is one, so it cannot block the version that repairs it |
| `bundles_removed` | These streams have no bundle. The version's other streams were compared |
| `manifest_removed` | The manifest is gone, and every version behind it is unknown too |
| `other_decode_policy` | The version was staged under another decoder. A match still refuses, but finding none proves nothing, because its frames may hash differently |
| `other_schema` | These streams' bundles, or for a lineage the whole version, are of a major that keeps no [comparison projection](#reading-sealed-records), so their facts are unknown. The version's other streams were compared |

A rebuilt predecessor is `CORPUS_CONFLICT`, a damaged record `RECORD_TAMPERED`, and a bundle of
another stream or version `BUNDLE_CONFLICT`: those are refused rather than compared. A predecessor
and its bundles are read through their majors' projections, so one of another major is compared
when its major holds the facts, and named under `other_schema` when it does not; a predecessor
manifest with no projection ends the chain there. `corpus verify` repeats the check because a
predecessor staged after its successor was not there to compare with, and that successor's frame set
stays as it was. Stage and verify match a frame set that exists before the run, so a replaced
bundle stays `FRAME_SET_MISMATCH`. A first stage refuses a repeated run before writing cases or a
frame set. When verify finds no frame set, it names a repeated run before reporting that staging
has not finished. A generated case is not written after a refusal, so verify then names the missing
bundle. The result is never sealed: it depends on what a data root holds, and a frame set must not.

What this cannot see:

- A re-encoded copy shares no frame hash. `near-duplicate-detection` in the [plan](../plan.md) covers
  it.
- Windows of a copy that share no frame, such as `[0, 12)` of one and `[12, 24)` of the other. A
  stream with fewer than eight different frames cannot hold a run at all.
- A copy that replaces its original in the same group of a linked version. No version holds both,
  so none counts a frame twice.
- A version no chain links to. [Version lineage](#version-lineage) lists a shared source hash.
  This check still does not read that version's frames.

On the development host, reading a sealed index of a million frames takes about 2 s, and searching
ten million hashes across 100 streams took 11 s, so the check costs about 3 s and 600 MB per million
frames compared. A million 1080p frames is 6 TB of bundles. The same-group check adds a membership
test per candidate stream, not per frame. The
[repeated-frames record](../records/0032-corpus-provenance-group-repeated-frames.md) holds the
accepted task.

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

`src/ss_track/corpus/sources/terms.py` owns the shared check. The Python build, stage and verify functions
accept keyword-only `today: date | None` for deterministic evaluation; commands use the UTC day
captured once at operation start. This evaluation day is never sealed, so valid reruns keep the same
bytes and hashes. The declared deadline is retained in source and corpus records.

`rights.derived_frames: false` permits ordinary stream staging but refuses any generated-case recipe
with `RIGHTS_CONFLICT`, naming its parent stream and source. `grouping.py` checks this before recipe
execution or corpus publication. Both new fields are required. Quoted and unquoted YAML dates
normalize to the same ISO string. Numbers, timestamps, invalid dates and string booleans are refused.

Source manifests now use schema 2. Old source manifests and corpus records missing the new terms
are refused with `RECORD_SCHEMA_UNSUPPORTED` and the `facts` disposition; their terms are never
guessed. A
[re-import over an old source](#reading-sealed-records) is refused the same way. An old source record
gains its terms through an [amendment](#withdrawing-rights), and a new corpus version then uses it. No
automatic migration runs.

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

`_require_sources_hold` in `src/ss_track/corpus/bundles/staging.py` is this one check for both
commands, and each stream is checked, which covers every generated case because a case holds its
parent's rights. Retention comes first and reads only the corpus, so an expired source stays
`RETENTION_EXPIRED` after its directory is removed. Otherwise a missing record is
`SOURCE_NOT_IMPORTED`, an unreadable one is `RECORD_TAMPERED`, and one of another schema is
`RECORD_SCHEMA_UNSUPPORTED`.

### Withdrawing rights

`ss-track import` never changes an imported record. Declaring other terms for an imported source is
`IMPORT_CONFLICT`, which records nothing, names each term in `changed_terms` and, when only terms
differ, names the command that records them:

```bash
ss-track import --source recording.yaml --amend-terms      # now declaring the new terms
```

```json
{"status": "amended", "changed_terms": ["rights.sharing"], "decode_policy_current": true,
 "manifest_sha256": "...", "replaced_manifest_sha256": "...", "replaced_path": "...",
 "source_sha256": "...", "manifest_path": "..."}
```

`src/ss_track/corpus/sources/amendment.py` replaces `rights` and `sensitivity` and writes the
current schema. Every other section is carried from the existing record, so an amended record equals
a fresh import of the same declaration under the same decoder. It keeps the old record in
`replaced/` first and then replaces the manifest by one rename, so a run killed at any point leaves
one whole record and a rerun finishes it. A repeat reports `unchanged`. Restoring the old terms
restores the old seal, so a version pinning it verifies again. Amendments carry no date, so the kept
records have no recorded order.

An amendment finds its source by the bytes at `source.path`, or by a declared `source.sha256` once the
original has gone. With the file present the two must agree, as in a plain import. It does not read
the stored copy, so a withdrawal stays recordable after that copy is removed. `corpus build` hashes it
again regardless. `sha256_declared` is carried over, because it states what import was told.

It does not consult the installed decoder either, because a withdrawal must not wait for a decode of
the material it withdraws. The record keeps its policy and `decode_policy_current` reports whether that
is the installed one. When it is not, `corpus build` refuses the record with `DECODE_POLICY_MISMATCH`
until it is decoded again.

| Declaration or record | Result |
| --- | --- |
| Bytes with no import record | `IMPORT_CONFLICT`, and nothing is imported |
| Changed `capture` or capture-clock evidence | `IMPORT_CONFLICT`, naming `changed_facts` |
| File that contradicts its declared hash | `SOURCE_HASH_MISMATCH` |
| File gone and no declared hash | `SOURCE_NOT_FOUND` |
| Schema 1 record holding every current decoded fact | Gains the terms and schema 2. Schema 1 is a `facts` major, read as written through `read_stated` |
| Schema 1 record short of a decoded fact | `RECORD_SCHEMA_UNSUPPORTED`, naming each `violations` entry of the current source contract the carried record breaks, with the remedy: [`--redecode --amend-terms`](#redecoding-under-a-new-policy) together |
| Any newer record | `RECORD_SCHEMA_UNSUPPORTED` |

Every corpus version that pinned the old record then refuses at `corpus stage` and `corpus verify`.
The amendment lists those versions on this data root. `impact` is absent when nothing needs
reporting, including a repeat that reports `unchanged`. Versions are ordered by directory name, and
each names the frames directory where that version's bundles are stored, whether or not it currently
holds files. A version is listed once however many of its streams pin the record. A manifest that
cannot be read, a version directory that cannot be read, and a major that keeps no projection are
named under `not_compared`, ordered by directory name, and are not skipped. A name with a leading
dot is not a version. When the corpus directory itself cannot be listed, `impact` is
`{"scan": "unreadable"}` and the amendment is still recorded. The listing deletes nothing and is
not part of the source record. Its frames stay on disk until an operator removes them.

```json
{"status": "amended", "impact": {"versions": [
 {"corpus_id": "alpha", "frames_directory": ".../corpus/alpha/frames"}],
 "not_compared": [
 {"corpus_id": "broken", "reason": "unreadable"},
 {"corpus_id": "legacy", "reason": "other_schema"}]}}
```

`src/ss_track/corpus/versions/impact.py` reads `$DATA_DIR/corpus/*/manifest.json` through
`scan_corpus_manifests` and matches `source_manifest_sha256` on each major's comparison projection.
Corpus majors 2 and 3 carry that pin. Corpus major 1 keeps no projection, so a version of that
major is named `other_schema` rather than matched on its sequences. `--redecode` lists the same
way when it replaces a record. The
[amendment-impact record](../records/0034-corpus-provenance-amendment-impact-report.md) holds the
accepted task.

Rebuilding it is `RIGHTS_CONFLICT` if its scenario now asks too much, or `CORPUS_CONFLICT`, so
continuing needs a new corpus version, which may supersede the refused one.
An amendment reaches one data root: another host keeps its record until it is amended there, and
`corpus compare` reports the difference.

Verification compares records. It does not establish that a declaration is true, and a withdrawal
nobody recorded stays invisible to it.

## Canonical decode policy

`src/ss_track/corpus/decoding/decode_policy.py` owns `DecodePolicy`, and `decode.py` applies it in
the one strict inspection of a source. The decoder is PyAV, pinned exactly in `pyproject.toml`, and
its wheels bundle FFmpeg with no system dependency. `tests/corpus/decoding/test_decoder_pin.py`
keeps the exact pin and the arm64 Linux and macOS wheels true of `uv.lock`. The output pixel format
is `rgb24`. The policy hash covers all of these options:

| Option | Reason |
| --- | --- |
| `fflags=nofillin` | Without it the demuxer invents PTS from a guessed frame rate for files that store none |
| `err_detect=explode` | Without it decoders conceal damaged blocks and return a frame as if nothing happened |
| `flags=bitexact`, one thread | Removes decoder choices that can vary between runs |
| `idct=simple` | `bitexact` leaves the inverse DCT to the CPU, so without this MJPEG, MPEG-1, MPEG-2, MPEG-4, H.263, MSMPEG-4, DV and DNxHD decode differently on arm64 |
| `ACCURATE_RND`, `BITEXACT` conversion | Without them FFmpeg's SIMD and C paths round differently, so pixels depend on the CPU |
| `FULL_CHR_H_INT`, `FULL_CHR_H_INP` conversion | Without them chroma is repeated instead of interpolated and lands in the wrong place |

That inspection reads the video stream named under
[Video stream selection](#video-stream-selection).
The shared policy hash does not include the index.

Exit status alone is not enough evidence, so `inspect_media` also refuses on a demuxer corrupt-packet
flag, a decoder corrupt-frame flag, and any FFmpeg ERROR log. The log is the only signal for an FFV1
CRC mismatch and for most truncated Matroska files. FFmpeg's repeat filter stays off while reading,
because it would hide a second identical error.

Decoded dimensions are the stored dimensions: the policy does not apply display rotation, so
`display_rotation_degrees` is a fact for label tools, not a transform that modules receive. A tool
that honors rotation must map its coordinates back to the stored orientation.

`src/ss_track/corpus/decoding/pixels.py` owns the conversion to `rgb24`. It honors the stored color matrix,
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

A record states the policy that produced it. A new policy revision therefore refuses every earlier
record: `corpus build` and `corpus stage` with `DECODE_POLICY_MISMATCH`, and `import` of the same
source with `IMPORT_CONFLICT`. An [amendment](#withdrawing-rights) still records new terms, and the
record keeps its policy.

### Redecoding under a new policy

```bash
ss-track import --source recording.yaml --redecode                   # carries its terms over
ss-track import --source recording.yaml --redecode --amend-terms     # takes terms from this file too
```

```json
{"status": "redecoded", "source_sha256": "...", "manifest_sha256": "...",
 "replaced_manifest_sha256": "...", "replaced_path": "...", "changed_terms": [],
 "decode_policy_current": true, "manifest_path": "..."}
```

`src/ss_track/corpus/sources/redecode.py` decodes the one stored copy again under the policy
installed today, and writes the result the same way an amendment does: under the shared
`exclusive_source_lock`, keeping the replaced record in `replaced/` first and then replacing the
manifest by one rename, so a run killed at any point leaves one whole record and a rerun finishes
it. A repeat reports `unchanged`. The stored source is read, decoded and left byte-identical; its
hash is checked again first, and a source that no longer matches it is `SOURCE_HASH_MISMATCH`.

A plain `--redecode` carries the existing `rights` and `sensitivity` forward unchanged, exactly as
recorded, because terms are never invented. A record whose carried terms then fall short of the
current major, such as a schema 1 record still missing `retain_until` and `derived_frames`, is
`RECORD_SCHEMA_UNSUPPORTED` naming `--amend-terms`. Adding `--amend-terms` takes the terms from the
declaration instead, exactly as a plain amendment does, so a record too old for `--amend-terms`
alone -- one still short a decoded fact too -- reaches the current major only this way, because the
decode and the declared term arrive together. `require_current_facts`, shared with `amendment.py`,
raises this refusal from either path.

Every corpus version that pinned the old record then refuses at `corpus stage` and `corpus verify`
with `SOURCE_RECORD_CHANGED`, exactly as after an amendment, and the result lists them in `impact`
the same way. A new corpus version built after the redecode accepts the source. `capture` and
capture-clock evidence cannot change through a redecode either, so a declaration that disagrees
with the carried record is `IMPORT_CONFLICT`.

## Frame bundles

`corpus stage` writes one bundle per stream of a built corpus, with the same strict decode as
import. Pending streams of one source share that decode. `src/ss_track/corpus/bundles/staging.py`
groups them, `src/ss_track/corpus/bundles/bundle_writer.py` fans the frames out, and
`src/ss_track/corpus/bundles/publish.py` publishes that pass together.

| Path | Content |
| --- | --- |
| `00000012.rgb24` | One frame: tightly packed RGB rows, `width * height * 3` bytes, no padding |
| `manifest.json` | Sealed record with the frame index, per-frame SHA-256 and `bundle_sha256` |

The decode reads every frame, including frames no stream stores. Seeking to a window would skip the
proof that the stored source still matches its import. Only a frame inside a pending selection is
converted. Each stream keeps its own converter and sees only its own frames, so its pixels match a
stage of that stream alone. A build refuses a frame named by two selections. The writer still stores
that frame in each selection, which keeps the bundle hash equal to a stage of that stream alone.

Frame names and `frame_index` are positions in the source sequence, so a selection keeps them: a
window `[5, 9)` holds frames 5 to 8, and labels stay aligned with any window. A bundle holds only
its selection.

`bundle_sha256` covers the `identity` block: source hash, decode policy hash, pixel format, width,
height, bytes per frame, time base, selection and the ordered index of frame index, PTS and frame
hash. Nothing else enters it, so two stagings of one source and window under one policy give one
hash, whatever the corpus or stream is called. The record separately holds the source pixel format
and bit depth, `precision_reduced`, stored color tags, display rotation, interlaced frame count,
timestamp quality, its `stream_id` and the links to its corpus and source manifests.

Staging trusts nothing from before it ran. It re-hashes each stored source once on a pass, requires
the installed decode policy, requires the source record the corpus pinned, and refuses with
`DECODE_DRIFT` if this decode disagrees with the import record in any field. One stream is named
`stream_id`. Several are named `stream_ids`, in corpus order. It checks free space for the frames
those pending streams will store before decoding, because raw frames dwarf their source: 14 MB of
H.264 became 3.5 GB at 1080p. On the development host that clip staged at 74 frames per second with
an 87 MB peak.

Each new bundle is written in a scratch directory. The pass renames them into place only after the
source has decoded and every manifest is sealed, so a failure before that leaves none of them. A
rename that fails, or an interruption while they are moving, removes the ones already renamed.
Scratch that never moved is removed with its temporary directory. A source published before the
failure stays staged, including a stream listed after the one that failed, and repeating the command
decodes only a source that still has a missing bundle. One staging runs per corpus, under a lock
the kernel releases however a run ends. A second run gets `STAGING_IN_PROGRESS`, and the next run
to take the lock removes what a killed run left behind. A kill that the process cannot catch can
leave a complete bundle of that pass; the next stage keeps it and decodes the source again only for
what is still missing.

Repeating `corpus stage` re-hashes each existing bundle and reports `unchanged`. A source whose
streams are all present is left unread. A reduced-precision or untagged-matrix warning is logged
once for the source, naming every stream of the pass. A bundle staged from
another corpus version, or one sitting under another stream's path, is `BUNDLE_CONFLICT`, so moving a
bundle cannot carry frames into another split. A bundle is immutable: frames are mode `0444`, the
directory is `0555`, and a damaged one is never repaired in place. Remove it with
`chmod u+w <bundle> && rm -rf <bundle>`, then stage again; the hash comes back the same. `chmod`
applies to the directory only. A generated case may hard-link a parent frame, and changing that
file's mode would change the parent frame too.
`tests/corpus/bundles/test_single_pass.py` checks one decode per source, hashes that match a
per-stream stage, and a failure that publishes nothing from the pass. The
[task record](../records/0036-corpus-provenance-staging-single-pass.md) holds the acceptance.

### Frame set

A finished stage seals one record of what it staged, so a scenario pins a single hash rather than a
list of bundles. `src/ss_track/corpus/bundles/frame_set.py` owns it. `corpus stage` writes it after
the last bundle and under the staging lock, and both `corpus stage` and `corpus verify` report its
seal as `frame_set_sha256`:

```json
{"kind": "ss-track.frame-set", "schema_version": 1, "corpus_id": "pilot-v1",
 "corpus_manifest_sha256": "...", "manifest_sha256": "...", "bundles": [
  {"stream_id": "enc01-cam0", "parent_stream_id": null, "bundle_sha256": "...",
   "source_sha256": "...", "source_manifest_sha256": "..."},
  {"stream_id": "enc01-cam0-shake", "parent_stream_id": "enc01-cam0", "bundle_sha256": "...",
   "source_sha256": "...", "source_manifest_sha256": "..."}]}
```

`bundles` is sorted by name and holds every stream and generated case, and a case states the source
record of its parent. The record holds no path, clock or run identity, so one corpus version staged on
any data root gives identical bytes. The corpus manifest hash in it ties the frame set to the
version's membership and splits, so two versions sharing every bundle still have different frame sets.
A source's identity is part of it: a remux of a source gives a new hash over identical frames.

The record is written once and never rewritten:

| Found | `corpus stage` | `corpus verify` |
| --- | --- | --- |
| Every bundle, no frame set | Writes it, status `staged`, each bundle `unchanged` | `FRAME_SET_NOT_STAGED` |
| A bundle missing | Stages it again, then compares | `BUNDLE_NOT_STAGED`, naming the first |
| Another bundle under a named stream | `FRAME_SET_MISMATCH`, record untouched | `FRAME_SET_MISMATCH` |
| Anything undeclared among the bundles | `FRAME_SET_MISMATCH`, writing no record | `FRAME_SET_MISMATCH` |

A stage that stops early, or that [shared frames](#shared-frames) refuse, leaves no frame set, because
the record is the last thing written. A finished bundle stays staged, and repeating the command writes
the record. A frame set from an earlier complete
stage stays when a bundle is later removed: it still states what the corpus staged, and `corpus
verify` refuses until that bundle is back. A corpus staged before frame sets existed behaves as the
first row, so one `corpus stage` adds the record without touching a bundle.

A mismatch names every bundle at once, and also states both frame-set hashes and both corpus manifest
hashes, because a record of another corpus state differs with an empty `bundles` list:

```json
{"status": "refused", "code": "FRAME_SET_MISMATCH", "message": "...", "details": {
 "corpus_id": "pilot-v1", "frame_set_sha256": "...", "found_frame_set_sha256": "...",
 "frame_set_corpus_manifest_sha256": "...", "corpus_manifest_sha256": "...", "bundles": [
  {"stream_id": "enc01-cam1", "reason": "replaced", "frame_set_bundle_sha256": "...",
   "bundle_sha256": "..."}, {"stream_id": "stray", "reason": "unnamed"}]}}
```

The reason is `replaced`, `unnamed` for something the frame set does not name, or `missing` for a line
the corpus does not declare. A replaced parent of a generated case is `BUNDLE_CONFLICT` naming the case
before this comparison runs. Names beginning with a dot are ignored, because an identifier cannot begin
with one and they are the staging lock and scratch.

To recover from `replaced`, remove the bundle and stage it again, and the hash comes back. If the
mismatch stays, this host does not reproduce the bundle: build a new corpus version. Deleting
`frame-set.json` instead writes a new hash over whatever is on disk.

A seal is not a signature. It shows a record matches itself, so that deletion, or any rewrite of the
record, is visible only to a hash held elsewhere. The frame set therefore protects a run through the
scenario that pins it. It does not bind a bundle's own record to the corpus declaration beyond the
checks that open it, and `open_frame_bundle` opens any bundle directory without consulting it.

### Across hosts

A pin says only that two hosts differ. `ss-track corpus hashes` first runs everything `corpus
verify` does, then writes what this host staged to `$DATA_DIR/run/<run-id>/staged-hashes.json`: each
bundle and every frame's index, PTS and hash, each source's codec and pixel format, and the host's
machine, system and Python. `src/ss_track/corpus/hosts/host_hashes.py` owns it. Host facts stay out
of the frame set, which must be one hash on any host, and no frame moves between hosts.

`ss-track corpus compare` reads two such records and keeps its result in `hash-comparison.json`, under
its own run. `src/ss_track/corpus/hosts/hash_comparison.py` owns it. It compares frame sets first, because
an equal hash proves every bundle equal:

```json
{"status": "identical", "corpus_id": "pilot-v1", "source_count": 71, "bundle_count": 78,
 "sources": [], "left": {"host": {"machine": "x86_64", "system": "Linux", "python": "3.12.15"},
  "frame_set_sha256": "...", "corpus_manifest_sha256": "..."}, "right": {"...": "..."}}
```

Unequal hashes are a valid negative result, not a fault. The record is written first, then the command
refuses with `STAGED_HASHES_DIFFER` and exits 1, naming each source:

```json
{"status": "refused", "code": "STAGED_HASHES_DIFFER", "message": "...", "details": {
 "status": "different", "sources": [{"source_sha256": "...", "codec": "mjpeg",
  "source_pixel_format": "yuvj420p", "source_record_differs": false, "bundles": [{
   "stream_id": "enc01-cam0", "parent_stream_id": null, "left_bundle_sha256": "...",
   "right_bundle_sha256": "...", "frame_count": 12, "differing_frames": 9,
   "first_differing_frame": 1}]}]}}
```

| Found | Meaning |
| --- | --- |
| `differing_frames` above 0 | These frames differ in PTS or hash, or only one host has them |
| `differing_frames` of 0, with a `parent_stream_id` | Only a case's parent moved |
| `source_record_differs` with no `bundles` | The hosts agree on every frame and disagree on what import recorded |
| `sources` empty | The frame sets differ for a reason neither record holds. It stays `different` |

Records of different corpora, decode policies, sources or bundles are `HASHES_NOT_COMPARABLE`, naming
which, and write nothing, because no byte comparison answers that question. Both records must come
from one set of source bytes. Two writes of the fixed corpus on one host differ in 45 of 71 files, all
Matroska or WebM, whose random identifiers change, and a write on arm64 differs from x86-64 in the
packets of 41 of 71, so a host that regenerates its media compares different sources.

`corpus compare` treats any two hosts alike and `left` and `right` name them, so a cross-architecture
claim also needs two different `machine` values.
A record is sealed against accidents, not against a person, like every seal here.

`tests/corpus/hosts/_fixed_sources.py` holds the fixed corpus, `arch-fixed-v1`: 71 sources through 20
decoders and 28 pixel formats, with odd and short-row sizes, several color matrices and chroma
sitings, plus all seven transforms, and `tests/corpus/hosts/_fixed_corpus.py` holds the commands that
write and stage it. Each row states the format it must decode as. Its sources are written by one
host and carried to the other, so no binary enters the repository, and the [developer tooling
page](developer-tooling.md#quality-gates) describes the job that does this.

| Host pair | Result |
| --- | --- |
| x86-64 and emulated arm64, `neoverse-n2`, `cortex-a72` and `max`, this policy | Identical: every one of 78 bundles |
| x86-64 and emulated arm64, the policy without `idct=simple` | 14 of 71 sources differ, in 101 of 144 frames: every MJPEG, MPEG-1, MPEG-2, MPEG-4, H.263, MSMPEG-4, DV and 8-bit DNxHD source. Decoded planes differed in exactly those frames, so the difference was decoding and not conversion |
| x86-64 and GitHub-hosted arm64 hardware, `ubuntu-24.04-arm`, this policy | Identical: every one of 78 bundles, 879 frames |

Emulation runs the wheel's real arm64 machine code through QEMU's user mode, and the three CPU profiles
span NEON alone up to the newest features QEMU offers. The hardware row is one hosted runner, whose CPU
model the run does not record, and the workflow repeats it on every pull request and push to `main`,
failing on any difference. Neither row reaches a host that did not stage the corpus:
`select-reference-host` in the [plan](../plan.md#select-reference-host) compares each candidate on the
candidate itself. Pinning the IDCT changed no x86-64 pixel on any source. What moved is arm64, and the
policy hash, as any option change does.

### Reading frames

```python
from ss_track.corpus import open_frame_bundle

bundle = open_frame_bundle(data_root / "corpus" / "pilot-v1" / "frames" / "enc01-cam0")
ref = bundle.frame_ref(12)         # FrameRef for frame 12 of the source sequence
pixels = bundle.read_frame(12)     # packed RGB bytes, compared with the sealed hash on every read
```

`src/ss_track/corpus/bundles/frames.py` owns this access, and `bundle_reader.py` opens a bundle from
its sealed record and checks where it was staged from. `frame_refs()` yields every reference in
presentation order. A `FrameRef` carries stream, source hash, frame index, PTS, time base, timestamp
quality and capture-clock evidence, dimensions, pixel format, transform, bundle hash, frame name and
frame hash, plus `content_frame_index`, the parent frame whose pixels it shows. `transform` is
`identity` for a stream, whose pixels are as stored, with display rotation staying a record fact,
and the transform name for a generated case. An absent PTS stays `null`. An index the bundle does
not hold is `FRAME_NOT_IN_BUNDLE`.

### Dataset descriptors

`ss-track corpus describe --corpus <id> --declaration <dataset.yaml>` verifies the staged corpus and
writes a Croissant 1.1 document under `$DATA_DIR/corpus/<id>/descriptions/restricted/`.
`corpus/descriptors/descriptor.py` builds the document and
`corpus/descriptors/descriptor_publish.py` publishes it. The operator provides `declaration/dataset`
1.0.0: `schema_version`, `title`, `description`, `license`, `citation`, `address` and
`publication_date`. All fields are required. The declaration is outside the corpus seal and does not
change a cohort key.

The directory contains `croissant.json`, `dataset-card.md`, `contracts.json`, the frozen contract set,
and three CSV record sets: `streams`, `bundles` and `frames`. Each CSV record has one `record` column
containing JSON. Streams include the sealed source record and its terms, bundles include their sealed
frame index, and frames include paths, timestamps, hashes and raw pixel layout. Paths are relative to
the descriptor directory; retain the corpus directory structure when moving the files. Headerless
`rgb24` pixels are read through the frame-bundle contract, not directly through Croissant. Generated
cases are marked as such and are never counted as encounters. The card states that selection and
completeness remain unverified.

`--visibility public` requires public scenario sharing and a license. `schema/views/disclosure.py`
keeps a value only when the newest contract marks that field `x-sensitivity: public`. An unmarked
field is absent, and a `restricted` or `sensitive` field hides its children.
`corpus/descriptors/descriptor_public.py` applies that projection to streams outside the locked
split. A consumer can see stream identity, split, group and encounter, permitted terms (`basis`,
`sharing`, `derived_frames`, `retain_until` and the sensitivity level), layout, the frame index and
non-locating generated-case parameters such as a blur radius. Rights-holder names, retention text,
notes, capture descriptions, source file names and source hashes stay out, as do image regions and
label geometry. A declared hash and the installed decoder version are unmarked, so they stay out
too. Locked streams and cases derived from them contribute counts only, with no path, hash or
per-sequence fact. The frame-set bundle list remains restricted and is not copied. A restricted
corpus is refused with no identifying values in the refusal. The [public fields
record](../records/0026-data-contracts-public-descriptor-fields.md) holds the review.

The same inputs leave that directory in place, so a repeat yields identical bytes. A later
description whose generated bytes differ, including a corrected title or license, replaces that
visibility only. The new tree is written completely, the published directory moves to
`.replaced-<visibility>`, and the new tree takes the published name. A reader sees one generation,
or no directory during that swap. The previous tree is removed after the new one is in place. If a
run is killed first, the next description restores that tree when the published directory is absent,
and removes it when the published directory is already the new generation. Public and restricted
directories stay separate, and a sibling `.describe.lock` serializes publication without becoming
part of either descriptor. The command checks source terms, the frame set and every frame before it
writes. A refusal leaves the published directory unchanged, and neither the other visibility nor any
sealed record is modified. The [task record](../records/0024-data-contracts-dataset-descriptor.md)
and the [refresh record](../records/0027-data-contracts-descriptor-refresh.md) record acceptance.
`tests/corpus/descriptors/test_descriptor.py` and
`tests/corpus/descriptors/test_public_descriptor.py` test both views and use the separately locked
`croissant` extra to validate and load the records; the Croissant CI job runs that extra
independently of the runtime dependency closure.
`tests/corpus/descriptors/test_descriptor_refresh.py` and
`tests/corpus/descriptors/test_descriptor_publish.py` test replacement, a refusal that keeps the
published tree, and a swap interrupted before it finishes.

## Verification

`corpus verify` first checks the [source terms](#withdrawing-rights), then compares the bundles with
the [frame set](#frame-set), then repeats the [shared-frame check](#shared-frames), then re-hashes
every frame of every stream and names each damaged file with its stream:

```json
{"status": "refused", "code": "FRAME_CORRUPTED", "message": "...", "details": {"damaged_count": 1,
 "frames": [{"stream_id": "enc01-cam0", "frame": "00000003.rgb24", "reason": "hash_mismatch"}]}}
```

The reason is `hash_mismatch`, `missing` or `unexpected_file`. `damaged_count` is always complete; the
list names the first 32. A stage over a damaged bundle and a read of a damaged frame refuse the same
way, so a changed frame cannot reach a module. A case frame that is a hard link of its parent is the
same inode: damage is named once for every bundle that holds that file, and removing one name leaves
the others. A frame the case copied is named alone.

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
parent's exact bytes and, on one filesystem, that frame's disk space. `short_occlusion` needs parent
frames on both sides of its window, so a window
is required in practice. One `blur` draw is an edge-repeating box filter of `2 * radius + 1`, applied
per axis. `camera_shake` repeats the nearest pixel at an exposed edge.

Nothing here knows where a target is. A `region` must cover the target for the whole window, and for
`target_absence` the plate frame must not show it there. Both are the operator's claims, and a wrong
one makes a false negative interval. A moving target needs a rectangle covering its whole path.
[Case preview](#case-preview) draws that rectangle on one staged frame.

### Membership

`corpus build` copies a case's `encounter_id`, `group_id` and `split` from its parent, into a sorted
`generated_cases` list beside `streams`. The recipe has no such keys, and declaring one is
`MANIFEST_INVALID`. A case therefore cannot leave its parent's split, and because split and rights
rules and every group, encounter and stream count read only `streams`, a case is never a new
encounter. A case holds its parent's rights by reference: `parent_stream_id` names them.

Each record also stores `source_sha256`, `transform`, `transform_revision`, `seed`, the resolved
`window`, `parameters` and `label_transform`. `src/ss_track/corpus/cases/recipes.py` reads recipes and
builds these records. A build runs every transform without pixels, so a recipe its parent cannot
satisfy is refused before anything is staged, and `corpus build` needs no staged frames.

### Staging

`corpus stage` stages the streams, then each case from its parent's verified frames, under the same
lock, scratch and publish steps. `src/ss_track/corpus/cases/generated.py` writes a case, and a repeated
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

`src/ss_track/corpus/bundles/frame_store.py` writes each frame. When the bytes hash to the parent
frame they were read from, the name in scratch is a hard link to that file, and publishing the
scratch directory keeps the link. A filesystem that refuses the link, including a link across
devices, stores a copy of the same bytes. The sealed index and `bundle_sha256` are the same either
way. Free space is reserved for frames the case may change. A case that only drops or repeats frames
reserves none for pixels, because every stored frame is one of the parent's. If a filesystem shares
a device and then refuses the link, the copy can still run out of space: the command reports
`STORAGE_FAILED` and leaves that case unstaged.

On the development host, on tmpfs, four cases of 300 1080p frames took 37 s on top of staging their
parent, about 33 frames per second, with a 227 MB peak. A blur of radius 9 costs about 65 ms per
frame. A case that changes every frame still stores about 1.8 GB of new pixels. Frames it leaves
untouched add none. The [task record](../records/0039-corpus-provenance-bundle-frame-sharing.md)
holds the acceptance.

### Reproducibility

`src/ss_track/corpus/cases/transforms.py` and `region_transforms.py` hold the transforms. Each is a pure
function of frames, parameters and seed, in integer arithmetic only, and `seeded.py` derives every
random value with SHAKE-256 rather than a library generator whose stream may change.

`TRANSFORM_REVISIONS` versions each transform. A change to what one produces must raise its
revision, and `tests/corpus/cases/test_transform_golden.py` fails until it does. The installed
revision is stored in each case, and a stored case of another revision, or of a transform that no
longer exists, is `TRANSFORM_REVISION_MISMATCH` before anything is written. A case is never silently
regenerated as different evidence.

## Case preview

`corpus preview` writes one PNG of a single staged frame so an operator can check a declared
region by eye. The left panel is the parent frame. Each generated case of that stream follows, in
`case_id` order, with no gap. The command reads the bundles and writes only `--out`, which must
sit outside the corpus directory. It draws no label boxes and it does not change a bundle.

A case whose label transform is `region_status`, and whose window contains the frame, has that
rectangle's perimeter replaced with RGB (255, 0, 0). The outline uses the region's own pixels,
including a rectangle that touches the frame edge. Pixels inside and outside that perimeter stay
as the case stored them. The parent panel is not outlined. A case with no region on that frame,
such as blur or a frame outside the window, is shown unchanged.

A frame the case does not hold, which is how `dropped_frames` leaves a gap, is a panel of RGB
(255, 0, 255) in that case's place. The case is not dropped from the sheet. This is not
`FRAME_NOT_IN_BUNDLE`: that refusal is for a frame the parent itself does not hold. The result
names each panel `parent`, `case` or `removed`. A `case` panel includes `region` only when an
outline was drawn.

The encoder is `stored-deflate-rgb24-v1`: RGB rows, a none filter, and uncompressed deflate
blocks. The same frame therefore has the same bytes on every zlib build. The file holds the raw
rows plus one filter byte per row and a short header, because the pixels are not compressed.
`png_sha256` covers those bytes. A repeated command writes the same bytes. A refusal leaves an
existing `--out` untouched.

Passing a case id is `CASE_INVALID` and names the parent. An unknown stream, or a case that was
not staged, is `BUNDLE_NOT_STAGED`. A missing output directory, or an `--out` inside the corpus
directory, is `STORAGE_FAILED`.

```json
{"status": "written", "corpus_id": "pilot-v1", "files": ["sheet.png"],
 "preview": {"encoder": "stored-deflate-rgb24-v1", "stream_id": "enc01-cam0",
  "frame_index": 0, "width": 1280, "height": 720, "frame_width": 640,
  "frame_height": 720, "png_sha256": "...",
  "panels": [{"role": "parent", "stream_id": "enc01-cam0"}]}}
```

`src/ss_track/corpus/cases/preview.py` builds the sheet and
`src/ss_track/corpus/cases/preview_png.py` paints and encodes it.
`tests/corpus/cases/test_preview_png.py` checks a hand-listed perimeter.
`tests/corpus/cases/test_preview.py` and `test_preview_limits.py` check a staged stream. The
[task record](../records/0035-corpus-provenance-case-preview.md) holds the acceptance.

## Timestamp quality

`src/ss_track/corpus/sources/timestamps.py` grades stored PTS and never fills one in.

| Quality | Meaning |
| --- | --- |
| `measured` | Every frame stores a PTS, and the operator declared capture-clock evidence |
| `derived` | Every frame stores a PTS, with no evidence of where it came from |
| `missing` | At least one frame stores no PTS. Stored values are kept and absent ones stay `null` |

Duplicate or decreasing PTS is `PTS_NON_INCREASING`, naming the first offending frame. Capture-clock
evidence for a stream with missing PTS is `TIMESTAMP_CLAIM_UNSUPPORTED`. Under `nofillin`, AVI and
MPEG program streams import as `missing`, because they do not store a presentation time per frame.

## Reading sealed records

`src/ss_track/corpus/records/sealed.py` is the one way to read a sealed record, and
`tests/corpus/records/test_sealed_reads.py` scans the package so that no module reads around
it, calls `read_stated` outside the amendment, or compares a record's `schema_version` outside the
read path. Each read verifies the seal, then the kind, and interprets nothing before the seal has
held. Each format is one `RecordFormat` (`corpus/records/kinds.py`) beside its writer, holding its
kind and the one major this code writes. A record is never rewritten to fit. Three modules divide
the work: `sealed.py` decides how a record is read, `read_refusals.py` states each refusal it
raises, and `sealing.py` validates, seals and writes a record and hashes the files records pin. The
read path has three entries:

| Entry | Returns | Used by |
| --- | --- | --- |
| `read_sealed` | Evidence: a record of the current major as written, or of a `view` major as the current major, in memory | Every command that uses a record |
| `read_stated` | A record of the current major, or a `facts` or `view` major, as written, with its disposition | `ss-track import --amend-terms` and `--redecode` only |
| `read_comparable` | The seal, the major and the major's comparison projection, or none, for a record of any major | Lineage and shared-frame checks on predecessors |

A record of an earlier major takes the strictest disposition of each major it steps through, from the
contract's change log (see [contracts](contracts.md#runtime-enforcement)). `read_sealed` serves only
`view` and refuses `facts` and `retired`, and `read_stated` refuses only `retired`. A record of a
newer major, of a major no change log states, or whose version is not a true integer is refused by
both.

| Format | Writes | Older majors and their disposition | Remedy for an older record |
| --- | --- | --- | --- |
| Source manifest | 2 | 1: `facts` | `ss-track import --amend-terms` |
| Corpus manifest | 3 | 1, 2: `retired`; schema 3 without source terms: `facts` | Build a new corpus version that names it in `supersedes` |
| Frame bundle | 3 | 1, 2: `retired` | Build and stage a new corpus version |
| Frame set, staged hashes | 1 | None | No older major exists |

A refusal says what an operator needs to act on it:

```json
{"status": "refused", "code": "RECORD_SCHEMA_UNSUPPORTED",
 "message": "manifest.json (ss-track.source-manifest) has older schema 1 (facts); ...",
 "details": {"record": "manifest.json", "path": ".../import/<sha256>/manifest.json",
  "kind": "ss-track.source-manifest", "found_schema_version": 1, "accepted_schema_versions": [2],
  "age": "older", "disposition": "facts",
  "remedy": "Record its terms with ss-track import --amend-terms."}}
```

`age` is `older`, `newer` or `unstated`, and only an older record names a `disposition`. A newer
record is refused because this code cannot know what a newer field means, and its remedy is to
install the version that wrote it. A version that is not a true integer is `unstated`, as `True` and
`1.0` would otherwise compare equal to 1. `accepted_schema_versions` lists the current major and each
one a chain of views reaches. The remedy for an older record is the `migration` text of the
contract's change log, its one statement: a historic major's own entry in `retired_majors`, or else
the first major transition after it. A major with neither, which no ss-track version wrote, is told
to restore the record from a trusted copy.

**Views.** `src/ss_track/corpus/records/read_window.py` holds one `View` per `view` major: the kind,
the major it reads, a pure `upcast` to the next major, and `derived`, the JSON pointers of every
value it derives, with `*` for any list position. Views compose one major at a time, the read path
stamps the new major and keeps the original seal, so every pin, frame set and cohort key stays as it
was, and each step is logged with what it derived. A view naming a protected property (see
[contracts](contracts.md#evolution)), the seal, `kind` or `schema_version` is refused as
`CONTRACT_SET_INVALID` at read, and so is a `view` disposition with no function installed.
`check_view` applies a view to a real record and names every value it changed without declaring it,
or a change to the record it read. It walks every value, seconds on a million-frame bundle, so it
runs in tests and never on a read: `tests/corpus/records/test_historic_records.py` applies
every installed view to each kept record of its major and fails on any finding, or when no kept
record exists. A first-read check would prove no more, because a view is fixed code and that one
record is no better a witness than the kept one. No installed major is a view today, so the table is
empty: `tests/corpus/records/test_read_window.py` freezes a synthetic next corpus major with
the real `freeze` and proves both dispositions on records today's code writes.

**Stated shapes.** A corpus manifest sealed at schema 3 before source terms existed has no major of
its own. `stated_shape` tells it apart by one test, whether every stream's `rights` holds
`retain_until` and `derived_frames`, which reads streams and no frame. It is the
`corpus-3-without-source-terms` shape, with the `facts` disposition: `read_sealed` refuses it, naming
`shape` and the streams `lacking` terms, with the remedy to record terms and build a new version,
and `read_stated` returns it. A shape is read no more freely than its major, so a view never serves
it. This replaced the key check `corpus/sources/terms.py` held.

**Comparison projections.** `src/ss_track/corpus/records/projections.py` holds, per kind and major,
the facts a comparison reads from a record as written: a corpus version's `corpus_id`, seal, decode
policy hash, `supersedes` and each stream's `stream_id`, `source_sha256`, `group_id` and `split`,
plus `source_manifest_sha256`, which the amendment listing matches, and a bundle's pins and
`(frame_index, sha256)` pairs. Corpus majors 2 and 3 and bundle majors 2 and
3 have one, whatever their disposition. Corpus major 1 states no group or split, so it has none, and
nor does bundle major 1, which only a major-1 version staged. A record lacking a fact its projection
reads is `RECORD_TAMPERED`, as is any sealed record a reader walks and finds short of a fact:
`read_refusals.incomplete_record` is the one guard for that, since only a reseal by hand can make
one. Each projection is held to its era's kept record by
`tests/corpus/records/test_historic_records.py`. A predecessor with no projection is reported
as `not_compared` with reason `other_schema` and never fails its successor; [version
lineage](#version-lineage) and [shared frames](#shared-frames) show the results.

A record is validated once, in full, by `seal`, before anything is written: a writer defect is
`RECORD_INVALID` with nothing sealed, and its details name the contract version and violations. A
read walks no field beyond a stated shape's test, so opening a million-frame bundle record costs
what it did before contracts were enforced; `tests/corpus/records/test_read_cost.py` holds that
fixture. Validating such a record at staging costs about 32 seconds, measured on the kept bundle
grown to a million frames, which decoding and writing those frames far exceeds.

A plain import refuses an older record before decoding anything, so the remedy costs no decode. A
record that fails its seal or does not parse is `RECORD_TAMPERED`, including one holding a `NaN` or a
number too long to read, which no writer can produce.

`tests/corpus/kept_records/` keeps one real record of every major of every format, each written by
the code of the commit in its name and listed in its `README.md`, and a test fails when a new major
has none. The [read window record](../records/0021-data-contracts-record-read-window.md) holds the
accepted task, its decisions and its evidence.

## Refusal codes

`ss-track contracts` has [codes of its own](contracts.md#commands).

| Code | Raised when |
| --- | --- |
| `MANIFEST_INVALID` | A declaration is unreadable, breaks its contract, or breaks a reader rule above |
| `SOURCE_NOT_FOUND` | The declared source does not exist |
| `SOURCE_UNREADABLE` | The source is not a readable file, cannot be opened, or has no usable video stream |
| `SOURCE_EMPTY` | The source has zero length |
| `SOURCE_HASH_MISMATCH` | Bytes differ from the declared or imported hash, or the stored source is gone |
| `SOURCE_DAMAGED` | Decoding or a completeness check shows truncation or corruption |
| `SOURCE_NO_FRAMES` | The media opened but decoded to no frames |
| `SOURCE_FORMAT_CHANGED` | Resolution, pixel format or display rotation changes within the stream |
| `VIDEO_STREAM_UNSPECIFIED` | The declaration does not name a video stream this container holds. Details list every video stream |
| `PTS_NON_INCREASING` | Stored PTS repeats or goes backward |
| `TIMESTAMP_CLAIM_UNSUPPORTED` | Capture-clock evidence was declared without complete PTS |
| `SELECTION_OUT_OF_RANGE` | A selection runs past the end of its sequence |
| `SOURCE_NOT_IMPORTED` | A corpus names a source with no import record |
| `SOURCE_RECORD_CHANGED` | A source's record differs from the one its corpus pinned, at stage or verify |
| `SPLIT_LEAKAGE` | A group, encounter, stream or case name is declared in two splits, two groups share a source or a run of identical frames, or a source or group sits elsewhere than a declared predecessor placed it |
| `STREAM_OVERLAP` | Two streams use the same frames of one source, or two streams of one group share a run of identical frames |
| `RIGHTS_CONFLICT` | Scenario sharing/sensitivity conflicts or a generated case lacks derivation permission |
| `RETENTION_EXPIRED` | The evaluation day is after a source's inclusive retention deadline |
| `CASE_INVALID` | A generated case does not fit its parent, changes no frame of it, does not match its parent's frame shape, or is named where preview expects the parent stream |
| `TRANSFORM_REVISION_MISMATCH` | A stored case needs a transform revision this code does not provide |
| `RECORD_TAMPERED` | A sealed record is missing, malformed, of another kind or fails its seal, or a re-import finds changed stored bytes |
| `RECORD_INVALID` | A writer produced a record its contract refuses; nothing is sealed or written. This is a defect of ss-track, not of the input |
| `RECORD_SCHEMA_UNSUPPORTED` | [Any sealed record](#reading-sealed-records) is of a major or stated shape this code does not serve as evidence, including at a re-import or rebuild over it and a corpus without source terms, or an amendment or a [redecode](#redecoding-under-a-new-policy) finds a record it cannot write forward |
| `DECODE_POLICY_MISMATCH` | A source or pin uses a decode policy other than the installed one |
| `IMPORT_CONFLICT` | The same source was imported at the current major with another declaration or decoder, or an amendment or a redecode names bytes with no record or changes more than terms |
| `CORPUS_CONFLICT` | The `corpus_id` already exists with different content, or a superseded version differs from the seal its successor pinned, at build, stage or verify |
| `CORPUS_NOT_BUILT` | The named corpus version or a version of its declared chain does not exist, or the identifier cannot name one |
| `DECODE_DRIFT` | A staging decode disagrees with the import record of its source |
| `BUNDLE_NOT_STAGED` | A stream has no staged frame bundle |
| `BUNDLE_CONFLICT` | A bundle was staged from a different corpus version, for a different stream, or from other parent frames |
| `FRAME_SET_NOT_STAGED` | Every bundle is staged but no frame set exists, so staging has not finished |
| `FRAME_SET_MISMATCH` | Staged bundles differ from the frame set, or something undeclared sits among them |
| `HASHES_NOT_COMPARABLE` | Two staged-hash records state different corpora, decode policies, sources or bundles |
| `STAGED_HASHES_DIFFER` | Two hosts staged different bytes. The comparison is kept and names each source |
| `STAGING_IN_PROGRESS` | Another run is staging this corpus version |
| `FRAME_CORRUPTED` | A staged file differs from the sealed index, is gone, or is not in it |
| `FRAME_NOT_IN_BUNDLE` | A bundle does not hold a frame index, including a frame a case dropped |
| `STORAGE_FAILED` | The data root cannot be written, lacks the space for raw frames, or a preview PNG cannot be written outside the corpus directory |

## Integrity limits

These measurements set the checks above. The truncation sweep inspected every byte-length prefix of
each file; an accepted prefix had to match the complete file's PTS and pixels.

| Container | Truncation result | `completeness_checks` |
| --- | --- | --- |
| Matroska and WebM of known size | Every cut refused | `matroska_segment_size` |
| MP4 with a sample table, AVI | Every cut refused unless all frames survive intact | `frame_count` |
| Fragmented MP4, MPEG-TS, MPEG-PS, raw streams, live Matroska | A short file can be accepted | empty |

A Matroska file cut just after a cluster header ends cleanly: FFmpeg logs nothing and returns fewer
frames, so `src/ss_track/corpus/decoding/integrity.py` compares the file with the segment size in
its header. An MP4 edit list can mark stored samples as never presented. They count toward the
container total as `discarded_frames` and are not frames of the sequence.

A bundle's per-frame hashes prove that frames have not changed since staging. They cannot show that
a frame was right when staged, because that rests on the source hash and the limits above.

Two pixel comparisons bound the conversion. Staged frames matched system `ffmpeg` 8.0.1 exactly on 26
of 32 real-encoder files, including every lossless source. The other six are H.264 and HEVC with
left-sited chroma, where decoded YUV matched and only conversion differed. A measured chroma ramp
settles which is right: the pinned path lands within 0.02 pixels when the tag is true, and system
`ffmpeg` lands 0.48 pixels off because it treats `left` as `center`. Software that converts with that
binary therefore sees different pixels from a bundle on those sources.

Bundle hashes matched on all 32 files with FFmpeg's SIMD disabled, and the bit-exact flags are what
make that true. [Across hosts](#across-hosts) states the arm64 evidence. Bundles are not claimed to be
identical across decoders, on macOS, or for a decoder or pixel format outside the fixed corpus: there,
a comparison on the host in question answers.

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
repository. `tests/corpus/decoding/test_decode.py` covers the strict inspection,
`test_decode_policy.py` the policy and its hash, and `test_decode_damage.py` the truncation sweep
over small H.264 Matroska and MP4 clips and the damage default decoding hides and the policy
refuses. `tests/corpus/bundles/test_bundle_writer.py`, `test_bundle_writer_refusals.py`,
`test_staging.py`, `test_single_pass.py`, `test_frame_store.py`, `test_frames.py`,
`test_bundle_reader.py`, `test_frame_verification.py` and `test_pixels.py` cover staging, reading
and verifying bundles, and
`test_pixels.py` includes the
comparison with FFmpeg's SIMD disabled. `tests/corpus/bundles/test_frame_set.py` covers the frame
set across data roots, `test_frame_set_runs.py` an interrupted, failed or concurrent stage and the
staging lock, and `test_frame_set_refusals.py` each refusal by name.
`tests/corpus/hosts/test_host_hashes.py` covers one host's record, `test_hash_comparison.py` and
`test_hash_comparison_inputs.py` each comparison result and refused input from the record to the
exit status, and `test_fixed_corpus.py` stages the whole fixed corpus and pins each row's decoded
format. `tests/corpus/versions/test_grouping.py`, `test_grouping_manifest.py`,
`test_scenario_rights.py` and `test_stream_identity.py` cover membership, rights and each stream's
identity from build to `FrameRef`. `tests/corpus/versions/test_lineage.py` compares hand-built
versions, and `test_lineage_build.py`, `test_lineage_leakage.py` and `test_lineage_chain.py` cover
linked builds, leakage and broken chains from the declaration to the exit status.
`test_unlinked_versions.py` and `test_unlinked_scan.py` cover sources placed elsewhere by a version
no declaration links, and manifests the scan cannot read.
`tests/corpus/bundles/test_shared_runs.py` covers the run rule on hand-written indexes, and
`test_shared_runs_group.py` a run inside one group. `test_duplicate_frames.py`,
`test_duplicate_frames_allowed.py`, `test_duplicate_frames_chain.py`,
`test_duplicate_frames_unread.py` and `test_group_repeated_frames.py` cover remuxed media from
staging to the exit status, in one version, across a chain, inside one group and where a chain
cannot be read.
`tests/corpus/sources/test_source_terms.py` covers retention boundaries at every entrypoint,
unchanged evidence across evaluation dates, explicit permission, strict declarations and legacy
records. `tests/corpus/sources/test_verify_rights.py` changes source terms through the real
amendment and `test_verify_records.py` changes source records through the real importer, and both
cover verification from the command's exit status to what each refusal names.
`tests/corpus/declarations/test_declaration.py` and `test_declaration_values.py` cover the
declaration readers. `tests/corpus/sources/test_amend_terms.py`, `test_amend_refusals.py`,
`test_amend_records.py` and `test_amend_impact.py` cover the amendment from the command to the
kept records and the versions that pin a replaced record, including a subprocess killed at each
write and real schema 1 records from `tests/corpus/kept_records/`, each written by the code of
the commit in its name. `tests/corpus/sources/test_redecode.py` covers
`--redecode` and `--redecode --amend-terms` the same way: a simulated policy upgrade, a tampered
stored source, a repeat, a subprocess killed at each write, and both kept schema 1 records, one
through the sequential route and one that needs both flags together.
`tests/corpus/records/test_sealed.py` covers the read path itself, `test_sealing.py` the seal, the
write and hashed copies, and `test_sealed_reads.py` scans for reads around the read path.
`test_historic_records.py` reads every kept record through the read path and
`test_historic_commands.py` runs each through the commands
that can reach it, `test_duplicate_frames_major.py` covers a predecessor's bundles of another major,
real and unprojected, and `test_read_window.py` covers a synthetic next major read as a view and as
`facts`, a view deriving a rights field, a decode policy mismatch through a view and the stated
shape. `tests/corpus/cases/test_transforms.py`, `test_transform_recipes.py` and
`test_transform_golden.py` cover each transform on hand-checkable frames and pin its bytes, and
`test_recipes.py`, `test_generated_cases.py`, `test_case_membership.py`, `test_case_frames.py`,
`test_frame_sharing.py` and `test_case_refusals.py` cover recipes and cases from declaration to
staged frames.

```bash
make test
```
