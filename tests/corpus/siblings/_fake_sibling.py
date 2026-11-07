"""A throwaway environment holding the fake ss-perception, and caches of pinned fake weights.

The environment is a virtual environment whose site path holds `fake_site/` and this suite's numpy,
so the worker runs there as it runs in the sibling's pinned environment: by `python -I`, importing
neither ss-track nor anything outside that site path. Each test gets its own caches, whose weight
files the plan pins by revision, hash and size, and its own `defects.json`.
"""

import hashlib
import json
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy

from ss_track.corpus.discovery.plan import EmbeddingPlan, ExtractorPlan

FAKE_SITE = Path(__file__).with_name("fake_site")
COMMIT = "12cb0861af8f6ae6562d2cf5211547e284c5b40d"
SNAPSHOT = "977e3dd0ec55ab8da155f2fbeb6b5f54948b6e3d"
CLIP_REPO = "timm/fake-clip"
DIMENSIONS = 8
CLIP_BYTES = b"fake clip weights"
DINO_BYTES = b"fake dino weights"
HUBCONF = b"dependencies = []\n"


def create_environment(directory: Path, commit: str | None = COMMIT) -> Path:
    """Create the environment and return its interpreter."""
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(directory)], check=True)
    site = next((directory / "lib").glob("python3*/site-packages"))
    numpy_site = Path(numpy.__file__).parent.parent
    (site / "fake.pth").write_text(f"{FAKE_SITE}\n{numpy_site}\n", encoding="ascii")
    info = site / "ss_perception-0.2.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: ss-perception\nVersion: 0.2.1\n", encoding="ascii"
    )
    if commit is not None:
        vcs = {"url": "https://github.com/volod/ss-fusion.git", "vcs_info": {"commit_id": commit}}
        (info / "direct_url.json").write_text(json.dumps(vcs), encoding="ascii")
    return directory / "bin" / "python"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode() + b"\0")
            digest.update(_sha(path.read_bytes()).encode() + b"\n")
    return f"tree-sha256:{digest.hexdigest()}"


@dataclass(frozen=True, slots=True)
class Caches:
    """One test's model caches and the environment the worker is started from."""

    home: Path

    @property
    def environ(self) -> dict[str, str]:
        return {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home),
            "HF_HOME": str(self.home / "hf"),
            "TORCH_HOME": str(self.home / "torch"),
        }

    def defects(self, **defects: object) -> None:
        (self.home / "hf" / "defects.json").write_text(json.dumps(defects), encoding="ascii")

    def clip_weight(self) -> dict[str, Any]:
        return {
            "name": CLIP_REPO,
            "revision": SNAPSHOT,
            "sha256": _sha(CLIP_BYTES),
            "size_bytes": len(CLIP_BYTES),
        }

    def dino_weight(self) -> dict[str, Any]:
        hub = self.home / "torch" / "hub"
        return {
            "name": "fake_dinov2_main:dinov2_vitb14_reg4_pretrain.pth",
            "revision": _tree_digest(hub / "fake_dinov2_main"),
            "sha256": _sha(DINO_BYTES),
            "size_bytes": len(DINO_BYTES),
        }


def make_caches(home: Path) -> Caches:
    """Write a Hugging Face snapshot and a torch.hub tree, as the real caches lay them out."""
    repo = home / "hf" / "hub" / f"models--{CLIP_REPO.replace('/', '--')}"
    blob = repo / "blobs" / _sha(CLIP_BYTES)
    blob.parent.mkdir(parents=True)
    blob.write_bytes(CLIP_BYTES)
    snapshot = repo / "snapshots" / SNAPSHOT
    snapshot.mkdir(parents=True)
    (snapshot / "open_clip_model.safetensors").symlink_to(blob)
    (repo / "refs").mkdir()
    (repo / "refs" / "main").write_text(SNAPSHOT, encoding="ascii")
    hub = home / "torch" / "hub"
    (hub / "fake_dinov2_main").mkdir(parents=True)
    (hub / "fake_dinov2_main" / "hubconf.py").write_bytes(HUBCONF)
    (hub / "checkpoints").mkdir()
    (hub / "checkpoints" / "dinov2_vitb14_reg4_pretrain.pth").write_bytes(DINO_BYTES)
    return Caches(home)


def clip_extractor(caches: Caches, **changes: Any) -> ExtractorPlan:
    extractor = ExtractorPlan(
        "openclip", "clip-b16", "ViT-B-16", "openai", "cpu", 4, DIMENSIONS, (caches.clip_weight(),)
    )
    return replace(extractor, **changes)


def dino_extractor(caches: Caches, **changes: Any) -> ExtractorPlan:
    extractor = ExtractorPlan(
        "dino", "dino-b14", "dinov3_vitb14", None, "cpu", 3, DIMENSIONS, (caches.dino_weight(),)
    )
    return replace(extractor, **changes)


def embedding_plan(extractors: Iterable[ExtractorPlan], frame_stride: int = 1) -> EmbeddingPlan:
    return EmbeddingPlan("ss-perception", COMMIT, frame_stride, tuple(extractors))
