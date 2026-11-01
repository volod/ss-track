"""Small synthetic media, generated at test time so no binary enters the repository."""

from collections.abc import Callable, Sequence
from fractions import Fraction
from pathlib import Path

import av

WIDTH = 64
HEIGHT = 48
FRAME_COUNT = 24
FRAME_RATE = 25
_MILLISECOND = Fraction(1, 1000)
_AUDIO_RATE = 48000
_AUDIO_PACKET_SAMPLES = 4800
_AUDIO_PACKETS = 30
X264_WITH_B_FRAMES = {"preset": "medium", "bframes": "3"}
MP4_OPTIONS = {"movflags": "faststart"}


def expected_rgb(index: int, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """Return the packed pixels of one synthetic frame, for comparison after a lossless trip."""
    return b"".join(
        bytes(
            value
            for x in range(width)
            for value in ((x * 5 + index * 7) % 256, (y * 5) % 256, (index * 11) % 256)
        )
        for y in range(height)
    )


def flat_rgb(_: int, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """Return one uniform frame, which every blur leaves exactly as it is."""
    return bytes((90, 120, 150)) * (width * height)


def _frame(
    index: int,
    width: int = WIDTH,
    height: int = HEIGHT,
    content: Callable[[int, int, int], bytes] = expected_rgb,
) -> av.VideoFrame:
    frame = av.VideoFrame(width, height, "rgb24")
    plane = frame.planes[0]
    row_bytes = width * 3
    pixels = content(index, width, height)
    padding = bytes(plane.line_size - row_bytes)
    plane.update(
        b"".join(pixels[row * row_bytes : (row + 1) * row_bytes] + padding for row in range(height))
    )
    return frame


def write_clip(
    path: Path,
    codec: str = "mjpeg",
    pixel_format: str = "yuvj420p",
    options: dict[str, str] | None = None,
    container_options: dict[str, str] | None = None,
    container_format: str | None = None,
    frames: int = FRAME_COUNT,
    width: int = WIDTH,
    height: int = HEIGHT,
    content: Callable[[int, int, int], bytes] = expected_rgb,
) -> Path:
    """Encode a short deterministic clip."""
    with av.open(path, "w", format=container_format, options=container_options or {}) as container:
        stream = container.add_stream(codec, rate=FRAME_RATE)
        stream.width, stream.height, stream.pix_fmt = width, height, pixel_format
        stream.thread_count = 1
        stream.options = options or {}
        for index in range(frames):
            frame = _frame(index, width, height, content).reformat(format=pixel_format)
            frame.pts, frame.time_base = index, Fraction(1, FRAME_RATE)
            container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
    return path


def write_rotated_clip(path: Path, degrees: int) -> Path:
    """Write an MP4 that asks players to rotate it, leaving its stored pixels upright."""
    with av.open(path, "w") as container:
        stream = container.add_stream("libx264", rate=FRAME_RATE)
        stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
        stream.options = {"preset": "ultrafast"}
        stream.set_display_rotation(degrees)
        for index in range(FRAME_COUNT):
            frame = _frame(index).reformat(format="yuv420p")
            frame.pts, frame.time_base = index, Fraction(1, FRAME_RATE)
            container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
    return path


def _mjpeg_payloads(width: int, height: int, frames: int) -> list[bytes]:
    encoder = av.CodecContext.create("mjpeg", "w")
    encoder.width, encoder.height, encoder.pix_fmt = width, height, "yuvj420p"
    encoder.time_base = Fraction(1, FRAME_RATE)
    payloads: list[bytes] = []
    for index in range(frames):
        frame = _frame(index, width, height).reformat(format="yuvj420p")
        frame.pts = index
        payloads += [bytes(packet) for packet in encoder.encode(frame)]
    return payloads + [bytes(packet) for packet in encoder.encode(None)]


def _mux_mjpeg(
    path: Path,
    payloads: Sequence[bytes],
    pts: Sequence[int],
    dts: Sequence[int],
    audio: bool = False,
) -> Path:
    with av.open(path, "w") as container:
        video = container.add_stream("mjpeg", rate=FRAME_RATE)
        video.width, video.height, video.pix_fmt = WIDTH, HEIGHT, "yuvj420p"
        video.time_base = _MILLISECOND
        # Every stream must exist before the first packet writes the container header.
        sound = (
            container.add_stream("pcm_s16le", rate=_AUDIO_RATE, layout="mono") if audio else None
        )
        for payload, presented, decoded in zip(payloads, pts, dts, strict=True):
            packet = av.Packet(payload)
            packet.stream, packet.time_base = video, _MILLISECOND
            packet.pts, packet.dts, packet.is_keyframe = presented, decoded, True
            container.mux(packet)
        if sound is not None:
            _mux_silence(container, sound)
    return path


def _mux_silence(container: av.container.OutputContainer, stream: av.audio.AudioStream) -> None:
    time_base = Fraction(1, _AUDIO_RATE)
    for index in range(_AUDIO_PACKETS):
        packet = av.Packet(bytes(_AUDIO_PACKET_SAMPLES * 2))
        packet.stream, packet.time_base = stream, time_base
        packet.pts = packet.dts = index * _AUDIO_PACKET_SAMPLES
        container.mux(packet)


def write_clip_with_pts(path: Path, pts: Sequence[int]) -> Path:
    """Mux intra frames with exact PTS, keeping DTS valid so bad PTS reach the reader."""
    payloads = _mjpeg_payloads(WIDTH, HEIGHT, len(pts))
    return _mux_mjpeg(path, payloads, pts, list(range(0, 2 * len(pts), 2)))


def write_clip_with_longer_audio(path: Path) -> Path:
    """Write a clip whose audio outlasts its video, as field recorders often do."""
    pts = [index * 40 for index in range(FRAME_COUNT)]
    payloads = _mjpeg_payloads(WIDTH, HEIGHT, FRAME_COUNT)
    return _mux_mjpeg(path, payloads, pts, pts, audio=True)


def write_size_change(path: Path) -> Path:
    """Write a stream that changes resolution partway through."""
    payloads = _mjpeg_payloads(WIDTH, HEIGHT, 4) + _mjpeg_payloads(WIDTH // 2, HEIGHT // 2, 4)
    pts = [index * 40 for index in range(len(payloads))]
    return _mux_mjpeg(path, payloads, pts, pts)


def flip_bytes(path: Path, fraction: float, length: int = 32) -> Path:
    """Invert a run of bytes in place, leaving the file length unchanged."""
    data = bytearray(path.read_bytes())
    start = int(len(data) * fraction)
    data[start : start + length] = bytes(value ^ 0xFF for value in data[start : start + length])
    path.write_bytes(data)
    return path


def skip_leading_samples(source: Path, target: Path, media_time_delta: int) -> Path:
    """Make an MP4 edit list skip stored samples without touching the samples themselves."""
    data = bytearray(source.read_bytes())
    media_time_at = data.index(b"elst") + 16
    media_time = int.from_bytes(data[media_time_at : media_time_at + 4])
    data[media_time_at : media_time_at + 4] = (media_time + media_time_delta).to_bytes(4)
    target.write_bytes(data)
    return target
