# Sibling integration for corpus formation

This page records what [ss-video](https://github.com/volod/ss-video) and
[ss-fusion](https://github.com/volod/ss-fusion) offer for
[video corpus formation](../../../design/spec.md#41a-self-supervised-video-corpus-formation), and the
integration plan the corpus tasks follow. No adapter code exists yet. ss-track does not depend on
either sibling, and its tests never import them. The evidence comes from inspecting the pinned trees
and running ss-perception on clips that ss-track staged. The
[task record](../../records/0050-self-supervised-corpus-corpus-sibling-integration-study.md) holds
the commands and results.

## Pinned revisions

| Project | Tag | Commit | Declared version | Licence |
| --- | --- | --- | --- | --- |
| ss-video | `v0.2.0` | `703e3c943dbc960a16cbc859680172c5a7ba5255` | `selfsuvis` 0.1.0 | MIT |
| ss-fusion | `v0.2.0` | `12cb0861af8f6ae6562d2cf5211547e284c5b40d` | every package 0.2.1 | none |
| ss-common | `v0.2.1` | `255837301437c84c253627499c2f8ae9c9953c03` | 0.2.1 | MIT |

Both `v0.2.0` tags point at the head of each default branch. ss-video pins ss-fusion `v0.2.0` and
both pin ss-common `v0.2.1`, so they use one tree. The 0.2.0 and 0.2.1 labels are not a code
mismatch: the ss-fusion `v0.2.0` tag holds packages that declare 0.2.1. Package metadata alone
therefore cannot identify the revision. An installer that records the commit (`uv` writes it to
`direct_url.json`) can.

## Interfaces

| Interface | Where | Use for ss-track |
| --- | --- | --- |
| `OpenCLIPEmbedder`, `DINOEmbedder` | ss-perception `selfsuvis.models` | Usable. `encode_images(list[PIL.Image])` returns L2-normalised float32 rows |
| `extract_frames(path, video_id)` | ss-perception `selfsuvis.pipeline.media.ffmpeg` | Not a frame identity. See [frame mapping](#frame-mapping) |
| `VideoIndexer.index_video` | ss-video `pipeline/workflows/indexer/` | Service-only. It writes to Qdrant and PostgreSQL |
| `POST /query/text`, `/query/image` | ss-video API | Hints only. At most 100 matches, without vectors, source hash or model name |
| SSL fine-tuning, `ssv` pipeline | ss-fusion `selfsuvis.pipeline.training`, `ssv_vdp` | Excluded. See [adapted models](#adapted-models) |

ss-video has no bulk export of frames, vectors or payloads. A full inventory would need direct reads
of its Qdrant collection and PostgreSQL tables. That is privileged service access, and running the
stack needs Redis, PostgreSQL, Qdrant, an API, a worker and optional GPU containers. The corpus tasks
therefore do not depend on a running ss-video.

## Frame mapping

ss-track names a frame by source hash, stream, frame index, PTS and pixel hash
([reading frames](../corpus.md#reading-frames)). The siblings do not keep that identity.

| ss-track field | Sibling counterpart | Mapping |
| --- | --- | --- |
| `source_sha256`, video stream 0 | ss-video `processed_files.file_hash` | Equal SHA-256 of the file bytes. Qdrant points carry a random `uuid4` `video_id`, so the join needs PostgreSQL |
| Video stream index above 0 | none | ffmpeg picks its default stream. Multi-stream sources cannot be mapped |
| `frame_index`, `pts` | `t_sec = k / SAMPLE_FPS_MAX` of JPEG `k` | Many-to-one. See below |
| Packed RGB pixels | JPEG at `-q:v 2` from `fps=N,format=yuv420p` | Mean absolute difference of about 2.2 of 255 per channel |
| Kept keyframe | `VideoIndexer` filters and drift tests | Depends on history. No inclusion probability, and no record of what was dropped |
| Qdrant point id | `stable_point_id(video_id, segment_id, ms, "frame")` | Changes on every re-index, since `video_id` is random |
| Model | `model_version_id`, default `base` | Names neither architecture, weights nor checkpoint |

`extract_frames` runs the system `ffmpeg` with an `fps` filter and labels JPEG `k` as `k / N`
seconds. It does not use the source PTS. On the study clips with ffmpeg 8.0.1, one rule reproduced
all 80 JPEGs: frame `f` falls in slot `floor((pts_f - pts_0) * N + 1/2)`, each slot shows the last
frame that falls in it, and an empty slot repeats the previous one. This rule has three consequences:

- `t_sec` counts from the first frame, so a source starting at PTS 1.5 s maps 1.5 s off.
- The label precedes the content by up to half a slot. At 30 frames per second and `N = 5`, JPEG 0
  shows frame 2, not frame 0. Nearest-time matching would name the wrong frame.
- A source slower than `N` repeats frames. A 4 frame per second clip gave 20 JPEGs from 16 frames.

A sibling time can therefore only name a window of source frames, and only under a recorded ffmpeg
version and `SAMPLE_FPS_MAX`. Candidate records must name ss-track frames.

## Model and data rights

| Item | Revision used | Licence | Note |
| --- | --- | --- | --- |
| ss-fusion code, ss-perception included | `v0.2.0` | none in the repository | No licence grants use, copying or redistribution. Running it needs the owner's grant |
| OpenCLIP code | `open_clip_torch` 4.2.1 | MIT-style | |
| CLIP ViT-B/16 `openai` weights | Hugging Face `timm/vit_base_patch16_clip_224.openai`, `main` resolved to `977e3dd0` | tagged Apache-2.0; OpenAI CLIP repository MIT | The OpenAI model card puts any deployed use out of scope. Downloaded from `main` with no pinned revision |
| DINO "dinov3" weights | `dinov2_vitb14_reg` via `torch.hub` `facebookresearch/dinov2` `main` | Apache-2.0 | ss-perception aliases every `dinov3_*` name to a DINOv2 `_reg` model |
| Video sources | none | - | Owned by [source authorization](../../plan.md#authorize-video-corpus-sources) |

No tool here may treat an ss-fusion install as licensed. The
[source authorization task](../../plan.md#authorize-video-corpus-sources) owns that grant along with
model approval.

## Reproducibility

Measured on the development host's CPU with torch 2.15.0+cpu, over 24 staged 320 by 240 frames:

| Check | OpenCLIP ViT-B/16 | DINOv2 ViT-B/14 reg |
| --- | --- | --- |
| Same frames again, one process | bitwise equal | bitwise equal |
| Second process, same weights | same SHA-256 of all rows | same SHA-256 of all rows |
| Batch of 16 against batch of 1 | differs by up to 2.4e-7 | bitwise equal |
| Sibling JPEG against staged frame, cosine | 0.974 minimum, 0.989 mean | 0.994 minimum, 0.997 mean |

Rows are reproducible only for a fixed batch size, device and weight file, and vectors computed from
sibling JPEGs are not interchangeable with vectors of staged frames. A GPU run was not measured.

Hazards in the inspected code that an adapter must neutralise:

- Importing `selfsuvis.pipeline.core.config` adds 21 variables to the process environment, among
  them `DATA_DIR=./.data`, which ss-track also reads. It also loads `.env`, `.data/.env` and
  `.data/.env.local` from a project root it takes from the working directory. Started in the
  ss-track checkout, that root is ss-track. Sibling code must therefore run in its own process,
  with an explicit environment and a neutral working directory.
- Model loading prints its download progress on standard output, which carries the one JSON record
  of an ss-track command.
- `DINOEmbedder` loads `DINO_CHECKPOINT`, or a path in `active_checkpoint.txt`, without recording
  it. A missing checkpoint file logs a warning and keeps the base weights.
- On CUDA out-of-memory both embedders move to the CPU for the rest of the run, so one run can mix
  fp16-autocast GPU vectors with fp32 CPU vectors.
- Both embedders resize the short side to 224 and centre-crop it. A 16:9 frame loses about 22% of
  its width on each side, and a small bird shrinks with the frame.
- `torch.hub` reads `facebookresearch/dinov2` at `main`, and `open_clip` reads Hugging Face at
  `main`, so the weights can change underneath one pin.

## Adapted models

ss-fusion SSL fine-tuning trains on every frame under its `DATA_DIR/frames/` and writes
`dino_ssl_*.pt` without a `model-artifact` manifest. Only the ONNX export writes one, and its
`training_data` names a kind and a reference, not sources. An adapted checkpoint therefore cannot
show that it never saw locked-test footage, and corpus selection uses frozen pretrained backbones.

## Integration plan

1. **Embedding worker.** ss-track runs ss-perception in a separate, pinned environment over frames
   it staged itself. The worker receives packed RGB frames named by `FrameRef` and an explicit
   environment. It returns one feature row per frame, keyed by bundle hash, frame index and frame
   hash, with the package commit, torch and open_clip versions, weight revisions and SHA-256,
   device, dtype, batch size and preprocessing. It refuses an unpinned weight, a set
   `DINO_CHECKPOINT` and a device change. The
   [video index adapter](../../plan.md#corpus-video-index-adapter) owns it.
2. **ss-video hints.** A query match or exported point becomes a candidate window only through the
   `file_hash` join and the slot rule above, under a recorded ffmpeg version and sampling rate. It
   never names a frame by itself. The same adapter task owns this optional reader.
3. **Selection features.** Whole-frame vectors miss edges and tiny targets, so
   [SSL selection](../../plan.md#corpus-ssl-selection) adds tiled or uncropped coverage and measures
   it on small-target fixtures.
4. **Rights.** Running the worker on real sources waits for the
   [source authorization](../../plan.md#authorize-video-corpus-sources) grant for ss-fusion code and
   the pinned weights.

## Resources

| Item | Measured |
| --- | --- |
| Isolated Python 3.12 environment | 1.2 GB: ss-perception, ss-common, torch and torchvision CPU wheels, open_clip |
| CLIP weights | 598,516,980 bytes, SHA-256 `4b8699299b1e8997753c64b052ba32031449d5d853f55a039148560ee02b820f` |
| DINOv2 weights | `dinov2_vitb14_reg4_pretrain.pth`, 346,393,545 bytes, SHA-256 `73182a088cf94833c94b1666d1c99e02fe87e2007bff57b564fb6206e25dba71` |
| CPU time per frame | 151 ms for CLIP and 205 ms for DINOv2 |
| Load with cached weights | 1.4 s per model |
| Peak resident memory | 1.6 GB |

At these rates one hour of video sampled at five frames per second costs about 1.8 CPU hours for
both models. `torch.hub` fetched `facebookresearch/dinov2` at `main`, which GitHub reported as
commit `7764ea0f` during the study; the downloaded archive does not record a commit.
