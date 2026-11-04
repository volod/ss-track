"""The canonical decode policy turns off what fabricates evidence, and its hash covers it."""

import hashlib
from dataclasses import replace
from pathlib import Path

import av
import av.logging

from ss_track.corpus.decoding.decode import (
    inspect_media,
)
from ss_track.corpus.decoding.decode_policy import DecodePolicy
from ss_track.corpus.sources.importer import decode_policy_sha256
from tests.corpus._media import (
    write_clip,
)
from tests.corpus.decoding._decoding import POLICY


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


def test_the_conversion_is_part_of_the_policy_identity() -> None:
    changed = replace(POLICY, conversion_flags="BILINEAR")

    assert decode_policy_sha256(changed.as_record()) != decode_policy_sha256(POLICY.as_record())
