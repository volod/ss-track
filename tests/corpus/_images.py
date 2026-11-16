"""Lossless PNG fixtures encoded through the pinned decoder library."""

from pathlib import Path

import av
import numpy as np


def image(
    path: Path,
    value: int,
    width: int = 4,
    *,
    height: int = 4,
    codec: str = "png",
    pixel_format: str = "rgb24",
) -> Path:
    pixels = np.full((height, width, 3), value, dtype=np.uint8)
    with av.open(str(path), mode="w", format="image2") as output:
        stream = output.add_stream(codec)
        stream.width, stream.height, stream.pix_fmt = width, height, pixel_format
        frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
        for packet in stream.encode(frame):
            output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    return path
