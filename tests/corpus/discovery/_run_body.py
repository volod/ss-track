"""The run body of the golden discovery run: one pinned extractor, two scores, one hint source.

The extractor states the CLIP revision, weight hash and library versions the sibling study measured,
so a fixture shows the provenance a real run must carry.
"""

from ss_track.core.refusal import JsonValue

RUN_ID = "discovery-1"
CORPUS_ID = "pilot-v1"
GROUP_ID = "group-one"
WINDOW_FRAMES = 8


def extractor() -> dict[str, JsonValue]:
    """The pinned CLIP extractor the sibling study measured."""
    return {
        "extractor_id": "clip-b16",
        "architecture": "ViT-B-16",
        "package": {
            "name": "ss-perception",
            "version": "0.2.1",
            "commit": "12cb0861af8f6ae6562d2cf5211547e284c5b40d",
        },
        "libraries": [
            {"name": "open-clip-torch", "version": "4.2.1"},
            {"name": "torch", "version": "2.15.0+cpu"},
        ],
        "weights": [
            {
                "name": "timm/vit_base_patch16_clip_224.openai",
                "revision": "977e3dd0",
                "sha256": "4b8699299b1e8997753c64b052ba32031449d5d853f55a039148560ee02b820f",
                "size_bytes": 598516980,
            }
        ],
        "device": "cpu",
        "dtype": "float32",
        "autocast": False,
        "batch_size": 16,
        "pixel_source": "staged_frame",
        "preprocessing": {
            "resize": "short_side",
            "crop": "center",
            "interpolation": "bicubic",
            "input_width": 224,
            "input_height": 224,
            "mean": [0.48145466, 0.4578275, 0.40821073],
            "std": [0.26862954, 0.26130258, 0.27577711],
        },
        "output": {"dimensions": 512, "normalized": True},
    }


def run_body(
    frame_set_sha256: str, pool_windows: int, budget: int, sample_size: int
) -> dict[str, JsonValue]:
    """A run body as a writer passes it: every field but stamp, inventories and seal."""
    return {
        "run_id": RUN_ID,
        "corpus_id": CORPUS_ID,
        "frame_set_sha256": frame_set_sha256,
        "processing": {"ss_track_version": "0.1.0", "revision": 1},
        "extractors": [extractor()],
        "scores": [
            {
                "score_id": "motion",
                "method": "frame-difference",
                "revision": 1,
                "extractor_ids": [],
                "preferred": "higher",
            },
            {
                "score_id": "novelty",
                "method": "cosine-novelty",
                "revision": 1,
                "extractor_ids": ["clip-b16"],
                "preferred": "higher",
            },
        ],
        "hint_sources": [
            {
                "hint_source_id": "ss-video-1",
                "project": "ss-video",
                "commit": "703e3c943dbc960a16cbc859680172c5a7ba5255",
                "ffmpeg_version": "8.0.1",
                "sample_rate": "5/1",
            }
        ],
        "pool": {"window_frames": WINDOW_FRAMES},
        "selection": {
            "method": "score-rank",
            "revision": 1,
            "seed": None,
            "budget": budget,
            "score_ids": ["motion", "novelty"],
        },
        "audit": {
            "design": "stratified_fixed_size",
            "revision": 1,
            "seed": 7,
            "strata": [
                {
                    "stratum_id": GROUP_ID,
                    "eligible_count": pool_windows,
                    "sample_size": sample_size,
                }
            ],
        },
    }
