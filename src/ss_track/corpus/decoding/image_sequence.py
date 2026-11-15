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
    clock: deadline.Clock = deadline.decode_clock,
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
            current = inspect_media(path, policy, deliver)
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
        time_base=(
            f"{frame_rate.denominator}/{frame_rate.numerator}" if frame_rate is not None else None
        ),
        pts=tuple(range(len(paths))) if frame_rate is not None else (None,) * len(paths),
        completeness_checks=(),
    )


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


def inspect_stored_sequence(
    path: Path,
    policy: DecodePolicy,
    on_frame: FrameConsumer,
    clock: deadline.Clock,
    decode_limit_seconds: float,
) -> MediaInspection:
    """Read the pinned sequence inventory used by all downstream decode paths."""
    from ss_track.corpus.sources.image_sequence import image_name, read_index

    inventory = read_index(path)
    paths = [path / image_name(index) for index in range(len(inventory["hashes"]))]
    rate = inventory["frame_rate"]
    return inspect_image_sequence(
        paths,
        policy,
        on_frame,
        frame_rate=None if rate is None else Fraction(rate),
        clock=clock,
        decode_limit_seconds=decode_limit_seconds,
    )
