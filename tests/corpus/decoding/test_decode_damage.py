"""Damage the default decoder hides is refused, at every truncation point and in every log."""

import hashlib
from pathlib import Path

import av
import av.logging
import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.decoding.decode import (
    inspect_media,
)
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from tests.corpus._media import (
    FRAME_COUNT,
    MP4_OPTIONS,
    X264_WITH_B_FRAMES,
    flip_bytes,
    write_clip,
)
from tests.corpus.decoding._decoding import (
    POLICY,
    decoded_frame,
    fake_media,
    inspect_clip,
    inspection_refusal,
)

_MATROSKA_CLUSTER_ID = bytes.fromhex("1F43B675")
_CLUSTER_HEADER_BYTES = 8


# Early enough for short streams, whose payload ends where a late fraction would reach the header.
_FLIP_FRACTIONS = tuple(step / 20 for step in range(1, 19))


def _pixels(path: Path, policy: DecodePolicy = POLICY) -> str:
    digest = hashlib.sha256()
    with av.open(path, options=dict(policy.format_options)) as container:
        for frame in container.decode(video=0):
            for plane in frame.planes:
                digest.update(bytes(plane))
    return digest.hexdigest()


def _assert_every_prefix_refused_or_identical(source: Path, work: Path) -> None:
    """The truncation invariant: a cut file never yields a different accepted sequence."""
    data = source.read_bytes()
    complete = inspect_clip(source)
    pixels = _pixels(source)
    cut = work / f"cut{source.suffix}"
    for length in range(1, len(data)):
        cut.write_bytes(data[:length])
        try:
            accepted = inspect_clip(cut)
        except CorpusRefusal:
            continue
        assert accepted.pts == complete.pts, f"{length} bytes lost frames silently"
        assert _pixels(cut) == pixels, f"{length} bytes changed pixels silently"


def _default_decoder_frames(path: Path) -> int:
    """Count frames. A flip can land in a header, whose position depends on the encoder's bytes."""
    try:
        with av.open(path) as container:
            video = container.streams.video
            return sum(1 for _ in container.decode(video[0])) if video else 0
    except av.FFmpegError:
        return 0


def _is_refused(path: Path) -> bool:
    try:
        inspect_clip(path)
    except CorpusRefusal as refusal:
        return refusal.code is RefusalCode.SOURCE_DAMAGED
    return False


@pytest.mark.parametrize(
    ("name", "codec", "pixel_format", "options"),
    [
        ("concealed.mkv", "libx264", "yuv420p", X264_WITH_B_FRAMES),
        ("crc.mkv", "ffv1", "yuv420p", {}),
        ("mpeg4.mp4", "mpeg4", "yuv420p", {}),
    ],
)
def test_damage_the_default_decoder_hides_is_refused(
    media: Path, name: str, codec: str, pixel_format: str, options: dict[str, str]
) -> None:
    """Default options return every frame here; only the strict policy reports the damage."""
    source = write_clip(media / name, codec, pixel_format, options).read_bytes()
    damaged = media / f"damaged-{name}"
    for fraction in _FLIP_FRACTIONS:
        damaged.write_bytes(source)
        flip_bytes(damaged, fraction)
        if _default_decoder_frames(damaged) == FRAME_COUNT and _is_refused(damaged):
            return
    pytest.fail("no flip was both hidden by default decoding and refused by the policy")


def test_cut_just_after_a_matroska_cluster_header_is_refused(media: Path) -> None:
    """Regression: this cut ends cleanly, so FFmpeg reported fewer frames and no error."""
    data = write_clip(media / "whole.mkv").read_bytes()
    second_cluster = data.index(_MATROSKA_CLUSTER_ID, data.index(_MATROSKA_CLUSTER_ID) + 1)
    cut = media / "cut.mkv"
    cut.write_bytes(data[: second_cluster + _CLUSTER_HEADER_BYTES])

    refusal = inspection_refusal(cut)

    assert refusal.code is RefusalCode.SOURCE_DAMAGED
    assert "segment ends at byte" in str(refusal.details["reason"])


@pytest.mark.parametrize(
    ("name", "options", "container_options"),
    [
        ("sweep.mkv", X264_WITH_B_FRAMES, None),
        ("sweep.mp4", {"preset": "ultrafast"}, None),
        ("faststart.mp4", {"preset": "ultrafast"}, MP4_OPTIONS),
    ],
)
def test_no_truncation_point_yields_a_different_accepted_sequence(
    media: Path, name: str, options: dict[str, str], container_options: dict[str, str] | None
) -> None:
    """Regression: truncated MP4 headers crashed on a stream with no codec context."""
    source = write_clip(media / name, "libx264", "yuv420p", options, container_options, frames=8)

    _assert_every_prefix_refused_or_identical(source, media)


def test_truncation_known_only_from_the_error_log_is_seen_every_time(media: Path) -> None:
    """Regression: FFmpeg's repeat filter dropped the second identical error, so a file with no
    declared length was refused once and accepted when read again in the same process."""
    whole = write_clip(media / "whole.mkv", container_options={"live": "1"})
    data = whole.read_bytes()
    damaged = media / "damaged.mkv"
    damaged.write_bytes(data[: len(data) // 2])

    assert [_is_refused(damaged) for _ in range(3)] == [True, True, True]


def test_inspection_restores_global_ffmpeg_logging(clip: Path) -> None:
    before = (av.logging.get_level(), av.logging.get_skip_repeated())

    inspect_clip(clip)

    assert (av.logging.get_level(), av.logging.get_skip_repeated()) == before


def test_a_frame_after_damage_never_reaches_the_consumer(tmp_path: Path) -> None:
    damaged = flip_bytes(write_clip(tmp_path / "clip.mkv", "ffv1", "yuv420p"), 0.6)
    seen: list[int] = []

    with pytest.raises(CorpusRefusal) as caught:
        inspect_media(damaged, POLICY, lambda index, _: seen.append(index))

    assert caught.value.code is RefusalCode.SOURCE_DAMAGED
    assert len(seen) < FRAME_COUNT


def test_a_frame_the_decoder_flags_as_corrupt_never_reaches_the_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = fake_media(monkeypatch, [decoded_frame(0, corrupt=True)])
    seen: list[int] = []

    with pytest.raises(CorpusRefusal) as caught:
        inspect_media(source, POLICY, lambda index, _: seen.append(index))

    assert caught.value.code is RefusalCode.SOURCE_DAMAGED
    assert seen == []
