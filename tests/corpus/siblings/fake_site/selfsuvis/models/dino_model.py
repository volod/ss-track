"""Fake DINOEmbedder: hub code from a torch.hub directory and a checkpoint beside it."""

import os
from pathlib import Path

from selfsuvis.models._fake import FakeEmbedder, read_weights
from selfsuvis.pipeline.core.config import DEFECTS


class DINOEmbedder(FakeEmbedder):
    def __init__(self, model_name: str = "dinov2_vitb14") -> None:
        # The real embedder aliases every dinov3 name to a DINOv2 model.
        self.model_name = str(DEFECTS.get("alias", model_name))
        hub = Path(os.environ["TORCH_HOME"]) / "hub"
        if "loose_weights" not in DEFECTS:  # a checkpoint loaded with no hub tree behind it
            hubconf = hub / "fake_dinov2_main" / "hubconf.py"
            with open(hubconf, "rb") as handle:
                handle.read()
        super().__init__(read_weights(*sorted((hub / "checkpoints").iterdir())))
