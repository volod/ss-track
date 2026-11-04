"""The canonical decode policy: everything that can change which frames, or pixels, a source gives.

A record states the policy that produced it and its hash, so a new policy needs new evidence. The
options turn FFmpeg's concealment, short reads and invented timestamps into visible failures.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field

import av

from ss_track.core.refusal import JsonValue
from ss_track.corpus.decoding.pixels import CONVERSION_FLAGS, OUTPUT_PIXEL_FORMAT

POLICY_REVISION = 3
_FORMAT_OPTIONS = {"fflags": "nofillin", "err_detect": "explode"}
_CODEC_OPTIONS = {"err_detect": "explode", "flags": "bitexact", "idct": "simple"}
_THREAD_COUNT = 1


@dataclass(frozen=True, slots=True)
class DecodePolicy:
    """Everything that can change which frames, or which pixels, a source decodes to."""

    decoder: str
    decoder_version: str
    ffmpeg_version: str
    format_options: Mapping[str, str] = field(default_factory=lambda: dict(_FORMAT_OPTIONS))
    codec_options: Mapping[str, str] = field(default_factory=lambda: dict(_CODEC_OPTIONS))
    thread_count: int = _THREAD_COUNT
    output_pixel_format: str = OUTPUT_PIXEL_FORMAT
    conversion_flags: str = CONVERSION_FLAGS
    revision: int = POLICY_REVISION

    def as_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form stored in manifests."""
        record: dict[str, JsonValue] = asdict(self)
        return record


def current_decode_policy() -> DecodePolicy:
    """Return the policy of the installed, pinned decoder."""
    return DecodePolicy(
        decoder="pyav", decoder_version=av.__version__, ffmpeg_version=av.ffmpeg_version_info
    )
