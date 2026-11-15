"""Decode a stored source the one way every command does: as import retained it.

A stored source is a directory exactly when import retained an image sequence, so this is the one
place that tells the two apart. A video file is decoded as one container; a sequence is decoded
image by image in its inventory's order, at the rate the inventory states.
"""

from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from ss_track.corpus.decoding import deadline
from ss_track.corpus.decoding.decode import (
    FrameConsumer,
    MediaInspection,
    ignore_frame,
    inspect_media,
)
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from ss_track.corpus.decoding.image_sequence import inspect_image_sequence
from ss_track.corpus.decoding.streams import recorded_video_stream_index
from ss_track.corpus.sources.image_sequence import (
    IMAGE_NAME_PATTERN,
    declared_rate,
    read_index,
    retained_images,
)


def inspect_stored(
    stored: Path,
    policy: DecodePolicy,
    on_frame: FrameConsumer = ignore_frame,
    *,
    video_stream_index: int | None = None,
    clock: deadline.Clock | None = None,
    decode_limit_seconds: float = deadline.DECODE_LIMIT_SECONDS,
) -> MediaInspection:
    """Decode the retained source strictly, with `inspect_media`'s contract for `on_frame`.

    `video_stream_index` selects a stream of a video file; a sequence has one stream and no index.
    """
    if stored.is_dir():
        inventory = read_index(stored)
        return inspect_image_sequence(
            retained_images(stored, inventory),
            policy,
            on_frame,
            frame_rate=declared_rate(inventory),
            clock=clock,
            decode_limit_seconds=decode_limit_seconds,
        )
    return inspect_media(
        stored,
        policy,
        on_frame,
        video_stream_index=video_stream_index,
        clock=clock,
        decode_limit_seconds=decode_limit_seconds,
    )


def player_input(stored: Path, sequence: Mapping[str, Any]) -> list[str]:
    """Return the FFmpeg player arguments that open this stored source at its recorded stream.

    A sequence plays through the image demuxer at its declared rate, or the player's default
    rate when it declared none; playback is for a reviewer's eyes and states no timing.
    """
    if stored.is_dir():
        time_base = sequence.get("time_base")
        rate = [] if time_base is None else ["-framerate", str(1 / Fraction(str(time_base)))]
        return ["-f", "image2", *rate, "-i", str(stored / IMAGE_NAME_PATTERN)]
    return ["-vst", f"v:{recorded_video_stream_index(sequence)}", "-i", str(stored)]


def describe_stored(stored: Path, sequence: Mapping[str, Any]) -> str:
    """Name a stored source for a reviewer: its path and what in it the corpus uses."""
    if stored.is_dir():
        return f"{stored} (image sequence of {sequence['frame_count']} images)"
    return f"{stored} (video stream {recorded_video_stream_index(sequence)})"
