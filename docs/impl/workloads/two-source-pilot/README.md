# Two-source pilot creation recipe

This directory is the media-free recipe of the two-source pilot. Every authorized host acquires the
pinned sources itself and creates the same source, corpus and frame-set identities from these
files; no host copies media, imported sources or staged frames from another. The owner's
[source authorization](../../current/corpus.md#source-authorization)
bounds the use under `approval-2026-11-13`: local internal processing, restricted sharing, no
public redistribution, and a 50 GB transfer cap across all pilot acquisitions. Acquiring this
recipe transfers about 9.8 GB.

| File | Content |
| --- | --- |
| `inventory.yaml` | `declaration/source-inventory` 1.0.0: the Zenodo record and Hugging Face commit, the first 31 selected videos and their terms |
| `inventory-additions.yaml` | Six further drone-dataset videos for the branch and skyline strata, acquired as their own run |
| `pool.yaml` | `declaration/corpus-pool` 1.1.0: rights, splits, the CSV name rules that join the drone metadata to its videos, and the related groups |
| `link-decisions.yaml` | `declaration/link-decisions`: the delegated link review of the ungrouped version, 8 related and 58 unrelated pairs |
| `plan-diverse.yaml`, `plan-uniform.yaml` | The paired discovery plans: one pool, audit seed and budget |
| `protocol.md` | The review protocol, frozen before `discover blind` |
| `reviews/pilot-*-grouped-20261113.yaml` | `declaration/corpus-review`: the unblinded audit decisions of each run with its selection pass, which `discover export` and `corpus freeze` replay |

## Selection

WetlandBirds v4 ([Zenodo 15696105](https://zenodo.org/records/15696105), CC BY 4.0): 16 videos
from the upstream train and validation splits, one of each of the 13 species plus a second little
ringed plover, moorhen and squacco heron from distant clip numbers. Adjacent clip numbers of one
species often share a session, so they were avoided. The upstream test split is never selected.

Drone Detection Dataset
([`wayneballard/drone-detection-dataset`](https://huggingface.co/datasets/wayneballard/drone-detection-dataset)
at `509cdb0f45c77f61fe5f62e5a303411045148c8d`, MIT card): 21 RGB videos. Fifteen are in
`inventory.yaml`. Six show only birds at
long and mid range, two birds with insects, one insects only, one empty sky, one airplane and one
helicopter as confusers, two drones with birds and one drone at night. Six more from
`inventory-additions.yaml` cover the approved branch and skyline strata, chosen by inspecting
frames: a forest edge with insects, a tree line over grass, bare branches under a small bird,
branches below a helicopter, and distant skylines with a small bird and an airplane. Thermal
footage is not selected. Each video's upstream license (`cc-1.0`, `mit` or `personal`) is in its
inventory terms, and the pool joins it from `metadata/videos_*.csv` by the declared name rules.

All 37 are `development`. This is a review pilot, not a held-out set.

## Grouping

The link review of the ungrouped version flagged 148 pairs. The owner delegated it to Claude,
which decided 66 from frames and burned-in camera overlays: 8 related and 58 unrelated. Related
pairs share a scene or a trail camera's deployment. The two Anti-UAV clips share a gimbal overlay
and date, although the dataset CSV labels one of them `cc-1.0`. The other 82 pairs come from one
source and share no scene, so their session cannot be established. The pool groups each such
source as an operator choice: the DroneDetectionThesis clips, the dataset author's recordings and
the handheld WetlandBirds clips are one group each. The grouped version has 13 groups, and its
link review is clear. The owner confirmed the decisions and the grouping without change, and a
second computer recreated the dataset identically.

## Create the dataset

From the project root after `make bootstrap`, with `ffmpeg` installed:

```bash
source scripts/shared/common.sh
sst_load_env
W=docs/impl/workloads/two-source-pilot
.venv/bin/ss-track discover inventory --file "$W/inventory.yaml" --out "$DATA_DIR/pilot-inventory.json"
.venv/bin/ss-track discover acquire --inventory "$W/inventory.yaml" --provider zenodo \
  --collection 15696105 \
  $(grep -o 'videos/[0-9][0-9][0-9]-[a-z_]*\.mp4' "$W/inventory.yaml" | sed 's/^/--video /') \
  --run-id pilot-wetland-acq-20261112 \
  --download-budget 9433000000 --extraction-budget 340000000 --authorized
.venv/bin/ss-track discover acquire --inventory "$W/inventory.yaml" --provider huggingface \
  --collection wayneballard/drone-detection-dataset \
  $(grep -o 'videos/[a-z_]*_footage/[a-z_/]*[0-9]*\.mp4' "$W/inventory.yaml" | sed 's/^/--video /') \
  --metadata metadata/videos_drone.csv --metadata metadata/videos_no_drone.csv \
  --metadata metadata/sources.txt --metadata metadata/scenarios.yaml \
  --run-id pilot-drone-acq-20261112 \
  --download-budget 165000000 --extraction-budget 165000000 --authorized
A="$W/inventory-additions.yaml"
.venv/bin/ss-track discover acquire --inventory "$A" --provider huggingface \
  --collection wayneballard/drone-detection-dataset \
  $(grep -o 'videos/[a-z_]*_footage/[a-z_/]*[0-9]*\.mp4' "$A" | sed 's/^/--video /') \
  --metadata metadata/videos_drone.csv --metadata metadata/videos_no_drone.csv \
  --metadata metadata/sources.txt --metadata metadata/scenarios.yaml \
  --run-id pilot-drone-extra-acq-20261113 \
  --download-budget 150000000 --extraction-budget 150000000 --authorized
.venv/bin/ss-track discover pool --declaration "$W/pool.yaml" --run-id pilot-pool-grouped-20261113
for recording in "$DATA_DIR"/self-supervised-corpus/pilot-pool-grouped-20261113/recordings/*.yaml; do
  .venv/bin/ss-track import --source "$recording"
done
.venv/bin/ss-track corpus build \
  --manifest "$DATA_DIR/self-supervised-corpus/pilot-pool-grouped-20261113/corpus.yaml"
.venv/bin/ss-track corpus stage --corpus pilot-two-source-grouped-20261113
.venv/bin/ss-track corpus verify --corpus pilot-two-source-grouped-20261113
.venv/bin/ss-track corpus hashes --corpus pilot-two-source-grouped-20261113 --run-id pilot-hashes-<host>
```

Compare the host's `staged-hashes.json` with the origin's using `corpus compare`, or let
`discover review-accept` compare it. The identities below must match exactly.

## Runs

The model-assisted run needs the pinned ss-perception environment in `SST_PERCEPTION_PYTHON` and the
pinned weights in the Hugging Face and torch caches. Set `device` and `batch_size` for the host in a
copy of `plan-diverse.yaml`; keep every other value. The uniform run embeds nothing.

The environment is Python 3.12 with `torch==2.7.1` and `torchvision==0.22.1` (the `cu128` index
for an NVIDIA GPU, CPU wheels otherwise), `open_clip_torch`, `timm`, ss-common `v0.2.1` and
`ss-perception @ git+https://github.com/volod/ss-fusion@75debcfed31a3c148d2f194a8ae2345e4b7508f1#subdirectory=packages/ss-perception`.
The DINO code tree must be `facebookresearch/dinov2` commit
`7764ea0f912e53c92e82eb78a2a1631e92725fc8`
([sibling integration](../../current/corpus/sibling-integration.md#reproducibility)):

```bash
export TORCH_HOME="$DATA_DIR/cache/torch-pilot"
mkdir -p "$TORCH_HOME/hub/checkpoints"
curl -L -o dinov2.zip https://github.com/facebookresearch/dinov2/archive/7764ea0f912e53c92e82eb78a2a1631e92725fc8.zip
unzip -q dinov2.zip -d dinov2-src
mv dinov2-src/dinov2-7764ea0f912e53c92e82eb78a2a1631e92725fc8 "$TORCH_HOME/hub/facebookresearch_dinov2_main"
touch "$TORCH_HOME/hub/trusted_list"
# place dinov2_vitb14_reg4_pretrain.pth (SHA-256 73182a08...) in "$TORCH_HOME/hub/checkpoints/"
```

```bash
export SST_PERCEPTION_PYTHON=/path/to/ss-perception-env/bin/python
.venv/bin/ss-track discover run --plan "$W/plan-diverse.yaml"
.venv/bin/ss-track discover run --plan "$W/plan-uniform.yaml"
.venv/bin/ss-track discover verify --run-id pilot-diverse-grouped-20261113
.venv/bin/ss-track discover verify --run-id pilot-uniform-grouped-20261113
.venv/bin/ss-track discover links --corpus pilot-two-source-grouped-20261113 \
  --run-id pilot-links-grouped-20261113 --features pilot-diverse-grouped-20261113 \
  --decisions "$W/link-decisions.yaml"
```

## Freeze the reviewed versions

The reviews in `reviews/` replay the owner's review on any host that recreated the dataset and both
runs. The model-assisted run must match the origin's identity, so use `cuda` and batch 64 or
expect a refusal:

```bash
for m in diverse uniform; do
  .venv/bin/ss-track discover export --review "$W/reviews/pilot-$m-grouped-20261113.yaml" \
    --corpus-id pilot-frozen-$m-20261113 --out "$DATA_DIR/pilot-frozen-$m-20261113.yaml"
  .venv/bin/ss-track corpus build --manifest "$DATA_DIR/pilot-frozen-$m-20261113.yaml"
  .venv/bin/ss-track corpus stage --corpus pilot-frozen-$m-20261113
  .venv/bin/ss-track discover links --corpus pilot-frozen-$m-20261113 \
    --run-id pilot-links-frozen-$m-20261113 --decisions "$W/link-decisions.yaml"
  .venv/bin/ss-track corpus freeze --corpus pilot-frozen-$m-20261113 \
    --review "$W/reviews/pilot-$m-grouped-20261113.yaml" --links pilot-links-frozen-$m-20261113
done
```

## Expected identities

From the origin host's sealed records. The source, pool, corpus and frame-set identities must match
on every host. The model-assisted run's identity also records its device and batch size, so it
matches only for the same host settings; the uniform run and the audit draw do not depend on them.

| Record | SHA-256 |
| --- | --- |
| WetlandBirds `videos.zip` (published MD5 `95eae83aceb2d12803f5f567c31060a9`) | `61da33ebad3c709ae1866308e609072728577cbbf961f05decf272e8b7d5b2c6` |
| Acquisition `pilot-wetland-acq-20261112` | `1fa3ef478673428437f03701a7ecd1e4d35a067ddc6fe461921143141cc2628e` |
| Acquisition `pilot-drone-acq-20261112` | `bc9946dcbcfbdf40e0e9f2d0f4062f3e94b57c715fe4968bcb0f1fb7be0ccf9e` |
| Acquisition `pilot-drone-extra-acq-20261113` | `571be24eaf916c2f19c8e7d5ce1673567f4e97a273afb335e1e77e85e392dce0` |
| Pool `pilot-pool-grouped-20261113` | `6f60d81c6767b3c3ea0a7a7b6268b66bc6d74c68c85dfc879f3c93bf084a6083` |
| Corpus manifest `pilot-two-source-grouped-20261113` | `47b8aa20c55377daaa79388e2dee403ad0112421056d80c72666a9cf2f02a70c` |
| Frame set | `2d7c30b9b518beb749d1628d2d965b21f2f37d6752a13a1711889ef3bb678d7c` |
| Run `pilot-uniform-grouped-20261113` | `eee2d02c464795e5528a214fc6d633f217aad643aca978fc1e22978a24e5f459` |
| Run `pilot-diverse-grouped-20261113` (`cuda`, batch 64) | `e5d59b73d9f73a65ebfb3d95ad943257d72fbf78cf86cf9e63f3ab601d12c31e` |
| Links `pilot-links-grouped-20261113` | `748d524efe0d39338ebc6faeded0f99af1e39e11ac193c5bac69b1cc4f7976d2` |
| Frozen `pilot-frozen-diverse-20261113` (`freeze.json`) | `23c1661133058bfe986e245543d0d830b7a3cbf8eff0ac294fab0f2ea37be8a3` |
| Frozen `pilot-frozen-uniform-20261113` (`freeze.json`) | `bf9d9b38952abffc158b8be494e5bd93e55e698a1f434ab13fc7c204a8deccf6` |

The [pilot record](../../records/0067-self-supervised-corpus-corpus-two-source-pilot.md) holds the
measured resources and the unresolved evidence.
