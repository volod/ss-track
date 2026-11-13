# Review and freeze

A reviewer decides the candidate windows one [discovery run](discovery-runs.md) offers, and a frozen
corpus version is made from those decisions through the existing build, stage and verify flows.
`ss-track discover queue` shows what a run offers and writes a review file to fill in,
`ss-track discover export` writes the corpus declaration a review makes, and `ss-track corpus
freeze` seals the built and staged version with its decision provenance once its terms, its
membership, its [link review](leakage-review.md) and its frames all hold. `ss-track discover blind`
presents the common audit sample without selection, score or source cues, and `ss-track discover
unblind` maps the reviewer's item decisions back to the review file freeze already reads. A frozen
version holds membership only: no observation a reviewer records is a label, and labels come only
from the annotation contract. The
[task record](../../records/0055-self-supervised-corpus-corpus-review-and-freeze.md) holds the
decisions and acceptance evidence.

## Workflow

```bash
ss-track discover queue --run-id discovery-1 --out review.yaml   # every offered window, undecided
# the reviewer inspects windows with `corpus preview` and decides them in review.yaml
ss-track discover export --review review.yaml --corpus-id frozen-v1 --out frozen-v1.yaml
ss-track corpus build --manifest frozen-v1.yaml
ss-track corpus stage --corpus frozen-v1
ss-track discover links --corpus frozen-v1 --run-id links-frozen-v1 --decisions decisions.yaml
ss-track corpus freeze --corpus frozen-v1 --review review.yaml --links links-frozen-v1
```

