# Leakage review

`ss-track discover links` writes one link review of a staged corpus version. A link joins two
recordings held by different encounter groups that a similarity method flagged or a reviewer
decided. The command first applies the checks that already refuse known leakage, then shows each
uncertain match to a reviewer and applies the reviewer's decisions. A pair a reviewer decided is
related refuses the version until one group holds both. Nothing merges a group: grouping stays the
operator's judgment, and a similarity is a question, not ground truth. The
[task record](../../records/0054-self-supervised-corpus-corpus-group-and-leakage-review.md) holds
the decisions and acceptance evidence.

## Commands

```bash
ss-track discover links --corpus pilot-v1 --run-id links-1
ss-track discover links --corpus pilot-v1 --run-id links-2 --features discovery-1 \
  --decisions decisions.yaml
```

### Interactive review

Run the review in a terminal with the run ID of a sealed link record and the reviewer's name:

```bash
ss-track discover review-links --run-id pilot-links-features-v2-20261109 --reviewer "Your name"
```

The command explains the controls on startup. Use `a` and `b` to play the recordings using
`ffplay`, `r` or `u` to decide related or unrelated, `n` and `p` to navigate, `j` to jump, `c` to
clear a decision, and `q` to quit. Notes are optional ASCII. The display includes source identities,
available origin information, local paths, and the similarity evidence. If `ffplay` is unavailable,
open the displayed path with a local player. Locked recordings are not displayed or played. Review
only what you can establish; leave uncertain links undecided. This is not a blinded selection audit.

Every change is atomically replaced, with the file and its directory synchronized. The checkpoint is
`$DATA_DIR/self-supervised-corpus/<run-id>/link-review/decisions.yaml`; restart with the same run ID
and reviewer to resume at the first undecided link. Only one review of a run can write at a time.
The initial empty checkpoint asserts no relationships. The reviewer identity must match a prior
checkpoint or existing decisions in the link record, which are preserved, including decisions outside
the flagged links. The command emits one JSON result; the terminal interaction uses the controlling
terminal. Use the checkpoint as `--decisions` in a new `discover links` run with the same corpus and
feature run. Related sources in separate groups must first be grouped in a new corpus version.

The [interactive review record](../../records/0071-self-supervised-corpus-corpus-interactive-link-review.md)
contains implementation and acceptance evidence.

### Review on another host

