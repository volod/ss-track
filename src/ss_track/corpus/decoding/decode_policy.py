"""The canonical decode policy: everything that can change which frames, or pixels, a source gives.

A record states the policy that produced it and its hash, so a new policy needs new evidence. The
options turn FFmpeg's concealment, short reads and invented timestamps into visible failures.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field

import av

from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.decoding.declared_color import sws_colorspace
from ss_track.corpus.decoding.pixels import CONVERSION_FLAGS, OUTPUT_PIXEL_FORMAT, PixelConverter

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

    def sha256(self) -> str:
        """Return the hash that identifies this policy, over its canonical record."""
        return sha256_bytes(canonical_json(self.as_record()))

    def record_fields(self) -> dict[str, JsonValue]:
        """Return the two fields a record decoded under this policy states: it and its hash."""
        return {"decode_policy": self.as_record(), "decode_policy_sha256": self.sha256()}

    def converter(self, matrix: int | None = None) -> PixelConverter:
        """Return a converter under this policy, applying a recorded declared matrix when given."""
        colorspace = None if matrix is None else sws_colorspace(matrix)
        return PixelConverter(self.conversion_flags, self.thread_count, matrix=colorspace)


def current_decode_policy() -> DecodePolicy:
    """Return the policy of the installed, pinned decoder."""
    return DecodePolicy(
        decoder="pyav", decoder_version=av.__version__, ffmpeg_version=av.ffmpeg_version_info
    )


def require_policy(found: JsonValue, expected: str, origin: str) -> None:
    """Refuse a record or pin decoded under anything but the installed policy, whose hash is
    `expected`. An absent pin, `None`, asks for no policy in particular.
    """
    if found is not None and found != expected:
        raise CorpusRefusal(
            RefusalCode.DECODE_POLICY_MISMATCH,
            f"{origin} uses a different decode policy than the installed decoder",
            {"found_decode_policy_sha256": found, "installed_decode_policy_sha256": expected},
        )
