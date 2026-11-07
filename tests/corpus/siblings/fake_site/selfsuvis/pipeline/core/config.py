"""Fake sibling settings: added variables as the real import adds them, and defects on request."""

import json
import os
from pathlib import Path

_DEFECTS_FILE = Path(os.environ.get("HF_HOME", ".")) / "defects.json"
DEFECTS: dict[str, object] = (
    json.loads(_DEFECTS_FILE.read_text()) if _DEFECTS_FILE.is_file() else {}
)

os.environ.setdefault("SAMPLE_FPS_MAX", "5")  # the real import adds 21 such defaults
if "env" in DEFECTS:
    os.environ["OPENCLIP_MODEL"] = "ViT-L-14"  # what a loaded .env would do to a setting
if "dotenv_checkpoint" in DEFECTS:
    os.environ["DINO_CHECKPOINT"] = "/missing/dino_ssl.pt"
if "stdout" in DEFECTS:
    print("config: loading layered .env files")


class _Settings:
    OPENCLIP_MODEL = os.environ.get("OPENCLIP_MODEL", "ViT-B-16")
    OPENCLIP_PRETRAINED = os.environ.get("OPENCLIP_PRETRAINED", "openai")
    DEVICE = os.environ.get("DEVICE", "auto")
    USE_FP16 = os.environ.get("USE_FP16", "true").lower() == "true"
    DINO_CHECKPOINT = os.environ.get("DINO_CHECKPOINT", "")
    SUP_CHECKPOINT_DIR = os.environ.get("SUP_CHECKPOINT_DIR", "./.data/checkpoints/supervised")


settings = _Settings()