`--supersedes <corpus-id>` on the export makes the frozen version name a predecessor, so its build
applies [version lineage](../corpus.md#version-lineage) and its freeze applies the reviewer's related
decisions to that chain. Each command logs one JSON record:

```json
{"status": "frozen", "corpus_id": "frozen-v1", "manifest_sha256": "...",
 "manifest_path": ".../corpus/frozen-v1/freeze.json", "frame_set_sha256": "...",
 "review": {"offered": 6, "included": 3, "excluded": 1, "unreviewed": 2, "withheld": 3,
            "stream_count": 2, "frame_count": 24},
 "superseded": {"compared_versions": [], "not_compared": []}}
```

`discover queue` reports `listed` with `queue`: windows offered, per reason, withheld per stream,
and pool windows not offered. `discover export` reports `exported` with the declaration's path and
SHA-256 and the same `review` counts. A retry of export or freeze with the same inputs reports
`unchanged`; a template or export never replaces a file holding other bytes, which is
`CORPUS_CONFLICT`, and neither does freezing a version already frozen from other decisions.

## What review offers

Review is bounded by the run. It offers the windows selection ranked, every window the audit sample
drew and every sibling window. A window named more than once is offered once, so the cost is that
distinct count, not the selection budget plus the audit sample. An unselected window reaches a
reviewer only through the independent audit sample. A withheld window is not part of that cost. A
window of a stream in the `locked` split is never offered while no custodian policy allows it,
although the audit sample draws from locked groups' strata: the queue, the template and the freeze
record name each such stream with reason `locked_without_policy` and the windows it withheld. A
decision on a withheld or unoffered window is `MANIFEST_INVALID`, naming each under
`locked_without_policy` or `not_offered`.

The template lists every offered window as `unreviewed`, each after a comment stating its frames,
why it was offered, what selection and the audit decided, and its scores. Its `reviewer` is empty,
which the contract refuses, so a template cannot pass as a review until someone is named.

## Blinded audit

`discover queue` stays the review of everything a run offers, comments and all. `discover blind`
is the other presentation: the common audit sample of one or more runs that share a pool, frame
set and audit design. Selected and unselected sampled windows are shown together. A window the
sample did not draw, and every sibling window, stays out. A sampled window of a locked stream is
withheld. The packet states how many and `locked_without_policy`. The stream id stays in the
private mapping.

```bash
ss-track discover blind --audit-id audit-1 --run-id discovery-1 --out packet/
# fill packet/review.yaml; pictures are packet/items/<item-id>/<offset>.png
ss-track discover unblind --audit-id audit-1 --review packet/review.yaml --out reviews/
# reviews/<run-id>.yaml is a corpus review that export and freeze already read
```

Item ids are `item-000` onward, ordered by a SHA-256 of the frame set, the audit seed, the stream
and the candidate. The same runs always assign the same ids. The order is neither frame order nor
a selection rank. A picture file is named by its offset in the window, and its bytes are the staged
frame encoded as PNG. The private mapping stores the SHA-256 of those bytes in display order. A
picture can still show where the footage came from. The packet names no recording, filename, model,
score, method or reason a window was offered.

The template is `declaration/audit-review` 1.0.0. Its reviewer is empty and `reviewer_minutes` is
absent, so it is not a review until both are set. `independence` and `blinding` are `declared` or
`not_declared`. Either value is what was declared. Reading it does not check that the procedure was
followed. An observation is still not a label.

`unblind` requires every item of the mapping and no other item. It writes one corpus review per
named run, copying the declaration, the minutes and the audit id. A review submitted without its
`items/` directory is still read. A directory that is present and whose pictures differ from the
stored hashes is `RECORD_INVALID`.

The private mapping is `record/audit-blinding` 1.0.0 at
`$DATA_DIR/self-supervised-corpus/<audit-id>/blinding.json`. That directory is the discovery-run
namespace, so an audit id that already holds a discovery run, or a different mapping, is
`CORPUS_CONFLICT`. The packet is written apart from that directory. Writing it inside is
`STORAGE_FAILED`. Reading the mapping recomputes the sample and the picture hashes from the runs
and the staged frames. A sealed record that names other windows is `RECORD_INVALID`. A missing file
and a byte that no longer seals are `RECORD_TAMPERED`. The same mapping and the same packet again
report `unchanged`. A path that already holds other bytes is `CORPUS_CONFLICT` and is left as it
was. Runs that differ in pool, frame set, audit design or sampled windows are `MANIFEST_INVALID`
and write nothing.

`discover blind` reports `presented`. Its `blind` object counts windows presented, withheld, outside
the sample, runs, and presented windows at least one named run did not select. It also reports the
review file's SHA-256 and the mapping's path and seal. `discover unblind` reports `unblinded`, the
same counts, the declared independence, blinding and minutes, and one path per mapped review.
Neither success record names a stream, a score or an offer reason.

The [task record](../../records/0063-self-supervised-corpus-corpus-blinded-audit-review.md) holds
the decisions and acceptance evidence.

### Interactive audit review

`ss-track discover review-audit` walks a reviewer through a packet in the terminal and writes the
completed blinded review, so nobody edits 100 YAML entries by hand:

```bash
ss-track discover review-audit --packet packet/ --reviewer "site lead" --blinding declared
ss-track discover unblind --audit-id audit-1 --review packet/review-completed.yaml --out reviews/
```

It reads only the packet: `review.yaml` for the audit id and item order, and `items/`. It never
opens the private mapping, a run or a queue template, so it cannot show a stream, a score, a
selection or an offer reason. On arrival at an undecided item it loops the item's pictures in
`ffplay` at 4 frames per second (`--no-autoplay` turns that off). `v` plays them again, `d` plays
frame differences amplified eightfold so that a small moving object lights up, and `o` opens the
item folder in the desktop viewer for zooming. `t`, `a`, `f` and `u` include the window as
`target_present`, `target_absent`, `confuser` or `unknown`; `x` excludes it with an observation
and a reason, and `other` requires a note. Both are taken by key or name (`q`, `quality`, `no
value`) in either order; an invalid answer is asked again and a blank one cancels. `e` edits a
note, `c` clears a decision back to `unreviewed`, `n`, `p`, `g` (next unreviewed) and `j` move, `s`
summarizes and `q` saves and quits.

Every decision atomically replaces the review file, `<packet>/review-completed.yaml` unless
`--review` names another. It is always a complete `declaration/audit-review` 1.0.0 that lists
undecided items `unreviewed`, so a paused review can be unblinded too; it then reports them as
unreviewed exposure. The packet template and pictures are never changed, so `unblind` still
matches the picture hashes. Restarting with the same reviewer resumes at the first unreviewed
item; another reviewer or a review of another packet is `IMPORT_CONFLICT`, and a second session on
one review file is `DISCOVERY_IN_PROGRESS`. `reviewer_minutes` is measured: the time between two
answers counts, capped at five minutes so a break is not review work, and is rounded up to whole
minutes. A resumed session starts from the saved whole minutes, so each pause can add up to
one minute. `--independence` and
`--blinding` set the declarations, which otherwise keep the saved values or start
`not_declared`; the command does not check them. The command reports `recorded` with the review
file as `record_path`. The terminal interaction uses the controlling terminal. The
[interactive audit record](../../records/0076-adhoc-interactive-audit-review.md) holds the
decisions and acceptance evidence.

## Decisions

`declaration/corpus-review` 1.0.0, with optional provenance from 1.1.0 and an optional
[selection pass](#selection-pass) from 1.2.0:

```yaml
schema_version: 1
run_id: discovery-1
reviewer: site lead
decisions:
- {stream_id: one, candidate_id: pool-000, decision: include, observation: target_present}
- {stream_id: one, candidate_id: pool-002, decision: exclude, observation: unknown,
   reason: quality, note: blurred}
- {stream_id: two, candidate_id: pool-000, decision: unreviewed}
```

| Field | Values |
| --- | --- |
| `decision` | `include`: the window's frames join the frozen version. `exclude`: they stay out. `unreviewed`: no one decided; the same as leaving the window out of the file |
| `observation` | Required on include and exclude: `target_present`, `target_absent` (no target seen, not a verified absence), `confuser` (no target, but a moving object that could pass for one) or `unknown` |
| `reason` | Required on exclude: `no_value`, `quality`, `sensitive`, `rights`, `duplicate` or `other`, which needs a `note` |
| `independence`, `blinding` | Optional. `declared` or `not_declared`. Absent when the review does not state it. A stated value is a declaration, not a verification |
| `reviewer_minutes` | Optional minutes the reviewer recorded. Absent when effort was not recorded |
| `audit_id` | Optional id of the blinded audit the decisions were mapped from |
| `selection_pass` | Optional. Every selected window reviewed again, with the pass reviewer and optional minutes. See [selection pass](#selection-pass) |

A candidate is decided at most once. A review of another run, one that includes nothing, and one
that excludes a frame another decision includes are `MANIFEST_INVALID`.

## Selection pass

A shared blinded audit reviews its sample once for both runs of a comparison. Each run then pays
only for its selected windows outside that sample, so two runs that select equally can still cost
different work. In the two-source pilot, 100 selections each overlapped the 104-window audit by
7 and 11, which left 93 and 89 windows to review. A selection pass removes that dependence on the
audit draw. The reviewer looks at every window the run selected and offers, including the ones the
audit already showed, and records an observation for each. Each run's pass is then exactly its
selected count of exposures, and the paired comparison counts that work under the
[`selection_pass` protocol](discovery-runs.md#evaluating-selection).

```yaml
selection_pass:
  reviewer: second reviewer
  reviewer_minutes: 25          # optional; absent is unmeasured, not zero
  windows:
  - {stream_id: one, candidate_id: pool-003, observation: target_present}
  - {stream_id: two, candidate_id: pool-001, observation: unknown}
```

The protocol is fixed before review and has no seed or tuning: review every selected window of
each run, over one shared blinded audit. `discover queue` writes the block commented out at the end
of its template, listing each selected window with a blank observation. The block cannot pass
until its reviewer is named and every observation is set. In the blinded workflow, copy it into the
review `discover unblind` wrote for that run. The pass is not blinded, because its reviewer knows
the windows were selected.

A pass changes neither selection, the audit draw nor any audit weight. Its observations never enter
the population estimate. The audit observation of a window stays authoritative, and a pass that
disagrees with the run's review is listed, not resolved. Its findings are reported as the run's
review yield. That includes targets in selected windows the audit never sampled, which the
estimate cannot see. A pass that leaves a selected window out is incomplete, and the comparison
then treats the work as unmeasured. `unknown` is a reviewed window and counts as work.

A pass window must be a selected window the run offers, listed at most once. A window of a locked
stream is withheld and cannot be in a pass. Either mistake is `MANIFEST_INVALID` at export, freeze
and evaluation, with details `not_selected` and `locked_without_policy`. A pass therefore cannot be
replayed onto another run. A freeze record carries the pass with its windows ascending, so editing
it breaks the seal (`RECORD_TAMPERED`). A resealed record whose pass windows are out of order or
repeated is `RECORD_INVALID`.

Padding was the alternative considered and rejected. It adds deterministic unselected windows to
the smaller arm until the two workloads are equal. It pays for windows neither method chose, and
its findings belong to no method. The amount it needs follows the audit draw rather than the
methods, so a different audit seed changes it. Counting its findings would credit a method with
random review. Ignoring them would hide discoveries.

The [selection-pass record](../../records/0070-self-supervised-corpus-corpus-balanced-review-budget.md)
holds the decision and acceptance evidence.

### Interactive selection pass

`ss-track discover review-pass` conducts a run's pass in the terminal and writes the
`selection_pass` block into the review `discover unblind` wrote for that run, instead of the
commented block being copied by hand:

```bash
ss-track discover review-pass --run-id discovery-1 --review reviews/discovery-1.yaml \
  --reviewer "second reviewer"
```

It verifies the run and lists every selected window it offers, ascending, which is exactly what a
complete pass reviews; a locked window is never listed. Each window shows its stream, candidate and
frame range and its observation so far, never a score, a method or the audit observation of the
window. Its pictures are rendered from the staged frames into a temporary folder outside the data
root only while that window is shown, and removed on the next window, so a pass needs about one
window of disk (about 100 MB in the pilot) rather than a copy of the run. The controls are those of
the audit review: `v`, `d` and `o` look, `t`, `a`, `f` and `u` record `target_present`,
`target_absent`, `confuser` or `unknown`, `c` clears, and `n`, `p`, `g`, `j`, `s`, `h` and `q` move,
summarize and quit. `--no-autoplay` turns off playing each unreviewed window on arrival.

Every observation atomically rewrites the review: its decisions and provenance unchanged, and the
pass so far with its reviewer, measured `reviewer_minutes` and windows ascending. A review holding
part of a pass is valid and incomplete, which the comparison treats as unmeasured work; one with no
observation yet has no pass. Quitting without a change leaves the file's bytes as they were.
Restarting with the same pass reviewer resumes at the first unreviewed window, its minutes from the
saved whole minutes. Another pass reviewer is `IMPORT_CONFLICT`; a review of another run, or a pass
naming a window the run did not select and offer, is `MANIFEST_INVALID`; a second session on one
review is `DISCOVERY_IN_PROGRESS`. After the pass, `discover unblind` into the same directory is
`CORPUS_CONFLICT`, because the review now holds other bytes. The command reports `recorded` with
the review as `record_path`. The
[interactive pass record](../../records/0077-adhoc-interactive-selection-pass.md) holds the
decisions and acceptance evidence.

## Membership

Each frozen stream is one maximal run of included windows of one pool stream, overlapping or
adjacent, named `<pool-stream-id>.<start>-<end>`, with that half-open window of source frames as its
`selection`. A pool stream name that leaves no room for the window within 64 characters is
`MANIFEST_INVALID`. A frozen stream keeps its pool stream's group and split: grouping and splits are
the operator's judgment on the pool version, and review neither moves nor merges them. Each frozen
stream is its own encounter, because streams of one encounter are not declared synchronized, so two
cameras' windows cannot be paired. The declaration pins the pool version's decode policy and copies
its scenario rights, so build refuses another decoder. Excluded and unreviewed windows never become
members, and generated cases are never exported.

## Refusals

| Step | Refusal | When |
| --- | --- | --- |
| Export, freeze | `RETENTION_EXPIRED` | An included source's retention ended on the evaluation day |
| Export, freeze | `SOURCE_RECORD_CHANGED` | An included source's record changed after the run read it, such as withdrawn rights: the reviewer decided under the terms the run read |
| Export, queue, freeze | `FRAME_SET_MISMATCH`, `RECORD_TAMPERED`, `RECORD_INVALID` | The discovery run fails [`verify_discovery`](discovery-records.md#interfaces) |
| Freeze | `CORPUS_CONFLICT` | The version does not hold exactly the streams the review makes of its run, with the pool's decode policy and scenario rights and no generated case. Details list `missing`, `unexpected` and `changed` streams and differing `fields` |
| Freeze | `FRAME_SET_MISMATCH` | The link review read another manifest or frame set than this version's |
| Freeze | `LINKS_UNRESOLVED` | The link review leaves a link across splits undecided; details list each |
| Freeze | `SPLIT_LEAKAGE` | A recording sits in another split than a related recording a superseded version held |
| Freeze | `FRAME_CORRUPTED` and the other [verify](../corpus.md#verification) refusals | A frame, bundle or frame set does not hold |
| Export, freeze, evaluate | `MANIFEST_INVALID` | A selection pass names a window twice, an unselected or unoffered window (`not_selected`) or a withheld one (`locked_without_policy`) |
| Blind, unblind | `MANIFEST_INVALID` | The runs do not share a sample, the review names another audit, an item is missing, repeated or unexpected, or a mapped review fails the corpus-review contract |
| Blind, unblind | `CORPUS_CONFLICT` | The audit id already holds another run or mapping, or the output path holds other bytes |
| Blind | `STORAGE_FAILED` | The packet would be written inside the private mapping's directory |
| Unblind | `RECORD_TAMPERED` | No blinding record, or its bytes no longer seal |
| Unblind | `RECORD_INVALID` | The mapping does not match the runs and frames, or pictures beside the review differ |

Freezing reads the link review with `read_links`, so a forged review is `RECORD_INVALID`. A link
review covers one version, so a related decision naming a recording the version does not hold is
listed outside its links; freezing applies every related decision, inside or outside, to each
version the frozen one supersedes, read through its comparison projection, and names one whose
major keeps no projection under `not_compared`. An undecided link inside one split does not refuse
and is counted as `unresolved_same_split`.

## Record

`corpus/<corpus-id>/freeze.json` is `record/corpus-freeze` 1.2.0, sealed beside the manifest.
A review that states no provenance still freezes without those fields, so an older review keeps
its record shape:

| Field | Holds |
| --- | --- |
| `corpus_manifest_sha256`, `frame_set_sha256` | The frozen version and its staged frames |
| `discovery` | The run, its seal, and the pool version and frame set it read |
| `links` | The link review, its seal, its status and its undecided links inside one split |
| `review` | The reviewer, the SHA-256 of the review's canonical JSON, windows offered and decisions made. Independence, blinding, minutes, `audit_id` and the [selection pass](#selection-pass) are copied only when the review stated them; pass windows are ascending |
| `label_revision` | Always null: a frozen version holds no label |
| `members` | Each frozen stream with its pool stream, group, split, window and the included candidates, each with its offers, observation and note |
| `exclusions`, `unreviewed` | Each excluded candidate with its observation, reason and note; each offered candidate left undecided |
| `withheld` | Each locked stream whose windows review withheld, with the reason and count |
| `sources` | Each source with its pinned record and the rights and sensitivity it states |
| `superseded` | The predecessors the related decisions were applied to, and those not compared |

`read_freeze` checks the seal, the contract and the rules it states in words: members are the
manifest's streams, each window is the union of its candidates without a gap, a candidate appears
once among members, exclusions and unreviewed, and no exclusion shares a frame with a member. A
forged record is `RECORD_INVALID`, and a retry that meets one refuses too.

Replaying the review reproduces everything. The same review of the same run writes the same
declaration bytes, which build and stage turn into the same manifest and frame set, and freezing
writes the same record: the test replays a review on a second data root and compares the records.

## Limits

- An observation is recorded, not adjudicated. Labels, label review and disagreement belong to the
  [annotation tasks](../../plan.md#annotation-contract); the
  [corpus selection evaluation](../../plan.md#corpus-selection-evaluation) scores observations of
  audit-sampled windows.
- Each frozen stream is its own encounter, so windows of two cameras showing one event count as two
  encounters of one group. The group, which is the unit of independence and the split, is unchanged.
- Review offers no locked window until a [custodian policy](../../plan.md#define-locked-test-policy-optional)
  exists, so no frozen version holds locked material yet.
- Freezing needs the discovery run and its pool version's frames to verify, so a pool version's
  frames stay on disk until its frozen versions are frozen.
- Related decisions apply along the declared chain only; a version no chain links to is compared by
  the build's [near-duplicate report](../corpus.md#near-duplicates) alone.
- The queue template still shows frames, offers, selection and scores. The blinded packet does not,
  and neither does `review-audit`, but nothing stops a reviewer from opening the queue template.
  Its pictures may still show the source, and a declared independence or blinding is not a check
  that the reviewer was kept from the queue or the mapping.
- Reviewer minutes are recorded only when the review states them. Discovery does not record compute
  cost.
- Pass disagreements compare each pass with its own run's review. A window both runs selected
  outside the audit, which no review observed, is not compared across the two passes; the
  [evaluation task](../../plan.md#corpus-selection-evaluation) owns that report.
- A selection pass is not blinded, and nothing checks that its reviewer worked apart from the audit
  reviewer. A pass reviewer who also reviewed the audit sees every selected window the audit drew twice.

## Interfaces

| Module | Does |
| --- | --- |
| `commands/discover.py` | `discover queue`, `discover export`, `discover blind`, `discover review-audit`, `discover unblind`, `discover review-pass` |
| `commands/corpus.py` | `corpus freeze` |
| `corpus/review/queue.py` | `review_queue`: offered, withheld and unoffered windows |
| `corpus/review/decisions.py` | `read_review` |
| `corpus/review/selection_pass.py` | `SelectionPass`, `read_pass`, `expected_windows` and `require_pass_windows` |
| `corpus/review/membership.py` | `review_membership`, `corpus_document` |
| `corpus/review/template.py` | `queue_review`, the review template |
| `corpus/review/export.py` | `export_review`, `apply_review`, current terms |
| `corpus/review/superseded.py` | `require_related_together` across the chain |
| `corpus/review/freeze.py` | `freeze_corpus`: replay, link and term checks, verify, seal, publish |
| `corpus/review/freeze_record.py` | The record body and `read_freeze` |
| `corpus/review/result.py` | Queue, export and freeze results |
| `corpus/review/blind.py` | `present_audit`, `unblind_audit` |
| `corpus/review/blind_sample.py` | The common audit sample and its item ids |
| `corpus/review/blind_packet.py` | The cue-free template and the picture files |
| `corpus/review/blind_key.py` | The sealed private mapping |
| `corpus/review/blind_review.py` | `read_audit_review`, and the mapped corpus reviews |
| `corpus/review/audit_session.py` | `read_packet`, `load_draft`, `save_draft`: the resumable review from the packet alone |
| `corpus/review/audit_interactive.py` | `review_audit_interactively`, `conduct_audit`: the terminal loop and effort clock |
| `corpus/review/review_terminal.py` | `ReviewTerminal`, `move`, `first_open`: prompts, the capped effort clock and navigation both terminal reviews share |
| `corpus/review/pass_session.py` | `pass_target`, `load_pass`, `save_pass`, `render_window`: the resumable pass inside the run's review |
| `corpus/review/pass_interactive.py` | `review_pass_interactively`, `conduct_pass`: the terminal pass and its one-window picture folder |
| `corpus/review/audit_viewer.py` | `play_flipbook`, `reveal_folder`: the ffplay loop, frame differences and folder opener |

## Verification

```bash
.venv/bin/pytest tests/corpus/review
.venv/bin/ss-track contracts validate --file tests/schema/examples/record-corpus-freeze.json
make ci
```

`test_selection_pass.py` covers the commented template block, a blank pass, a pass carried through
freeze and evaluation without adding an observation, an unselected or locked window, a repeat, an
edited and a resealed freeze record, and a review with no pass that still validates against the
1.1.0 contracts. `test_membership.py` covers joined and separate windows, the declaration,
include and exclude
conflicts, withheld and unoffered decisions, an unnoted `other`, a repeat, another run and a name
too long. `test_queue_and_export.py` stages three clips in three splits and runs discovery: the
queue withholds the locked stream, the template needs a reviewer, export repeats byte for byte and
never replaces a file, and withdrawn rights and ended retention refuse. `test_freeze.py` freezes the
stock review and checks every record section, that no observation reaches the manifest, a retry and
a conflicting review, and a replay on a second data root. `test_freeze_refusals.py` covers a
hand-edited declaration, another version's link review, an undecided link across splits and its
decision, a related recording a superseded version held in another split, changed terms, ended
retention and a forged record. `test_blind.py` presents a packet with no source cue, matches item
ids across two runs of one audit sample, withholds the locked stream, restores an `unknown`
observation, and refuses a forged mapping, a mismatched sample, a repeated item and a review that
names a stream. `test_audit_interactive.py` decides, excludes with a required note, edits, clears
and resumes, caps idle time, refuses another reviewer or packet and a packet item without pictures,
reviews a presented packet that `unblind` then maps, runs the CLI and checks the ffplay commands.
`test_pass_interactive.py` records, resumes and clears a pass that export accepts with the review's
decisions unchanged, leaves an untouched review byte for byte, refuses another pass reviewer, a
stray window and another run's review, renders one window at a time and runs the CLI.
