"""The fixed corpus two architectures stage, and the commands that write and stage it.

Sources are written once and carried to the other host. Writing media again gives other bytes, on
one host through a container's random identifiers and across architectures in the packets too, so a
host that regenerated them would compare different sources. No binary enters the repository: `write` keeps this table's media under a run directory, and the CI workflow
moves it between jobs. Every source decodes through another path of the decoder or the conversion,
and each draws its own texture, so no two streams share a frame.
"""

import argparse
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from ss_track.corpus import build_corpus, import_source, record_staged_hashes, stage_corpus
from ss_track.paths import resolve_data_root
from tests.corpus._media import write_clip
from tests.corpus.conftest import case_of, corpus_declaration, group_of, recording_declaration

CORPUS_ID = "arch-fixed-v1"
CORPUS_FILE = "corpus.yaml"
RECORDINGS_FILE = "recordings.yaml"
FRAMES = 12
WIDTH = 96
HEIGHT = 64
_BOX = (230, 40, 60)
_REGION = {"x": 8, "y": 6, "width": 40, "height": 30}
_WINDOW = {"start_frame": 3, "end_frame": 9}
_BT709 = "colormatrix=bt709:colorprim=bt709:transfer=bt709"
_FAST = {"preset": "fast"}
_X265 = {"preset": "fast", "x265-params": "log-level=error"}
_VP9 = {"crf": "30", "b": "0", "cpu-used": "4"}
_AV1 = {"preset": "10", "crf": "35"}

_LOG = logging.getLogger(__name__)

type Content = Callable[[int, int, int], bytes]


@dataclass(frozen=True, slots=True)
class FixedSource:
    """One source: a decoder and pixel-format path that a stage must reproduce."""

    name: str
    container: str
    codec: str
    pixel_format: str
    options: dict[str, str] = field(default_factory=dict)
    width: int = WIDTH
    height: int = HEIGHT
    frames: int = FRAMES
    decodes_as: str | None = None

    @property
    def file_name(self) -> str:
        return f"{self.name}.{self.container}"

    @property
    def decoded_format(self) -> str:
        """Return the format a stage must report, so no row claims a path it never takes."""
        return self.decodes_as or self.pixel_format


def _x264(name: str, pixel_format: str = "yuv420p", params: str = _BT709) -> FixedSource:
    options = _FAST | {"x264-params": params}
    return FixedSource(f"h264-{name}", "mkv", "libx264", pixel_format, options)


def _raw(name: str, pixel_format: str, width: int = WIDTH, height: int = HEIGHT) -> FixedSource:
    return FixedSource(f"raw-{name}", "nut", "rawvideo", pixel_format, {}, width, height)


def _ffv1(name: str, pixel_format: str, width: int = WIDTH, height: int = HEIGHT) -> FixedSource:
    return FixedSource(f"ffv1-{name}", "mkv", "ffv1", pixel_format, {}, width, height)


