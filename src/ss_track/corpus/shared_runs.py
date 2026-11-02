"""The rule that one recording stays in one group, however it was packaged.

Sources are compared by byte hash, so a remux of a recording is a new source with the same frames.
Decoded frames are what a module reads, so a run of them held by two groups is one recording in two
groups. Frame hashes can show only that frames are equal, not what they show, so a run has to rule
out what independent clips really share: black, a test signal, a screen that blinks. Everything here
reads records it is given and touches no disk.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import takewhile
from typing import Any

from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode

# Different frames in a row that two streams must share. At 25 frames per second this is a third of
# a second of changing picture, which a shared lead-in or test signal does not supply.
MIN_SHARED_FRAMES = 8

type IndexedFrame = tuple[int, str]
type _Window = tuple[str, ...]


@dataclass(frozen=True, slots=True, eq=False)
class StreamFrames:
    """One stream's place and frame index, with each frame held in place kept once."""

    corpus_id: str
    stream_id: str
    group_id: str
    split: str
    frames: tuple[IndexedFrame, ...]


def stream_frames(
    corpus_id: str, stream: Mapping[str, Any], frames: Iterable[IndexedFrame]
) -> StreamFrames:
    """Prepare one stream's index, in presentation order, for `find_shared_runs`.

    A held frame says nothing about where footage came from, and a clip can hold each frame for
    several positions, so a run counts changes rather than positions.
    """
    changes: list[IndexedFrame] = []
    for frame in frames:
        if not changes or changes[-1][1] != frame[1]:
            changes.append(frame)
    return StreamFrames(
        corpus_id, stream["stream_id"], stream["group_id"], stream["split"], tuple(changes)
    )


def _windows(stream: StreamFrames) -> Iterator[tuple[int, _Window]]:
    """Yield each stretch of different frames. A black lead-in or a blinking signal has none."""
    hashes = [sha256 for _, sha256 in stream.frames]
    for start in range(len(hashes) - MIN_SHARED_FRAMES + 1):
        window = tuple(hashes[start : start + MIN_SHARED_FRAMES])
        if len(set(window)) == MIN_SHARED_FRAMES:
            yield start, window


def _side(stream: StreamFrames, position: int) -> dict[str, JsonValue]:
    return {
        "corpus_id": stream.corpus_id,
        "stream_id": stream.stream_id,
        "group_id": stream.group_id,
        "split": stream.split,
        "first_shared_frame": stream.frames[position][0],
    }


def _shared_run(
    first: StreamFrames, first_at: int, second: StreamFrames, second_at: int
) -> dict[str, JsonValue]:
    """State one run, widened from where it was found to everything the two streams share there."""
    earlier, later = first.frames, second.frames
    while first_at and second_at and earlier[first_at - 1][1] == later[second_at - 1][1]:
        first_at, second_at = first_at - 1, second_at - 1
    pairs = zip(earlier[first_at:], later[second_at:], strict=False)
    frame_count = sum(1 for _ in takewhile(lambda pair: pair[0][1] == pair[1][1], pairs))
    return {
        "frame_sha256": earlier[first_at][1],
        "frame_count": frame_count,
        "streams": [_side(first, first_at), _side(second, second_at)],
    }


def find_shared_runs(
    current: Sequence[StreamFrames], earlier: Sequence[StreamFrames]
) -> list[JsonValue]:
    """Find the first run that each stream of a version shares with a stream of another group.

    Every stream of `current` is compared with the rest of `current` and with `earlier`. Streams of
    `earlier` are not compared with each other, because a version answers for itself and for what
    it adds to its chain, not for a conflict its predecessors already held.
    """
    holders: dict[_Window, dict[StreamFrames, int]] = defaultdict(dict)
    for stream in earlier:
        for start, window in _windows(stream):
            holders[window].setdefault(stream, start)
    found: dict[tuple[StreamFrames, StreamFrames], tuple[int, int]] = {}
    for stream in current:
        for start, window in _windows(stream):
            for other, other_start in holders[window].items():
                if other.group_id != stream.group_id:
                    found.setdefault((other, stream), (other_start, start))
            holders[window].setdefault(stream, start)
    return [_shared_run(a, a_at, b, b_at) for (a, b), (a_at, b_at) in found.items()]


def require_unshared_runs(
    corpus_id: str, current: Sequence[StreamFrames], earlier: Sequence[StreamFrames]
) -> None:
    """Refuse groups that hold one recording, because a new container is not new evidence."""
    runs = find_shared_runs(current, earlier)
    if runs:
        raise CorpusRefusal(
            RefusalCode.SPLIT_LEAKAGE,
            f"{len(runs)} pair(s) of streams in different groups share a run of identical frames; "
            "keep one recording in one group, in a new corpus version",
            {"corpus_id": corpus_id, "min_shared_frames": MIN_SHARED_FRAMES, "shared_runs": runs},
        )
