"""Read an ss-video hint file and turn each match into windows of staged ss-track frames.

A match names a file by its hash and a sample by its time. It becomes a window only through the
`file_hash` join to a stream's source and the slot rule under the hint file's ffmpeg version and
rate, and only when that window lies whole inside the stream's bundle. Every other match is counted
under the reason it names no window, never guessed at.
"""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from ss_track.corpus.declarations.fields import Fields
from ss_track.corpus.siblings.slots import (
    NOT_ON_SLOT,
    SlotWindows,
    parse_rational,
    slot_at,
    slot_windows,
)
from ss_track.schema.validation.enforce import read_declaration

HINTS_CONTRACT = "declaration/video-hints"
HINTS_SCHEMA_VERSION = 1
NO_HASH_JOIN = "no_hash_join"
MULTI_STREAM_SOURCE = "multi_stream_source"
MISSING_TIMESTAMPS = "missing_timestamps"
OUTSIDE_BUNDLE = "outside_bundle"


@dataclass(frozen=True, slots=True)
class HintSource:
    """One hint file: the ss-video tree and sampling that produced it, and its matches."""

    hint_source_id: str
    project: str
    commit: str
    ffmpeg_version: str
    sample_rate: str
    matches: tuple[tuple[str, float], ...]

    @property
    def rate(self) -> Fraction:
        return parse_rational(self.sample_rate)

    def to_run(self, mapping: "HintMapping") -> dict[str, Any]:
        """Return the run's hint-source entry, with what became of the matches."""
        return {
            "hint_source_id": self.hint_source_id,
            "project": self.project,
            "commit": self.commit,
            "ffmpeg_version": self.ffmpeg_version,
            "sample_rate": self.sample_rate,
            "matches": mapping.matches(),
        }


def read_hint_source(path: Path, hint_source_id: str) -> HintSource:
    """Read one hint file under its contract."""
    fields = Fields(read_declaration(path, HINTS_CONTRACT, HINTS_SCHEMA_VERSION), path.name)
    matches = []
    for position, raw in enumerate(fields.items("matches")):
        match = Fields(raw, f"{path.name}.matches[{position}]")
        matches.append((match.text("file_sha256"), float(match.scalar("t_sec") or 0)))
    return HintSource(
        hint_source_id=hint_source_id,
        project=fields.text("project"),
        commit=fields.text("commit"),
        ffmpeg_version=fields.text("ffmpeg_version"),
        sample_rate=fields.text("sample_rate"),
        matches=tuple(matches),
    )


@dataclass(frozen=True, slots=True)
class StreamTiming:
    """What the slot rule needs of one stream: its source, bundle window and decoded PTS."""

    stream_id: str
    source_sha256: str
    start_frame: int
    end_frame: int
    sequence: Mapping[str, Any]

    def unmappable(self) -> str | None:
        """Say why no sibling time can name frames of this stream, if none can."""
        if self.sequence.get("video_stream_count", 1) > 1:
            return MULTI_STREAM_SOURCE  # ffmpeg samples its default stream, which may be another
        if self.sequence.get("time_base") is None or None in self.sequence["pts"]:
            return MISSING_TIMESTAMPS
        return None


def sibling_window(timing: StreamTiming, slots: SlotWindows, slot: int) -> tuple[int, int] | str:
    """Return the bundle window a slot names, or why it names none."""
    window = slots.window(slot)
    if isinstance(window, str):
        return window
    if window[0] < timing.start_frame or window[1] > timing.end_frame:
        return OUTSIDE_BUNDLE
    return window


class SlotCache:
    """Each source's slot windows at one rate, computed once however many matches name it."""

    def __init__(self) -> None:
        self._found: dict[tuple[str, Fraction], SlotWindows] = {}

    def of(self, timing: StreamTiming, rate: Fraction) -> SlotWindows:
        key = (timing.source_sha256, rate)
        if key not in self._found:
            time_base = parse_rational(str(timing.sequence["time_base"]))
            self._found[key] = slot_windows(timing.sequence["pts"], time_base, rate)
        return self._found[key]


@dataclass(frozen=True, slots=True, order=True)
class HintWindow:
    """One window a match named in one stream."""

    stream_id: str
    slot: int
    start_frame: int
    end_frame: int


@dataclass(slots=True)
class HintMapping:
    """What one hint file's matches became."""

    read: int = 0
    mapped: int = 0
    unmapped: Counter[str] = field(default_factory=Counter)
    windows: set[HintWindow] = field(default_factory=set)

    def matches(self) -> dict[str, Any]:
        """Return the counts a run and a command result state."""
        return {
            "read": self.read,
            "mapped": self.mapped,
            "unmapped": [
                {"reason": reason, "count": count}
                for reason, count in sorted(self.unmapped.items())
            ],
        }


def map_hints(source: HintSource, streams: Iterable[StreamTiming]) -> HintMapping:
    """Map every match of a hint file onto the streams whose source it names."""
    by_source: dict[str, list[StreamTiming]] = {}
    for timing in sorted(streams, key=lambda item: item.stream_id):
        by_source.setdefault(timing.source_sha256, []).append(timing)
    mapping = HintMapping()
    cache = SlotCache()
    for file_sha256, t_sec in source.matches:
        mapping.read += 1
        outcome = _map_match(by_source.get(file_sha256, []), t_sec, source.rate, cache)
        if isinstance(outcome, str):
            mapping.unmapped[outcome] += 1
            continue
        mapping.mapped += 1
        mapping.windows.update(outcome)
    return mapping


def _map_match(
    timings: Sequence[StreamTiming], t_sec: float, rate: Fraction, cache: SlotCache
) -> list[HintWindow] | str:
    """Return the windows one match names, or the first stream's reason when it names none."""
    if not timings:
        return NO_HASH_JOIN
    slot = slot_at(t_sec, rate)
    if slot is None:
        return NOT_ON_SLOT
    found: list[HintWindow] = []
    reasons: list[str] = []
    for timing in timings:
        reason = timing.unmappable()
        window = (
            reason if reason is not None else sibling_window(timing, cache.of(timing, rate), slot)
        )
        if isinstance(window, str):
            reasons.append(window)
        else:
            found.append(HintWindow(timing.stream_id, slot, *window))
    return found if found else reasons[0]
