"""Strict decoding of an explicitly ordered sequence of lossless images."""

from collections.abc import Sequence
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import av

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.decoding import deadline
from ss_track.corpus.decoding.decode import FrameConsumer, MediaInspection, inspect_media
from ss_track.corpus.decoding.decode_policy import DecodePolicy

# Accept codecs rather than suffixes: a renamed lossy file must not pass.
LOSSLESS_CODECS = frozenset({"png"})
_SHAPE_FIELDS = (
    "original_width",
    "original_height",
    "decoded_width",
    "decoded_height",
    "source_pixel_format",
    "source_bits_per_component",
    "color",
    "display_rotation_degrees",
)


def inspect_image_sequence(
    paths: Sequence[Path],
    policy: DecodePolicy,
    on_frame: FrameConsumer,
    *,
    frame_rate: Fraction | None = None,
    clock: deadline.Clock | None = None,
    decode_limit_seconds: float = deadline.DECODE_LIMIT_SECONDS,
) -> MediaInspection:
    """Decode each image in the supplied order, retaining only declared timing.

    Callers must keep consumer output unpublished until this returns. A declared rate generates
    integer frame indices as PTS and its reciprocal as time base; images never prove capture time.
    """
    if not paths:
        raise CorpusRefusal(RefusalCode.SOURCE_NO_FRAMES, "image sequence is empty")
    if frame_rate is not None and frame_rate <= 0:
        raise ValueError("frame rate must be positive")
    clock = deadline.decode_clock if clock is None else clock
    bound = deadline.DecodeDeadline(decode_limit_seconds, clock)
    first: MediaInspection | None = None
    for index, path in enumerate(paths):
        bound.check(index)
        if not path.is_file():
            raise CorpusRefusal(
                RefusalCode.SOURCE_NOT_FOUND,
                f"sequence image not found: {path.name}",
                {"frame_index": index, "name": path.name},
            )

        def deliver(_: int, frame: av.VideoFrame, *, frame_index: int = index) -> None:
            frame.pts = frame_index if frame_rate is not None else None
            on_frame(frame_index, frame)

        try:
            current = inspect_media(
                path, policy, deliver, clock=clock, decode_limit_seconds=decode_limit_seconds
            )
        except CorpusRefusal as error:
            raise CorpusRefusal(
                error.code,
                f"{path.name}: {error}",
                error.details | {"frame_index": index, "name": path.name},
            ) from error
        bound.check(index + 1)
        _require_image(current, first, index, path)
        if first is None:
            first = current
    assert first is not None
    return replace(
        first,
        container="image-sequence",
        time_base=time_base(frame_rate),
        pts=tuple(range(len(paths))) if frame_rate is not None else (None,) * len(paths),
        completeness_checks=(),
    )


def time_base(frame_rate: Fraction | None) -> str | None:
    """Return the time base a declared rate gives frame-index timestamps: its reciprocal."""
    if frame_rate is None:
        return None
    return f"{frame_rate.denominator}/{frame_rate.numerator}"


def _require_image(
    current: MediaInspection, first: MediaInspection | None, index: int, path: Path
) -> None:
    if current.codec not in LOSSLESS_CODECS or len(current.pts) != 1:
        raise CorpusRefusal(
            RefusalCode.SOURCE_UNREADABLE,
            f"not one lossless image: {path.name}",
            {"frame_index": index, "name": path.name, "codec": current.codec},
        )
    if first is not None and any(
        getattr(first, field) != getattr(current, field) for field in _SHAPE_FIELDS
    ):
        raise CorpusRefusal(
            RefusalCode.SOURCE_FORMAT_CHANGED,
            f"sequence image format changed: {path.name}",
            {"frame_index": index, "name": path.name},
        )
