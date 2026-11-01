"""Conversion of one decoded frame to the single pixel layout every module receives.

PyAV's default conversion is unsafe for a hash: without bit-exact flags FFmpeg's SIMD and C paths
round differently, and a converted plane can carry row padding that is not image data.
"""

from dataclasses import dataclass
from functools import reduce
from operator import or_

import av
from av.video.reformatter import Interpolation, VideoReformatter

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode

OUTPUT_PIXEL_FORMAT = "rgb24"
OUTPUT_BYTES_PER_PIXEL = 3
OUTPUT_BITS_PER_COMPONENT = 8
CONVERSION_FLAGS = "BILINEAR|ACCURATE_RND|BITEXACT|FULL_CHR_H_INT|FULL_CHR_H_INP"
UNSPECIFIED_COLOR_MATRIX = 2
_FLAG_SEPARATOR = "|"
_MINIMUM_COLOR_COMPONENTS = 3


@dataclass(frozen=True, slots=True)
class ColorTags:
    """Every stored tag that steers conversion to RGB, as FFmpeg's enumeration values."""

    matrix: int
    range: int
    primaries: int
    transfer: int
    chroma_location: int


def color_tags(frame: av.VideoFrame) -> ColorTags:
    """Return what a frame declares about its color, which steers the conversion to RGB."""
    return ColorTags(
        matrix=int(frame.colorspace),
        range=int(frame.color_range),
        primaries=int(frame.color_primaries),
        transfer=int(frame.color_trc),
        chroma_location=int(frame.chroma_location),
    )


def bits_per_component(pixel_format: str) -> int:
    """Return the precision of a pixel format's deepest component."""
    return max(component.bits for component in av.VideoFormat(pixel_format).components)


def uses_color_matrix(pixel_format: str) -> bool:
    """Say whether reaching RGB needs a matrix. RGB, gray and palette sources need none.

    PyAV's component `is_chroma` means subsampled chroma, so it cannot identify 4:4:4 YUV.
    """
    description = av.VideoFormat(pixel_format)
    colors = [component for component in description.components if not component.is_alpha]
    return len(colors) >= _MINIMUM_COLOR_COMPONENTS and not (
        description.is_rgb or description.has_palette
    )


def frame_size_bytes(width: int, height: int) -> int:
    """Return the size of one tightly packed output frame."""
    return width * height * OUTPUT_BYTES_PER_PIXEL


class PixelConverter:
    """Turns decoded frames into tightly packed output pixels. Reuses one scaler context."""

    def __init__(self, flags: str, threads: int) -> None:
        names = flags.split(_FLAG_SEPARATOR)
        self._interpolation = reduce(or_, (Interpolation[name] for name in names))
        self._threads = threads
        self._reformatter = VideoReformatter()

    def pixels(self, frame: av.VideoFrame) -> bytes:
        """Return one frame's pixels, row after row, with no padding between rows."""
        converted = self._reformatter.reformat(
            frame,
            format=OUTPUT_PIXEL_FORMAT,
            interpolation=self._interpolation,
            threads=self._threads,
        )
        return _packed_rows(converted)


def _packed_rows(frame: av.VideoFrame) -> bytes:
    """Copy only image data. Bytes past each row are padding and may differ between decodes."""
    plane = frame.planes[0]
    stride = plane.line_size
    row_bytes = frame.width * OUTPUT_BYTES_PER_PIXEL
    if stride < row_bytes:
        raise CorpusRefusal(
            RefusalCode.SOURCE_UNREADABLE,
            "decoded frame has an unsupported row layout",
            {"line_size": stride, "row_bytes": row_bytes},
        )
    view = memoryview(plane)
    return b"".join(view[row * stride : row * stride + row_bytes] for row in range(frame.height))