SOURCES = (
    # Normative codecs: a conforming decoder has one right answer.
    _x264("420", params=f"bframes=3:{_BT709}"),
    _x264("420-full-range", params=f"range=pc:{_BT709}"),
    _x264("420-left-chroma", params=f"chromaloc=0:{_BT709}"),
    _x264("420-top-chroma", params=f"chromaloc=2:{_BT709}"),
    _x264("420-bt2020", params="colormatrix=bt2020nc:colorprim=bt2020:transfer=smpte2084"),
    _x264("420-cavlc", params=f"cabac=0:{_BT709}"),
    _x264("420-interlaced", params=f"interlaced=1:{_BT709}"),
    _x264("422", "yuv422p"),
    _x264("444", "yuv444p"),
    FixedSource("h264-gray", "mkv", "libx264", "gray", _FAST, decodes_as="yuv420p"),
    _x264("420p10", "yuv420p10le"),
    _x264("422p10", "yuv422p10le"),
    _x264("444p10", "yuv444p10le"),
    FixedSource("h264-untagged", "mp4", "libx264", "yuv420p", _FAST),
    FixedSource("h264-wide", "mkv", "libx264", "yuv420p", _FAST, 322, 182, 6),
    FixedSource("h264-wide-10-bit", "mkv", "libx264", "yuv420p10le", _FAST, 322, 182, 6),
    FixedSource("hevc-420", "mkv", "libx265", "yuv420p", _X265),
    FixedSource("hevc-420p10", "mkv", "libx265", "yuv420p10le", _X265),
    FixedSource("hevc-422p10", "mkv", "libx265", "yuv422p10le", _X265),
    FixedSource("hevc-444p12", "mkv", "libx265", "yuv444p12le", _X265),
    FixedSource("vp8-420", "webm", "libvpx", "yuv420p", {"crf": "20", "b": "200k"}),
    FixedSource("vp9-420", "webm", "libvpx-vp9", "yuv420p", _VP9),
    FixedSource("vp9-444", "mkv", "libvpx-vp9", "yuv444p", _VP9),
    FixedSource("av1-420", "mkv", "libsvtav1", "yuv420p", _AV1),
    FixedSource("av1-420p10", "mkv", "libsvtav1", "yuv420p10le", _AV1),
    # Inverse DCT codecs: no normative transform, so each differs across CPUs until it is pinned.
    FixedSource("mjpeg-420", "mkv", "mjpeg", "yuvj420p"),
    FixedSource("mjpeg-422", "mkv", "mjpeg", "yuvj422p"),
    FixedSource("mjpeg-444", "mkv", "mjpeg", "yuvj444p"),
    FixedSource("mjpeg-coarse", "mkv", "mjpeg", "yuvj420p", {"q": "28"}),
    FixedSource("mjpeg-wide", "mkv", "mjpeg", "yuvj420p", {}, 322, 182, 6),
    FixedSource("mpeg1-420", "mkv", "mpeg1video", "yuv420p", {"bf": "2"}),
    FixedSource("mpeg2-420", "mkv", "mpeg2video", "yuv420p", {"bf": "2"}),
    FixedSource("mpeg2-422", "mkv", "mpeg2video", "yuv422p"),
    FixedSource("mpeg4-420", "mkv", "mpeg4", "yuv420p", {"bf": "2"}),
    FixedSource("mpeg4-qpel", "mkv", "mpeg4", "yuv420p", {"flags": "+qpel"}),
    FixedSource("h263-420", "avi", "h263p", "yuv420p"),
    FixedSource("msmpeg4-420", "avi", "msmpeg4", "yuv420p"),
    FixedSource("wmv2-420", "avi", "wmv2", "yuv420p"),
    FixedSource("dv-420", "avi", "dvvideo", "yuv420p", {}, 720, 576, 4),
    FixedSource("dnxhd-422", "mov", "dnxhd", "yuv422p", {"b": "36M"}, 1920, 1080, 2),
    FixedSource(
        "dnxhr-422p10", "mov", "dnxhd", "yuv422p10le", {"profile": "dnxhr_hqx"}, 1280, 720, 2
    ),
    FixedSource("prores-422p10", "mov", "prores_ks", "yuv422p10le"),
    FixedSource("prores-444", "mov", "prores_ks", "yuv444p10le", decodes_as="yuv444p12le"),
    FixedSource("jpeg2000-rgb", "mkv", "jpeg2000", "rgb24", frames=3),
    # Lossless and raw sources: decoding is exact, so these exercise the conversion to RGB.
    _ffv1("420", "yuv420p"),
    _ffv1("444", "yuv444p"),
    _ffv1("420p10", "yuv420p10le"),
    _ffv1("411", "yuv411p"),
    _ffv1("410", "yuv410p"),
    _ffv1("alpha", "yuva420p"),
    _ffv1("bgra", "bgra"),
    _ffv1("gray", "gray"),
    _ffv1("gray16", "gray16le"),
    _ffv1("odd-444", "yuv444p", 99, 67),
    FixedSource("huffyuv-422", "avi", "huffyuv", "yuv422p"),
    FixedSource("ffvhuff-420", "avi", "ffvhuff", "yuv420p"),
    _raw("nv12", "nv12"),
    _raw("nv21", "nv21"),
    _raw("yuyv", "yuyv422"),
    _raw("uyvy", "uyvy422"),
    _raw("rgb24", "rgb24"),
    _raw("bgr24", "bgr24"),
    _raw("rgba", "rgba"),
    _raw("rgb565", "rgb565le"),
    _raw("rgb555", "rgb555le"),
    _raw("420p16", "yuv420p16le"),
    _raw("444p16", "yuv444p16le"),
    _raw("gbrp10", "gbrp10le"),
    _raw("odd-420", "yuv420p", 97, 65),
    _raw("odd-nv12", "nv12", 97, 65),
    _raw("short-row-yuyv", "yuyv422", 102, 66),
)
_CASE_PARENT = "h264-420"
_CASES = (
    ("target_absence", {"region": _REGION, "plate_frame": 0, "noise": 6}),
    ("moving_background", {"region": _REGION, "sprite_count": 4, "sprite_size": 5, "max_speed": 3}),
    ("camera_shake", {"amplitude": 4}),
    ("blur", {"max_radius": 3}),
    ("dropped_frames", {"count": 2}),
    ("duplicated_frames", {"count": 2}),
    ("short_occlusion", {"region": _REGION}),
)


