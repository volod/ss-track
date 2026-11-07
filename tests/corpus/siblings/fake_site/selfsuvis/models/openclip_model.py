"""Fake OpenCLIPEmbedder: weights from a Hugging Face snapshot, as open_clip resolves them."""

import os
from pathlib import Path

from selfsuvis.models._fake import FakeEmbedder, read_weights


class OpenCLIPEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        hub = Path(os.environ["HF_HOME"]) / "hub"
        refs = sorted(hub.glob("models--*"))
        commit = (refs[0] / "refs" / "main").read_text().strip()
        snapshot = refs[0] / "snapshots" / commit
        super().__init__(read_weights(*sorted(snapshot.iterdir())))
