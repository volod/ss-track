"""The worker's interpreter and its whole process environment, which ss-track builds explicitly.

The operator names the pinned environment's interpreter; ss-track never guesses it. The worker gets
only the cache and device variables it needs, the sibling settings set to fixed values, caches
offline, and an empty directory as its data and checkpoint directory. A configured adapted DINO
checkpoint is refused before any worker starts, since nothing records what it was trained on.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.discovery.plan import ExtractorPlan

PYTHON_VARIABLE = "SST_PERCEPTION_PYTHON"
# Forwarded so the worker finds its caches and devices; nothing else of this process reaches it.
_FORWARDED = ("PATH", "HOME", "HF_HOME", "HF_HUB_CACHE", "TORCH_HOME", "XDG_CACHE_HOME")
_FORWARDED_DEVICES = ("CUDA_VISIBLE_DEVICES",)
_CHECKPOINT_VARIABLE = "DINO_CHECKPOINT"


def worker_python(environ: Mapping[str, str] | None = None) -> Path:
    """Return the pinned environment's interpreter, which the operator names, never a default."""
    found = (os.environ if environ is None else environ).get(PYTHON_VARIABLE)
    if not found:
        raise CorpusRefusal(
            RefusalCode.WORKER_FAILED,
            f"set {PYTHON_VARIABLE} to the Python of the pinned ss-perception environment",
            {"variable": PYTHON_VARIABLE},
        )
    return Path(found)


def require_no_checkpoint(environ: Mapping[str, str] | None = None) -> None:
    """Refuse a configured adapted checkpoint, which the worker would otherwise never see."""
    found = (os.environ if environ is None else environ).get(_CHECKPOINT_VARIABLE)
    if found:
        raise CorpusRefusal(
            RefusalCode.EXTRACTOR_UNPINNED,
            f"{_CHECKPOINT_VARIABLE} is set; adapted checkpoints carry no training-source manifest",
            {"variable": _CHECKPOINT_VARIABLE},
        )


def worker_environment(
    extractor: ExtractorPlan, neutral: Path, environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Build the worker's whole environment: caches offline, settings explicit, data dir empty."""
    source = os.environ if environ is None else environ
    forwarded = {key: source[key] for key in (*_FORWARDED, *_FORWARDED_DEVICES) if key in source}
    settings = {
        "APP_ENV": "dev",
        "DATA_DIR": str(neutral),
        "SUP_CHECKPOINT_DIR": str(neutral / "checkpoints"),
        _CHECKPOINT_VARIABLE: "",
        "DEVICE": extractor.device,
        "USE_FP16": "false",
        "OPENCLIP_MODEL": extractor.model,
        "OPENCLIP_PRETRAINED": extractor.pretrained or "",
    }
    quiet = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "TQDM_DISABLE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
    }
    return forwarded | settings | quiet
