"""The one strict inspection: what a healthy source decodes to, and what it records."""

from pathlib import Path

import pytest

from ss_track.core.refusal import RefusalCode
from ss_track.corpus.decoding.decode import (
    inspect_media,
)
from tests.corpus._media import (
    FRAME_COUNT,
    HEIGHT,
    MP4_OPTIONS,
    WIDTH,
    X264_WITH_B_FRAMES,
    skip_leading_samples,
    write_clip,
    write_clip_with_longer_audio,
    write_rotated_clip,
    write_size_change,
)
from tests.corpus.decoding._decoding import (
    POLICY,
    decoded_frame,
    fake_media,
    inspect_clip,
    inspection_refusal,
)


@pytest.mark.parametrize(
    ("name", "codec", "pixel_format", "options", "check"),
    [
        ("mjpeg.mkv", "mjpeg", "yuvj420p", {}, "matroska_segment_size"),
        ("h264.mkv", "libx264", "yuv420p", X264_WITH_B_FRAMES, "matroska_segment_size"),
        ("h264.mp4", "libx264", "yuv420p", X264_WITH_B_FRAMES, "frame_count"),
        ("ffv1.mkv", "ffv1", "yuv420p", {}, "matroska_segment_size"),
        ("vp9.webm", "libvpx-vp9", "yuv420p", {"cpu-used": "8"}, "matroska_segment_size"),
    ],
)
def test_healthy_media_is_accepted_and_described(
    media: Path, name: str, codec: str, pixel_format: str, options: dict[str, str], check: str
) -> None:
    result = inspect_clip(write_clip(media / name, codec, pixel_format, options))

    assert len(result.pts) == FRAME_COUNT
    assert (result.decoded_width, result.decoded_height) == (WIDTH, HEIGHT)
    assert (result.original_width, result.original_height) == (WIDTH, HEIGHT)
    assert result.source_pixel_format == pixel_format
    assert result.completeness_checks == (check,)
    assert result.video_stream_count == 1


def test_display_rotation_is_recorded_and_pixels_stay_as_stored(media: Path) -> None:
    """Regression: a player would turn this frame, so labels and pixels could silently disagree."""
    result = inspect_clip(write_rotated_clip(media / "rotated.mp4", 90))

    assert abs(result.display_rotation_degrees) == 90
    assert (result.decoded_width, result.decoded_height) == (WIDTH, HEIGHT)


def test_unrotated_media_records_zero(clip: Path) -> None:
    assert inspect_clip(clip).display_rotation_degrees == 0


def test_longer_audio_track_does_not_read_as_missing_video(media: Path) -> None:
    result = inspect_clip(write_clip_with_longer_audio(media / "av.mkv"))

    assert len(result.pts) == FRAME_COUNT


def test_edit_list_samples_are_accounted_for_and_not_called_damage(media: Path) -> None:
    """Regression: skipped samples were reported as a truncated file."""
    source = write_clip(media / "a.mp4", "libx264", "yuv420p", X264_WITH_B_FRAMES, MP4_OPTIONS)
    first, second = inspect_clip(source).pts[:2]
    assert first is not None and second is not None

    result = inspect_clip(skip_leading_samples(source, media / "b.mp4", 2 * (second - first)))

    assert len(result.pts) == FRAME_COUNT - 2
    assert result.discarded_frames == 2
    assert result.completeness_checks == ("frame_count",)


def test_frame_count_shortfall_is_refused_without_a_container_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = fake_media(monkeypatch, [decoded_frame(index) for index in range(3)], 5)

    refusal = inspection_refusal(source)

    assert refusal.code is RefusalCode.SOURCE_DAMAGED
    assert refusal.details["frames_decoded"] == 3


def test_more_frames_than_declared_is_no_completeness_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = fake_media(monkeypatch, [decoded_frame(index) for index in range(3)], 2)

    assert inspect_clip(source).completeness_checks == ()


def test_container_without_a_length_reports_no_completeness_evidence(media: Path) -> None:
    source = write_clip(
        media / "live.mkv", "libx264", "yuv420p", {}, container_options={"live": "1"}
    )

    assert inspect_clip(source).completeness_checks == ()


def test_stored_absence_of_pts_is_kept_instead_of_guessing_from_frame_rate(media: Path) -> None:
    """Regression guard: FFmpeg's default demux invents these timestamps."""
    result = inspect_clip(write_clip(media / "raw.mjpeg", container_format="mjpeg"))

    assert result.pts == (None,) * FRAME_COUNT


def test_resolution_change_within_a_stream_is_refused(media: Path) -> None:
    refusal = inspection_refusal(write_size_change(media / "sizes.mkv"))

    assert refusal.code is RefusalCode.SOURCE_FORMAT_CHANGED
    assert refusal.details["frame_index"] == 4


def test_non_media_is_unreadable(media: Path) -> None:
    path = media / "notes.mkv"
    path.write_text("not a recording\n" * 100, encoding="ascii")

    assert inspection_refusal(path).code is RefusalCode.SOURCE_UNREADABLE


def test_every_accepted_frame_reaches_the_consumer_with_its_index(clip: Path) -> None:
    seen: list[tuple[int, int | None]] = []

    inspection = inspect_media(clip, POLICY, lambda index, frame: seen.append((index, frame.pts)))

    assert seen == list(enumerate(inspection.pts))


def test_a_color_tag_change_within_a_stream_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [decoded_frame(0, colorspace=1), decoded_frame(1, colorspace=5)]

    refusal = inspection_refusal(fake_media(monkeypatch, frames))

    assert refusal.code is RefusalCode.SOURCE_FORMAT_CHANGED
    assert refusal.details["frame_index"] == 1


def test_source_color_facts_are_recorded(clip: Path) -> None:
    inspection = inspect_clip(clip)

    assert inspection.source_bits_per_component == 8
    assert (inspection.color.matrix, inspection.color.range) == (5, 2)


def test_interlaced_frames_are_counted(tmp_path: Path) -> None:
    options = {"flags": "+ildct+ilme", "preset": "ultrafast"}
    clip = write_clip(tmp_path / "clip.mkv", "libx264", "yuv420p", options)

    assert inspect_clip(clip).interlaced_frames == FRAME_COUNT
