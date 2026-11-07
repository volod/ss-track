"""A discovery plan over the two staged test streams, with the fake extractor and one hint file."""

from pathlib import Path
from typing import Any

import yaml

from ss_track.corpus.siblings.embedding import PYTHON_VARIABLE
from tests.corpus.siblings._fake_sibling import COMMIT, DIMENSIONS, Caches

RUN_ID = "discovery-1"
CORPUS_ID = "pilot-v1"
HINT_COMMIT = "703e3c943dbc960a16cbc859680172c5a7ba5255"


def write_hints(directory: Path, source_sha256: str, *times: float) -> Path:
    """Write an ss-video hint file whose matches name one source at the given times."""
    path = directory / "hints.yaml"
    document = {
        "schema_version": 1,
        "project": "ss-video",
        "commit": HINT_COMMIT,
        "ffmpeg_version": "8.0.1-3ubuntu2+esm5",
        "sample_rate": "5/1",
        "matches": [{"file_sha256": source_sha256, "t_sec": t_sec} for t_sec in times]
        + [{"file_sha256": "f" * 64, "t_sec": 0.2}],
    }
    path.write_text(yaml.safe_dump(document), encoding="ascii")
    return path


def plan_document(caches: Caches, **changes: Any) -> dict[str, Any]:
    """A complete plan, which a test may then change."""
    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "corpus_id": CORPUS_ID,
        "source_approval": {"owner": "project owner", "reference": "fixture-media"},
        "pool": {"window_frames": 8},
        "audit": {"seed": 7, "sample_size": 2},
        "embedding": {
            "package": {"name": "ss-perception", "commit": COMMIT},
            "frame_stride": 4,
            "extractors": [
                {
                    "kind": "openclip",
                    "extractor_id": "clip-b16",
                    "model": "ViT-B-16",
                    "pretrained": "openai",
                    "device": "cpu",
                    "batch_size": 4,
                    "dimensions": DIMENSIONS,
                    "weights": [caches.clip_weight()],
                }
            ],
        },
        "hints": [{"hint_source_id": "ss-video-1", "file": "hints.yaml"}],
    } | changes


def write_plan(directory: Path, document: dict[str, Any]) -> Path:
    path = directory / "plan.yaml"
    path.write_text(yaml.safe_dump(document), encoding="ascii")
    return path


def worker_environ(caches: Caches, python: Path) -> dict[str, str]:
    return caches.environ | {PYTHON_VARIABLE: str(python)}
