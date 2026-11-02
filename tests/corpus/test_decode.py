import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import av
import av.logging
import pytest

from ss_track.corpus.decode import (
    DecodePolicy,
    MediaInspection,
    _decode_all,
    _Decoded,
    _frame_count_checks,
    _require_one_shape,
    current_decode_policy,
    inspect_media,
)
from ss_track.corpus.importer import decode_policy_sha256
from ss_track.corpus.refusal import CorpusRefusal, RefusalCode
from tests.corpus._media import (
    FRAME_COUNT,
    HEIGHT,
    MP4_OPTIONS,
    WIDTH,
    X264_WITH_B_FRAMES,
    flip_bytes,
    skip_leading_samples,
    write_clip,
    write_clip_with_longer_audio,
    write_rotated_clip,
    write_size_change,
)

POLICY = current_decode_policy()
_MATROSKA_CLUSTER_ID = bytes.fromhex("1F43B675")
_CLUSTER_HEADER_BYTES = 8
# Early enough for short streams, whose payload ends where a late fraction would reach the header.
_FLIP_FRACTIONS = tuple(step / 20 for step in range(1, 19))


def _inspect(path: Path) -> MediaInspection:
    return inspect_media(path, POLICY)


def _refusal(path: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        _inspect(path)
    return caught.value


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
    complete = _inspect(source)
    pixels = _pixels(source)
    cut = work / f"cut{source.suffix}"
    for length in range(1, len(data)):
        cut.write_bytes(data[:length])
        try:
            accepted = _inspect(cut)
        except CorpusRefusal:
            continue
        assert accepted.pts == complete.pts, f"{length} bytes lost frames silently"
        assert _pixels(cut) == pixels, f"{length} bytes changed pixels silently"


def test_policy_turns_off_the_behaviors_that_fabricate_evidence() -> None:
    assert POLICY.decoder == "pyav"
    assert POLICY.decoder_version == av.__version__
    assert POLICY.ffmpeg_version == av.ffmpeg_version_info
    assert POLICY.format_options["fflags"] == "nofillin"
    assert POLICY.codec_options["err_detect"] == "explode"
    assert POLICY.thread_count == 1
    assert POLICY.output_pixel_format == "rgb24"


def test_policy_pins_the_inverse_dct_that_bitexact_leaves_to_the_cpu() -> None:
    """Regression: 14 of 71 fixed sources decoded differently on arm64 without this option."""
    assert POLICY.codec_options["flags"] == "bitexact"
    assert POLICY.codec_options["idct"] == "simple"


def test_the_inverse_dct_option_reaches_the_decoder(media: Path) -> None:
    """x86-64 gives the same pixels with or without the pin, so only another IDCT can show this."""
    clip = write_clip(media / "clip.mkv")
    other = replace(POLICY, codec_options=dict(POLICY.codec_options) | {"idct": "faani"})

    def decoded(policy: DecodePolicy) -> str:
        digest = hashlib.sha256()
        inspect_media(clip, policy, lambda _, frame: digest.update(bytes(frame.planes[0])))
        return digest.hexdigest()

    assert decoded(POLICY) != decoded(other)


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
    result = _inspect(write_clip(media / name, codec, pixel_format, options))

    assert len(result.pts) == FRAME_COUNT
    assert (result.decoded_width, result.decoded_height) == (WIDTH, HEIGHT)
    assert (result.original_width, result.original_height) == (WIDTH, HEIGHT)
    assert result.source_pixel_format == pixel_format
    assert result.completeness_checks == (check,)
    assert result.video_stream_count == 1


def test_display_rotation_is_recorded_and_pixels_stay_as_stored(media: Path) -> None:
    """Regression: a player would turn this frame, so labels and pixels could silently disagree."""
    result = _inspect(write_rotated_clip(media / "rotated.mp4", 90))

    assert abs(result.display_rotation_degrees) == 90
    assert (result.decoded_width, result.decoded_height) == (WIDTH, HEIGHT)


def test_unrotated_media_records_zero(clip: Path) -> None:
    assert _inspect(clip).display_rotation_degrees == 0


def test_longer_audio_track_does_not_read_as_missing_video(media: Path) -> None:
    result = _inspect(write_clip_with_longer_audio(media / "av.mkv"))

    assert len(result.pts) == FRAME_COUNT


def test_edit_list_samples_are_accounted_for_and_not_called_damage(media: Path) -> None:
    """Regression: skipped samples were reported as a truncated file."""
    source = write_clip(media / "a.mp4", "libx264", "yuv420p", X264_WITH_B_FRAMES, MP4_OPTIONS)
    first, second = _inspect(source).pts[:2]
    assert first is not None and second is not None

    result = _inspect(skip_leading_samples(source, media / "b.mp4", 2 * (second - first)))

    assert len(result.pts) == FRAME_COUNT - 2
    assert result.discarded_frames == 2
    assert result.completeness_checks == ("frame_count",)


def test_frame_count_shortfall_is_refused_without_a_container_error() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        _frame_count_checks(5, _Decoded(pts=[0, 1, 2]))

    assert caught.value.code is RefusalCode.SOURCE_DAMAGED
    assert caught.value.details["frames_decoded"] == 3


def test_more_frames_than_declared_is_no_completeness_evidence() -> None:
    assert _frame_count_checks(2, _Decoded(pts=[0, 1, 2])) == ()


def test_container_without_a_length_reports_no_completeness_evidence(media: Path) -> None:
    source = write_clip(
        media / "live.mkv", "libx264", "yuv420p", {}, container_options={"live": "1"}
    )

    assert _inspect(source).completeness_checks == ()


def test_stored_absence_of_pts_is_kept_instead_of_guessing_from_frame_rate(media: Path) -> None:
    """Regression guard: FFmpeg's default demux invents these timestamps."""
    result = _inspect(write_clip(media / "raw.mjpeg", container_format="mjpeg"))

    assert result.pts == (None,) * FRAME_COUNT


def test_resolution_change_within_a_stream_is_refused(media: Path) -> None:
    refusal = _refusal(write_size_change(media / "sizes.mkv"))

    assert refusal.code is RefusalCode.SOURCE_FORMAT_CHANGED
    assert refusal.details["frame_index"] == 4


def test_non_media_is_unreadable(media: Path) -> None:
    path = media / "notes.mkv"
    path.write_text("not a recording\n" * 100, encoding="ascii")

    assert _refusal(path).code is RefusalCode.SOURCE_UNREADABLE


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
        _inspect(path)
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

    refusal = _refusal(cut)

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

    _inspect(clip)

    assert (av.logging.get_level(), av.logging.get_skip_repeated()) == before


def test_every_accepted_frame_reaches_the_consumer_with_its_index(clip: Path) -> None:
    seen: list[tuple[int, int | None]] = []

    inspection = inspect_media(clip, POLICY, lambda index, frame: seen.append((index, frame.pts)))

    assert seen == list(enumerate(inspection.pts))


def test_a_frame_after_damage_never_reaches_the_consumer(tmp_path: Path) -> None:
    damaged = flip_bytes(write_clip(tmp_path / "clip.mkv", "ffv1", "yuv420p"), 0.6)
    seen: list[int] = []

    with pytest.raises(CorpusRefusal) as caught:
        inspect_media(damaged, POLICY, lambda index, _: seen.append(index))

    assert caught.value.code is RefusalCode.SOURCE_DAMAGED
    assert len(seen) < FRAME_COUNT


def test_a_frame_the_decoder_flags_as_corrupt_never_reaches_the_consumer() -> None:
    frame = SimpleNamespace(is_corrupt=True)
    packet = SimpleNamespace(is_corrupt=False, is_discard=False, decode=lambda: [frame])
    container = SimpleNamespace(demux=lambda _: [packet])
    seen: list[int] = []

    with pytest.raises(CorpusRefusal):
        _decode_all(container, None, [], _Decoded(), lambda i, _: seen.append(i))  # type: ignore[arg-type]

    assert seen == []


def test_a_color_tag_change_within_a_stream_is_refused() -> None:
    first, second = av.VideoFrame(16, 16, "yuv420p"), av.VideoFrame(16, 16, "yuv420p")
    first.colorspace, second.colorspace = 1, 5
    decoded = _Decoded()
    _require_one_shape(first, decoded)

    with pytest.raises(CorpusRefusal) as caught:
        _require_one_shape(second, decoded)

    assert caught.value.code is RefusalCode.SOURCE_FORMAT_CHANGED


def test_source_color_facts_are_recorded(clip: Path) -> None:
    inspection = _inspect(clip)

    assert inspection.source_bits_per_component == 8
    assert (inspection.color.matrix, inspection.color.range) == (5, 2)


def test_the_conversion_is_part_of_the_policy_identity() -> None:
    changed = replace(POLICY, conversion_flags="BILINEAR")

    assert decode_policy_sha256(changed.as_record()) != decode_policy_sha256(POLICY.as_record())


def test_interlaced_frames_are_counted(tmp_path: Path) -> None:
    options = {"flags": "+ildct+ilme", "preset": "ultrafast"}
    clip = write_clip(tmp_path / "clip.mkv", "libx264", "yuv420p", options)

    assert _inspect(clip).interlaced_frames == FRAME_COUNT
