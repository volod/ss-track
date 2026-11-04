"""The installed decode policy and a strict inspection under it, for the decode tests."""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import av
import pytest

from ss_track.core.refusal import CorpusRefusal
from ss_track.corpus.decoding.decode import (
    MediaInspection,
    inspect_media,
)
from ss_track.corpus.decoding.decode_policy import current_decode_policy

POLICY = current_decode_policy()


def inspect_clip(path: Path) -> MediaInspection:
    return inspect_media(path, POLICY)


def inspection_refusal(path: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        inspect_clip(path)
    return caught.value


class _Frame:
    """A real decoded frame, reported as the decoder flagged it."""

    def __init__(self, frame: av.VideoFrame, corrupt: bool) -> None:
        self._frame = frame
        self.is_corrupt = corrupt

    def __getattr__(self, name: str) -> Any:
        return getattr(self._frame, name)


class _Container:
    """What `av.open` returns: one video stream whose packets each decode to one frame."""

    def __init__(self, frames: list[_Frame], declared_frames: int) -> None:
        context = SimpleNamespace(
            options={}, thread_count=0, width=16, height=16, codec=SimpleNamespace(name="fake")
        )
        stream = SimpleNamespace(codec_context=context, frames=declared_frames, time_base=None)
        self.streams = SimpleNamespace(video=[stream])
        self.format = SimpleNamespace(name="fake")
        self._packets = [
            SimpleNamespace(is_corrupt=False, is_discard=False, decode=lambda f=f: [f])
            for f in frames
        ]

    def demux(self, _: object) -> Iterator[SimpleNamespace]:
        return iter(self._packets)

    def __enter__(self) -> "_Container":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def decoded_frame(index: int, colorspace: int = 1, corrupt: bool = False) -> Any:
    """Return a 16x16 frame at `index` with a stated color matrix, as a decoder would give it."""
    frame = av.VideoFrame(16, 16, "yuv420p")
    frame.pts = index
    frame.colorspace = colorspace
    return _Frame(frame, corrupt)


def fake_media(
    monkeypatch: pytest.MonkeyPatch, frames: list[Any], declared_frames: int = 0
) -> Path:
    """Make `av.open` return a container of these frames, for what no real file can produce."""
    container = _Container(frames, declared_frames)
    monkeypatch.setattr(av, "open", lambda *_, **__: container)
    return Path("fake.media")
