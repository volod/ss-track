# Two-source pilot creation recipe

This directory is the media-free recipe of the two-source pilot. Every authorized host acquires the
pinned sources itself and creates the same source, corpus and frame-set identities from these
files; no host copies media, imported sources or staged frames from another. The owner's
[source authorization](../../records/0068-self-supervised-corpus-authorize-video-corpus-sources.md)
bounds the use: local internal processing, restricted sharing, no public redistribution, and a
50 GB transfer cap across all pilot acquisitions. Acquiring this recipe transfers about 9.6 GB.

| File | Content |
| --- | --- |
| `inventory.yaml` | `declaration/source-inventory` 1.0.0: the Zenodo record and Hugging Face commit, the 31 selected videos and their terms |
| `pool.yaml` | `declaration/corpus-pool` 1.1.0: rights, splits and the CSV name rules that join the drone metadata to its videos |
| `plan-diverse.yaml`, `plan-uniform.yaml` | The paired discovery plans: one pool, audit seed and budget |
| `protocol.md` | The review protocol, frozen before `discover blind` |

## Selection

WetlandBirds v4 ([Zenodo 15696105](https://zenodo.org/records/15696105), CC BY 4.0): 16 videos
from the upstream train and validation splits, one of each of the 13 species plus a second little
ringed plover, moorhen and squacco heron from distant clip numbers. Adjacent clip numbers of one
species often share a session, so they were avoided. The upstream test split is never selected.

Drone Detection Dataset
([`wayneballard/drone-detection-dataset`](https://huggingface.co/datasets/wayneballard/drone-detection-dataset)
at `509cdb0f45c77f61fe5f62e5a303411045148c8d`, MIT card): 15 RGB videos. Six show only birds at
long and mid range, two birds with insects, one insects only, one empty sky, one airplane and one
helicopter as confusers, two drones with birds and one drone at night. Thermal footage is not
selected. Each video's upstream license (`cc-1.0`, `mit` or `personal`) is in its inventory terms,
and the pool joins it from `metadata/videos_*.csv` by the declared name rules.

All 31 are `development`. This is a review pilot, not a held-out set.

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
.venv/bin/ss-track discover pool --declaration "$W/pool.yaml" --run-id pilot-pool-20261112
for recording in "$DATA_DIR"/self-supervised-corpus/pilot-pool-20261112/recordings/*.yaml; do
  .venv/bin/ss-track import --source "$recording"
done
.venv/bin/ss-track corpus build \
  --manifest "$DATA_DIR/self-supervised-corpus/pilot-pool-20261112/corpus.yaml"
.venv/bin/ss-track corpus stage --corpus pilot-two-source-20261112
.venv/bin/ss-track corpus verify --corpus pilot-two-source-20261112
.venv/bin/ss-track corpus hashes --corpus pilot-two-source-20261112 --run-id pilot-hashes-<host>
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
.venv/bin/ss-track discover verify --run-id pilot-diverse-20261112
.venv/bin/ss-track discover verify --run-id pilot-uniform-20261112
.venv/bin/ss-track discover links --corpus pilot-two-source-20261112 \
  --run-id pilot-links-20261112 --features pilot-diverse-20261112
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
| Pool `pilot-pool-20261112` | `30ea0050620996adebda2a5cd12dc09e4794abf950204d26ad97a830573c6a86` |
| Corpus manifest `pilot-two-source-20261112` | `fdc93071f60ad9036f0c236902c4b8ec0c6be000de82d2e430c573c9aa68d931` |
| Frame set | `27833c7df8a00c04eb21856fd667d08a35273c4a777d4ea1a651dd5a4315336d` |
| Run `pilot-uniform-20261112` | `07a71d1e6343d06edc1128341bd9f554e79fd9c3d75f81fc05af33837e93bb42` |
| Run `pilot-diverse-20261112` (`cuda`, batch 64) | `1384870b91d3904affc8882ab332caebb724da797bddb951a0392361218ef19b` |
| Links `pilot-links-20261112` | `bb346f68fa5cbaf0dfc5e130851166002b42611914a9f86b71f29a5f9628f85a` |

The [pilot record](../../records/0067-self-supervised-corpus-corpus-two-source-pilot.md) holds the
measured resources and the unresolved evidence.
