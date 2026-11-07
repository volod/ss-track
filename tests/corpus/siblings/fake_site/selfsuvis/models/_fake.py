"""What both fake embedders share: a model with a device, torchvision-like transforms and rows."""

import hashlib
import os
import socket
import sys
import time
from pathlib import Path

import numpy as np

from selfsuvis.pipeline.core.config import DEFECTS, settings

MEAN = [0.48145466, 0.4578275, 0.40821073]
STD = [0.26862954, 0.26130258, 0.27577711]


class InterpolationMode:
    def __init__(self, value: str) -> None:
        self.value = value


class Resize:
    def __init__(self, size: int) -> None:
        self.size = size
        self.interpolation = InterpolationMode("bicubic")


class CenterCrop:
    def __init__(self, size: int) -> None:
        self.size = (size, size)


class Normalize:
    def __init__(self, mean: list[float], std: list[float]) -> None:
        self.mean, self.std = mean, std


class Compose:
    def __init__(self, transforms: list[object]) -> None:
        self.transforms = transforms


class _Parameter:
    def __init__(self, device: str) -> None:
        self.device = device
        self.dtype = str(DEFECTS.get("dtype", "torch.float32"))


class _Model:
    def __init__(self, device: str) -> None:
        self.parameter = _Parameter(device)

    def parameters(self) -> object:
        return iter([self.parameter])


def resolved_device() -> str:
    """The real resolve_device falls back to the CPU when the requested device is missing."""
    if settings.DEVICE == "cpu" or "no_cuda" in DEFECTS:
        return "cpu"
    return f"{settings.DEVICE}:0"


def read_weights(*paths: Path) -> bytes:
    if "download" in DEFECTS:
        socket.create_connection(("huggingface.co", 443), timeout=1)
    if "stdout" in DEFECTS:
        print("downloading weights 100%")
        os.write(1, b"\r[progress bar]\n")
    data = b""
    for path in paths:
        with open(path, "rb") as handle:
            data += handle.read()
    return data


class FakeEmbedder:
    def __init__(self, weights: bytes) -> None:
        self.model = _Model(resolved_device())
        self.preprocess = Compose([Resize(224), CenterCrop(224), "to_tensor", Normalize(MEAN, STD)])
        self._seed = hashlib.sha256(weights).digest()
        self._calls = 0

    def image_dim(self) -> int:
        return int(DEFECTS.get("dimensions", 8))

    def encode_images(self, images: list[object], batch_size: int = 16) -> np.ndarray:
        self._calls += 1
        if "stdout" in DEFECTS:
            print(f"batch {self._calls}")
        if "oom" in DEFECTS and self._calls > 1:
            self.model.parameter.device = "cpu"  # the real embedders move to the CPU on OOM
        if "crash" in DEFECTS and self._calls > 1:
            sys.stderr.write("killed\n")
            sys.stderr.flush()
            os._exit(3)
        if "hang" in DEFECTS:
            time.sleep(60)
        rows = np.stack([self._row(image.tobytes()) for image in images])  # type: ignore[attr-defined]
        if "short" in DEFECTS:
            rows = rows[:-1]
        if "unnormalized" in DEFECTS:
            rows = rows * 2
        return rows.astype(np.float32)

    def _row(self, pixels: bytes) -> np.ndarray:
        digest = hashlib.sha256(self._seed + pixels).digest()
        values = (
            np.frombuffer(digest, dtype=np.uint8)[: self.image_dim()].astype(np.float64) - 127.5
        )
        return values / np.linalg.norm(values)
