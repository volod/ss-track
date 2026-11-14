"""Each defect the worker guards against is still present in the pinned ss-perception release.

These tests run only when `SST_PERCEPTION_PYTHON` names the pinned environment, because the suite
never installs or imports a sibling. Each runs a probe in that environment, from an empty working
directory, and fails once the release no longer shows its defect, naming the guard to remove from
`src/ss_track/corpus/siblings/perception_worker.py`. The probes do not download weights; the
missing-checkpoint probe substitutes a tiny model.
"""

import json
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest

from ss_track.corpus.siblings.worker_env import PYTHON_VARIABLE

PINNED_COMMIT = "12cb0861af8f6ae6562d2cf5211547e284c5b40d"
PYTHON = os.environ.get(PYTHON_VARIABLE)

pytestmark = pytest.mark.skipif(not PYTHON, reason=f"{PYTHON_VARIABLE} names no pinned environment")


def _probe(tmp_path: Path, code: str, **environ: str) -> dict[str, object]:
    """Run code in the pinned environment; it prints one JSON object as its last line."""
    base = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", str(tmp_path))}
    done = subprocess.run(
        [str(PYTHON), "-I", "-c", textwrap.dedent(code)],
        cwd=tmp_path,
        env=base | {"HF_HUB_OFFLINE": "1", "DATA_DIR": str(tmp_path / "data")} | environ,
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    result: dict[str, object] = json.loads(done.stdout.strip().splitlines()[-1])
    return result


def _remove(guard: str) -> str:
    return f"the pinned release no longer shows this defect: remove the {guard} guard"


def test_the_probed_environment_is_the_pinned_release(tmp_path: Path) -> None:
    found = _probe(
        tmp_path,
        """
        import importlib.metadata, json
        raw = importlib.metadata.distribution("ss-perception").read_text("direct_url.json")
        print(json.dumps({"commit": json.loads(raw)["vcs_info"]["commit_id"]}))
        """,
    )

    assert found["commit"] == PINNED_COMMIT


def test_importing_settings_loads_a_dotenv_and_adds_variables(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SST_DEFECT_PROBE=from-dotenv\n")
    found: Any = _probe(
        tmp_path,
        """
        import json, os, ss_kit.paths
        def no_project_root(*args, **kwargs):
            raise FileNotFoundError("no marker")
        ss_kit.paths.discover_project_root = no_project_root
        before = set(os.environ)
        import selfsuvis.pipeline.core.config
        print(json.dumps({"added": sorted(set(os.environ) - before)}))
        """,
    )

    assert "SST_DEFECT_PROBE" in found["added"], _remove("environment file access")
    assert "OPENCLIP_MODEL" in found["added"], _remove("environment comparison")


def test_a_download_attempt_writes_to_standard_output(tmp_path: Path) -> None:
    code = """
        import json, socket, torch.hub
        def refused(*args, **kwargs):
            raise OSError("refused")
        socket.socket.connect = refused
        socket.create_connection = refused
        try:
            torch.hub.load_state_dict_from_url("https://dl.fbaipublicfiles.com/dinov2/probe.pth")
        except Exception:
            pass
        print(json.dumps({}))
        """
    done = subprocess.run(
        [str(PYTHON), "-I", "-c", textwrap.dedent(code)],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "TORCH_HOME": str(tmp_path / "torch")},
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )

    assert done.stdout.startswith("Downloading:"), _remove("descriptor 1 redirection")


def test_a_missing_checkpoint_keeps_the_base_weights_silently(tmp_path: Path) -> None:
    found = _probe(
        tmp_path,
        """
        import json, torch
        from selfsuvis.models import dino_model
        class BaseModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.weight = torch.nn.Parameter(torch.ones(1))
            def forward(self, images):
                return torch.ones((images.shape[0], 768), device=images.device) * self.weight
        dino_model.hub_load_dino = lambda *args, **kwargs: BaseModel()
        embedder = dino_model.DINOEmbedder(model_name="dinov3_vitb14")
        print(json.dumps({"loaded": embedder.image_dim()}))
        """,
        DINO_CHECKPOINT=str(tmp_path / "missing.pt"),
        DEVICE="cpu",
        USE_FP16="false",
    )

    assert found["loaded"] == 768, _remove("configured-checkpoint")


def test_out_of_memory_moves_the_model_to_the_cpu(tmp_path: Path) -> None:
    found = _probe(
        tmp_path,
        """
        import inspect, json
        from selfsuvis.models.openclip_model import OpenCLIPEmbedder
        from selfsuvis.models.dino_model import DINOEmbedder
        sources = [inspect.getsource(c.encode_images) for c in (OpenCLIPEmbedder, DINOEmbedder)]
        print(json.dumps({"moves": all("self.model.cpu()" in source for source in sources)}))
        """,
    )

    assert found["moves"], _remove("per-batch device")


def test_a_missing_device_falls_back_to_the_cpu(tmp_path: Path) -> None:
    found = _probe(
        tmp_path,
        """
        import json, torch
        torch.cuda.is_available = lambda: False
        from selfsuvis.pipeline.core.gpu_utils import resolve_device
        print(json.dumps({"resolved": resolve_device("cuda")}))
        """,
    )
    assert found["resolved"] == "cpu", _remove("load-time device")


def test_weights_resolve_from_a_branch(tmp_path: Path) -> None:
    found = _probe(
        tmp_path,
        """
        import json, open_clip
        from selfsuvis.models import dino_model
        clip = open_clip.get_pretrained_cfg("ViT-B-16", "openai")
        print(json.dumps({"clip_hub": clip.get("hf_hub", ""), "dino": dino_model.DINO_HUB_REPO}))
        """,
    )

    assert "@" not in str(found["clip_hub"]), _remove("weight revision")
    assert found["dino"] == "facebookresearch/dinov2", _remove("hub tree digest")
