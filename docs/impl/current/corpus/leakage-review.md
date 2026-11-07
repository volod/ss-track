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

`declaration/link-decisions` 1.0.0:

```yaml
schema_version: 1
reviewer: site lead                 # who decided
decisions:
- sources: ["<64 hex>", "<64 hex>"] # two source identities, in either order
  decision: related                 # related or unrelated
  note: same flight, second battery # optional
```

A pair is decided once, in either order, and never with itself; either is `MANIFEST_INVALID`. A
decided pair across groups is a link even when no method flagged it, so a reviewer can state what
they know from capture notes. A decision whose sources this version does not both hold, or whose
group already holds both, is listed under `decisions_outside_links` as `not_in_corpus` or
`same_group`. `unrelated` keeps two groups apart whatever a score says.

## Record

`self-supervised-corpus/<run-id>/links.json` is `record/corpus-links` 1.0.0:

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
  near-duplicate report and, along its chain, by the shared-frame check. Applying decisions across
  the versions a frozen corpus supersedes belongs to
  [review and freeze](../../plan.md#corpus-review-and-freeze).
- The thresholds rest on one real recording and synthetic scenes. A related pair below them, such as
  two sessions of one site in other light, is not flagged, and the
  [scale pilot](../../plan.md#corpus-scale-pilot) measures them on reviewed real footage.
- A tile grid other than 4 by 2 uses the tiled threshold unmeasured; the scale pilot measures the
  grid it chooses.
- Background cosine is one matrix product, rounded to four decimals; a pair at a threshold could flip
  on another host's arithmetic, which the scale pilot's second-host check covers.
- The fingerprint compares every pair of windows in Python, so its cost grows with the square of the
  stream count; the scale pilot measures it at its stream count.
- An undecided link is written, not refused: refusing a version with unresolved links across splits
  is the freeze's rule.

## Interfaces

| Module | Does |
| --- | --- |
| `commands/discover.py` | `discover links` |
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
