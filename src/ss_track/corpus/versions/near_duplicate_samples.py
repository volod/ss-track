"""Sampled luma grids for one stored source.

The near-duplicate report asks for a few frames of each window. This reads those frames
once per source and stops after the last sample.
"""

from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any

import av

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.decoding.declared_color import recorded_matrix
from ss_track.corpus.decoding.decode import inspect_media
from ss_track.corpus.decoding.decode_policy import current_decode_policy
from ss_track.corpus.decoding.streams import recorded_video_stream_index
from ss_track.corpus.sources.stored import load_verified_source
from ss_track.corpus.versions.fingerprint import Grid, luma_grid, sample_indexes


class _SamplesReady(Exception):
    """The sampled frames are hashed, so the rest of the file is not needed."""


def sampled_frames(
    source_sha256: str, spans: Sequence[tuple[int, int]], data_root: Path
) -> dict[int, Grid]:
    """Return the luma grid of every sample index inside `spans`, keyed by frame index."""
    source = load_verified_source(source_sha256, data_root)
    wanted = {index for start, end in spans for index in sample_indexes(start, end)}
    return _decode_samples(source.stored, source.sequence, wanted)


def _decode_samples(stored: Path, sequence: Mapping[str, Any], wanted: set[int]) -> dict[int, Grid]:
    if not wanted:
        return {}
    last = max(wanted)
    found: dict[int, Grid] = {}
    policy = current_decode_policy()
    converter = policy.converter(recorded_matrix(sequence))

    def on_frame(frame_index: int, frame: av.VideoFrame) -> None:
        if frame_index in wanted:
            found[frame_index] = luma_grid(converter.pixels(frame), frame.width, frame.height)
        if frame_index >= last:
            raise _SamplesReady

    with suppress(_SamplesReady):
        inspect_media(
            stored,
            policy,
            on_frame,
            video_stream_index=recorded_video_stream_index(sequence),
        )
    if wanted - found.keys():
        missing: list[JsonValue] = [int(index) for index in sorted(wanted - found.keys())]
        raise CorpusRefusal(
            RefusalCode.SOURCE_DAMAGED,
            "a sampled frame was not decoded",
            {"missing": missing},
        )
    return found