def _content(name: str) -> Content:
    """Return a clip's frames: this source's own texture, a moving ramp and a sharp moving box."""

    def frame(index: int, width: int, height: int) -> bytes:
        seed = f"fixed-corpus-{name}".encode("ascii")
        texture = np.frombuffer(
            hashlib.shake_256(seed).digest(width * height * 3), dtype=np.uint8
        ).reshape(height, width, 3)
        columns = np.arange(width)[None, :, None]
        rows = np.arange(height)[:, None, None]
        ramp = (columns * 3 + rows * 2 + index * 5) % 256
        moved = np.roll(texture, (index * 2, index * 3), (0, 1))
        pixels = (moved // 4 + ramp // 2 + 40).astype(np.uint8)
        top, left = height // 6 + index, width // 5 + index * 2
        pixels[top : top + height // 3, left : left + width // 3] = _BOX
        return pixels.tobytes()

    return frame


def _recording_name(source: FixedSource) -> str:
    return f"{source.name}.yaml"


def write_sources(output: Path, sources: tuple[FixedSource, ...] = SOURCES) -> Path:
    """Write every source and its recording declaration into one directory that can be moved."""
    output.mkdir(parents=True, exist_ok=True)
    for source in sources:
        write_clip(
            output / source.file_name,
            source.codec,
            source.pixel_format,
            source.options,
            frames=source.frames,
            width=source.width,
            height=source.height,
            content=_content(source.name),
        )
        declaration = yaml.safe_dump(recording_declaration(source.file_name))
        (output / _recording_name(source)).write_text(declaration, encoding="utf-8")
    names = [_recording_name(source) for source in sources]
    (output / RECORDINGS_FILE).write_text(yaml.safe_dump(names), encoding="utf-8")
    return output


def _stream(name: str, source_sha256: str) -> dict[str, object]:
    stream: dict[str, object] = {"stream_id": name, "source_sha256": source_sha256}
    if name == _CASE_PARENT:
        stream["generated_cases"] = [
            case_of(f"{name}-{transform}", transform, seed, parameters, window=_WINDOW)
            for seed, (transform, parameters) in enumerate(_CASES)
        ]
    return stream


def _write_corpus(sources: Path, source_hashes: dict[str, str]) -> Path:
    """Declare one group of one encounter per source, which holds every transform once."""
    encounters = [
        {"encounter_id": name, "streams": [_stream(name, sha256)]}
        for name, sha256 in sorted(source_hashes.items())
    ]
    declaration = corpus_declaration(
        [group_of("fixed", "development", *encounters)], corpus_id=CORPUS_ID
    )
    path = sources / CORPUS_FILE
    path.write_text(yaml.safe_dump(declaration), encoding="utf-8")
    return path


def stage_sources(sources: Path, run_id: str, data_root: Path) -> str:
    """Import, build, stage and verify the corpus, record its hashes, and return its frame set."""
    names = yaml.safe_load((sources / RECORDINGS_FILE).read_text(encoding="utf-8"))
    hashes = {
        Path(name).stem: import_source(sources / name, data_root).source_sha256 for name in names
    }
    build_corpus(_write_corpus(sources, hashes), data_root)
    stage_corpus(CORPUS_ID, data_root)
    return record_staged_hashes(CORPUS_ID, run_id, data_root).frame_set_sha256


def main() -> None:
    """Write the sources, or stage ones that another host wrote."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", help="write the sources once")
    write.add_argument("--output", type=Path, required=True)
    stage = commands.add_parser("stage", help="stage stored sources and record their hashes")
    stage.add_argument("--sources", type=Path, required=True)
    stage.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "write":
        _LOG.info("wrote %d sources to %s", len(SOURCES), write_sources(args.output))
    else:
        frame_set = stage_sources(args.sources, args.run_id, resolve_data_root())
        _LOG.info("frame_set_sha256 %s", frame_set)


if __name__ == "__main__":
    main()
