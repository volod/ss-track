"""The rule that one recording stays in one group, and one frame in one stream.

Sources are compared by byte hash, so a remux of a recording is a new source with the same frames.
Decoded frames are what a module reads. A run of them held by two groups is one recording in two
groups, and a run held by two streams of one group counts each frame twice. Frame hashes can show
only that frames are equal, not what they show, so a run has to rule out what independent clips
really share: black, a test signal, a screen that blinks. Everything here reads records it is given
and touches no disk.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import takewhile
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

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


@dataclass(frozen=True, slots=True)
class _Pair:
    """One reported run, and whether both streams sit in one group."""

    run: dict[str, JsonValue]
    same_group: bool


def _reported(stream: StreamFrames, other: StreamFrames, version: set[int]) -> bool:
    """Report a different group, and the same group when both streams are this version's.

    A stream meets its own earlier window when a recording loops. That is one showing, not two
    streams, so it is not a pair.
    """
    if other is stream:
        return False
    return other.group_id != stream.group_id or id(other) in version


def _pairs(current: Sequence[StreamFrames], earlier: Sequence[StreamFrames]) -> list[_Pair]:
    """Find each pair once, in the order the streams were given.

    Streams of `earlier` are not compared with each other. A version answers for itself and for
    what it adds to its chain, not for a conflict its predecessors already held.
    """
    version = {id(stream) for stream in current}
    holders: dict[_Window, dict[StreamFrames, int]] = defaultdict(dict)
    for stream in earlier:
        for start, window in _windows(stream):
            holders[window].setdefault(stream, start)
    found: dict[tuple[StreamFrames, StreamFrames], tuple[int, int]] = {}
    for stream in current:
        for start, window in _windows(stream):
            for other, other_start in holders[window].items():
                if _reported(stream, other, version):
                    found.setdefault((other, stream), (other_start, start))
            holders[window].setdefault(stream, start)
    return [
        _Pair(_shared_run(first, first_at, second, second_at), first.group_id == second.group_id)
        for (first, second), (first_at, second_at) in found.items()
    ]


def find_shared_runs(
    current: Sequence[StreamFrames], earlier: Sequence[StreamFrames]
) -> list[JsonValue]:
    """Find the first run each stream of a version shares with another stream.

    Every stream of `current` is compared with the rest of `current` and with `earlier`. A
    same-group pair is reported only inside `current`: one version that holds a recording twice
    counts each frame twice. A copy that replaces its original in that group of a linked version
    is not a pair, because no version counts the frame twice.
    """
    return [pair.run for pair in _pairs(current, earlier)]


def _refuse(corpus_id: str, code: RefusalCode, message: str, runs: Sequence[JsonValue]) -> None:
    raise CorpusRefusal(
        code,
        message,
        {
            "corpus_id": corpus_id,
            "min_shared_frames": MIN_SHARED_FRAMES,
            "shared_runs": list(runs),
        },
    )


def require_unshared_runs(
    corpus_id: str, current: Sequence[StreamFrames], earlier: Sequence[StreamFrames]
) -> None:
    """Refuse one recording held by two groups, or twice by one group of this version.

    A version that does both is `SPLIT_LEAKAGE`, and that refusal names only the pairs in
    different groups. The same-group pairs are named once those are gone, so one refusal states
    one problem.
    """
    pairs = _pairs(current, earlier)
    leaked = [pair.run for pair in pairs if not pair.same_group]
    if leaked:
        count = len(leaked)
        _refuse(
            corpus_id,
            RefusalCode.SPLIT_LEAKAGE,
            f"{count} pair(s) of streams in different groups share a run of identical frames; "
            "keep one recording in one group, in a new corpus version",
            leaked,
        )
    overlapped = [pair.run for pair in pairs if pair.same_group]
    if overlapped:
        count = len(overlapped)
        _refuse(
            corpus_id,
            RefusalCode.STREAM_OVERLAP,
            f"{count} pair(s) of streams in one group share a run of identical frames; "
            "a frame in two streams counts twice in anything aggregated by encounter",
            overlapped,
        )