These commands prepare the current two-source pilot for review on a second computer. They transfer
the imported source records and media, the corpus manifest and the sealed link record. They do not
need the staged frames or the GPU models. Both computers need network access between them, `ssh` and
`rsync`; the reviewing computer also needs Git, Make, uv, Python 3.12 or newer, and `ffplay` for
in-command playback in a graphical session. The review computer needs enough free disk for the
selected files and the Python environment. Transfer the data only to a computer authorized for the
source terms.
The [portable review task](../../plan.md#corpus-portable-link-review) covers an automated, verified
handoff; the steps below are manual and the local checkpoint lock does not extend across computers.
The [handoff planning record](../../records/0072-adhoc-remote-link-review-plan.md) records the
verification of these instructions.

On the pilot computer, from the project root, choose a remote login and a new, empty directory on
the review computer. Use a directory path without spaces or single quotes for these commands. The
checkout copied below includes current uncommitted implementation and contract files, so it does
not depend on a commit having been created. If `DATA_DIR` or other private material is inside the
checkout under another name, add an exclusion for it before copying the checkout.

```bash
REVIEW_HOST="reviewer@example-host"
REVIEW_DIR="review/ss-track"
source scripts/shared/common.sh
sst_load_env

ssh "$REVIEW_HOST" "mkdir -p '$REVIEW_DIR/.data'"
rsync -a --exclude='/.git/' --exclude='/.venv/' --exclude='/.data/' \
  --exclude='/.env*' --exclude='/.agents/' --exclude='/.codex/' --exclude='/.aws/' \
  --exclude='/.pytest_cache/' --exclude='/.mypy_cache/' --exclude='/.ruff_cache/' \
  --exclude='**/__pycache__/' \
  ./ "$REVIEW_HOST:$REVIEW_DIR/"
(
  cd "$DATA_DIR"
  rsync -aR import/ corpus/pilot-two-source-v2-20261109/manifest.json \
    self-supervised-corpus/pilot-links-features-v2-20261109/links.json \
    "$REVIEW_HOST:$REVIEW_DIR/.data/"
)
```

If resuming an existing review, stop the review first. With a new empty destination, copy its
checkpoint as well:

```bash
(
  cd "$DATA_DIR"
  rsync -aR \
    self-supervised-corpus/pilot-links-features-v2-20261109/link-review/decisions.yaml \
    "$REVIEW_HOST:$REVIEW_DIR/.data/"
)
```

If the destination already has a checkpoint, inspect it first and do not overwrite it. Do not run
independent reviews against copies of the same checkpoint: the local lock does not coordinate
computers and one copy can overwrite another's decisions. On the second computer, run the following
from the transferred checkout:

```bash
cd ~/review/ss-track  # use REVIEW_DIR chosen above
export DATA_DIR="$PWD/.data"
make bootstrap
.venv/bin/ss-track discover review-links \
  --run-id pilot-links-features-v2-20261109 --reviewer "Your name"
```

Use the same reviewer name to resume. A source or seal refusal indicates that the copied files are
missing, changed, or no longer meet their recorded terms; repair the transfer or investigate the
terms before reviewing. The command verifies the source bytes when displaying or playing them.
For this pilot the reviewer starts with 136 flagged pairs. Leave uncertain pairs undecided.

When finished or pausing, stop the command. On the pilot computer, retrieve the checkpoint to a
separate directory so it cannot overwrite a local review:

```bash
source scripts/shared/common.sh
sst_load_env
mkdir -p "$DATA_DIR/self-supervised-corpus/pilot-links-features-v2-20261109/returned"
REVIEW_RUN_PATH="$REVIEW_DIR/.data/self-supervised-corpus/pilot-links-features-v2-20261109"
rsync -a \
  "$REVIEW_HOST:$REVIEW_RUN_PATH/link-review/decisions.yaml" \
  "$DATA_DIR/self-supervised-corpus/pilot-links-features-v2-20261109/returned/decisions.yaml"
```

Keep `REVIEW_HOST` and `REVIEW_DIR` set as above, or set them again in the new shell. To apply the
returned file on the pilot computer, use a fresh run ID:

```bash
.venv/bin/ss-track discover links --corpus pilot-two-source-v2-20261109 \
  --run-id pilot-links-reviewed-1 --features pilot-diverse-v2-20261109 \
  --decisions "$DATA_DIR/self-supervised-corpus/pilot-links-features-v2-20261109/returned/decisions.yaml"
```

The link checker refuses related sources in different groups; group them in a new corpus version
before rerunning, or retain the refusal and unresolved evidence as the pilot's result. The complete
staged frames and discovery feature run remain necessary on the pilot computer for this check.

`--features` names a [discovery run](discovery-runs.md) over the same staged version, whose feature
rows the `background-cosine` method compares; without it only the fingerprint runs.
`--decisions` names the reviewer's decisions file. The command logs one JSON record:

```json
{"status": "written", "run_id": "links-2", "corpus_id": "pilot-v1", "manifest_sha256": "...",
 "manifest_path": ".../self-supervised-corpus/links-2/links.json",
 "links": {"status": "unresolved", "count": 3,
           "states": [{"status": "unrelated", "count": 1}, {"status": "unresolved", "count": 2}],
           "unresolved_cross_split": 1,
           "flagged": [{"method": "background-cosine", "extractor_id": "dino-b14", "count": 3},
                       {"method": "luma-grid-16", "count": 1}],
           "not_compared": 0, "decisions_outside_links": 0}}
```

The same inputs write the same bytes, so a retry reports `unchanged`. Another review under a used
run id is `CORPUS_CONFLICT`. A link review shares the run-id namespace and locks of discovery runs,
so a run id holding a discovery run is `CORPUS_CONFLICT` too, and a second command for one run id is
`DISCOVERY_IN_PROGRESS` at once.

## Known leakage refuses

In this order, before any link is sought:

| Check | Rule reused | Refusal |
| --- | --- | --- |
| One source, or one file, in two groups | `require_separate_sources`, the build's rule | `SPLIT_LEAKAGE` |
| A run of eight identical frames in two groups, such as a remux, over the version and its chain | `require_unshared_frames`, stage's rule ([shared frames](../corpus.md#shared-frames)) | `SPLIT_LEAKAGE` |
| Every stream staged | the same read | `BUNDLE_NOT_STAGED`, then `FRAME_SET_NOT_STAGED` |
| Two recordings a reviewer decided are `related`, in different groups, in one split or two | `require_no_related_links` | `SPLIT_LEAKAGE` |

The last refusal lists each such link with its evidence and decision. The remedy is a new corpus
version whose one group holds both recordings; the same decisions file then applies to it, because a
decision names recordings, not a version. A version that stage refused for shared frames is refused
here the same way, so its leakage is not hidden behind `FRAME_SET_NOT_STAGED`.

## Methods

| Method | What it compares | Flags at |
| --- | --- | --- |
| `luma-grid-16` | The build's [near-duplicate fingerprint](../corpus.md#near-duplicates) over this version's windows only | 0.90 |
| `background-cosine` revision 1 | Per plan extractor of the discovery run: each stream's background, the unit mean of its feature rows, per tile position; the pair's similarity is the mean cosine over the positions | Per architecture and crop, below |

Every pair of streams in different groups is compared; a pair inside one group is not a question.
Similarities are rounded to four decimals before the comparison, and the record keeps the strongest
pair of each method and extractor for a link.

| Architecture | Crop | Threshold |
| --- | --- | --- |
| `ViT-B-16` (CLIP) | `center` | 0.89 |
| `ViT-B-16` (CLIP) | `tiled` | 0.85 |
| `dinov3_vitb14` (DINOv2) | `center` | 0.60 |
| `dinov3_vitb14` (DINOv2) | `tiled` | 0.75 |

Backbones scale cosine differently: CLIP put every pair of the measured clips between 0.53 and 0.99,
DINOv2 between -0.01 and 0.96. An extractor whose architecture and crop have no measured threshold
compares nothing and is named under `not_compared` with reason `no_threshold`; a stream the run holds
no rows for is `no_feature_rows`, and a source the fingerprint cannot decode is `source_unreadable`.
An unknown is never reported as clear.

### Measured thresholds

On 2026-11-07, 13 clips were staged as one corpus, each its own group, and embedded at every eighth
frame by the pinned CLIP ViT-B/16 and DINOv2 ViT-B/14, each centre-cropped and in a 4 by 2 grid
(`$DATA_DIR/self-supervised-corpus/links-eval-20261107/`, scripts under `results/scripts/`). Four
windows of the one real recording, the hawk-and-drone flight, stand for related recordings of one
session; an x264 re-encode of one window is a copy; four synthetic skies of one generator are
lookalikes; testsrc2, a Mandelbrot zoom, SMPTE bars and a cellular automaton are unrelated scenes.

| Extractor | Related, 9 pairs | Copy | Lookalikes, 6 | Unrelated, 62: highest | Unrelated flagged |
| --- | --- | --- | --- | --- | --- |
| CLIP centre | 0.893 to 0.981 | 0.943 | 0.978 to 0.994 | 0.891 | 1 |
| CLIP tiles | 0.854 to 0.966 | 0.881 | 0.983 to 0.989 | 0.895 | 3 |
| DINOv2 centre | 0.605 to 0.935 | 0.945 | 0.903 to 0.957 | 0.788 | 1 |
| DINOv2 tiles | 0.758 to 0.901 | 0.885 | 0.882 to 0.929 | 0.796 | 1 |

Each threshold sits at or below the least related similarity, so every related pair and the copy is
flagged by every extractor, and so is every lookalike: those are what a reviewer must decide. The
unrelated pairs flagged are test patterns with each other. DINOv2 separates best: apart from SMPTE
bars against testsrc2, no unrelated pair exceeded 0.451, while CLIP's margin is 0.002. The
fingerprint flagged the copy (0.9993) and five of the six lookalike pairs, and no related window
pair, since different moments of a flight are not copies. The review took 12 s and 92 MB.

### Reviewer loop

The same run then took a decisions file marking the six lookalikes and three test-pattern pairs
`unrelated` (9 of 19 links resolved, 10 unresolved, 4 across splits, since one hawk window sat in the
locked split), and a second file that also marked every pair of hawk windows `related`, which was
refused as `SPLIT_LEAKAGE` naming the 10 links. Version `links-eval-v2` puts the five hawk windows
in one development group. With the second file its review is `clear`, with feature rows from a
discovery run over that version and without them: nine `unrelated` links, and the ten related
decisions listed as `same_group`.

## Decisions

`declaration/link-decisions` 1.1.0 (1.0.0 remains readable):

```yaml
schema_version: 1
reviewer: site lead                 # who decided
decisions:
- sources: ["<64 hex>", "<64 hex>"] # two source identities, in either order
  decision: related                 # related or unrelated
  note: same flight, second battery # optional
```

A decisions list may be empty, meaning no relationship was decided. A pair is decided once, in
either order, and never with itself; either is `MANIFEST_INVALID`. A
decided pair across groups is a link even when no method flagged it, so a reviewer can state what
they know from capture notes. A decision whose sources this version does not both hold, or whose
group already holds both, is listed under `decisions_outside_links` as `not_in_corpus` or
`same_group`. `unrelated` keeps two groups apart whatever a score says.

## Record

`self-supervised-corpus/<run-id>/links.json` is `record/corpus-links` 1.1.0 (1.0.0 remains readable):

| Field | Holds |
| --- | --- |
| `corpus_manifest_sha256`, `frame_set_sha256` | The version and staged frames reviewed |
| `shared_frames` | What the shared-frame check compared, as `corpus stage` reports it |
| `features` | The discovery run and its seal, when one was named |
| `methods` | The fingerprint, then one entry per plan extractor with its run extractors and threshold |
| `not_compared` | Streams a method could not compare, by method and reason |
| `review`, `decisions_outside_links` | The reviewer and decision count, and decisions that name no link; both absent without a decisions file |
| `links` | Each link: both sources with group, split and streams, `cross_split`, `evidence`, the `decision` when one was made, and `status` |
| `status` | `clear` when every link is decided, else `unresolved` |

A link's `status` is `unresolved` or `unrelated`; `related` never appears in a written record,
because it refuses. `clear` says only that every link the applied methods and decisions produced is
decided: a review without `--features` compared no backgrounds, and `methods` and `not_compared`
state what was compared. `read_links` checks the seal, the contract and every rule the contract
states in words: two groups per link, sources in order, `cross_split` against the splits, each
status against its decision, and the review's status against its links. A forged record is
`RECORD_INVALID`, and a retry that meets one refuses too.

## Limits

- A review covers one version. Another version on the data root is compared only by the build's
  near-duplicate report and, along its chain, by the shared-frame check. A decision naming a
  recording the version does not hold is kept under `decisions_outside_links`, and
  [freezing](review-and-freeze.md#refusals) applies its related decisions to every version the
  frozen one supersedes.
- The thresholds rest on one real recording and synthetic scenes. A related pair below them, such as
  two sessions of one site in other light, is not flagged, and the
  [scale pilot](../../plan.md#corpus-scale-pilot) measures them on reviewed real footage.
- A tile grid other than 4 by 2 uses the tiled threshold unmeasured; the scale pilot measures the
  grid it chooses.
- Background cosine is one matrix product, rounded to four decimals; a pair at a threshold could flip
  on another host's arithmetic, which the scale pilot's second-host check covers.
- The fingerprint compares every pair of windows in Python, so its cost grows with the square of the
  stream count; the scale pilot measures it at its stream count.
- An undecided link is written, not refused: [freezing](review-and-freeze.md#refusals) refuses a
  version whose link review leaves a link across splits undecided, as `LINKS_UNRESOLVED`.

## Interfaces

| Module | Does |
| --- | --- |
| `commands/discover.py` | `discover links` and `discover review-links` |
| `corpus/links/interactive.py` | Terminal review, navigation, playback, and validation |
| `corpus/links/interactive_state.py` | Atomic, synchronized decision checkpoints |
| `corpus/links/run.py` | `write_links`, `build_links`: checks, flags, decisions, seal and publish |
| `corpus/links/evidence.py` | `luma_evidence`, `background_evidence` and the threshold table |
| `corpus/links/review.py` | `review_links`, `require_no_related_links` |
| `corpus/links/decisions.py` | `read_decisions` |
| `corpus/links/records.py` | `read_links` and the record's rules |
| `corpus/links/result.py` | `LinksResult`: the counted summary |
| `corpus/versions/near_duplicates.py` | `version_near_duplicates`: the fingerprint over one version |

## Verification

```bash
.venv/bin/pytest tests/corpus/links
make ci
```

`test_decisions.py` covers the contract, pair order and repeats. `test_review.py` covers links across
splits and inside one group, unrelated and related decisions in one split or two, decisions outside
links and the strongest flag. `test_evidence.py` checks background cosine, tile averaging, the
threshold boundary and unmeasured backbones against hand-calculated rows. `test_links_run.py` stages
real clips: a lookalike pair across splits is written unresolved while an unrelated scene is not
linked, a remux in another group and a related decision refuse and write nothing, an unstaged version
and bad or held run ids refuse, a retry is unchanged, and a forged record is refused.
`test_links_features.py` reads a fake-sibling discovery run and refuses one of another version.
`test_interactive.py` and `test_interactive_state.py` cover terminal navigation, playback selection,
restart, interruption, checkpoint durability, and conflicts. The link-run tests check that empty and
decided checkpoints are accepted by the link checker.
