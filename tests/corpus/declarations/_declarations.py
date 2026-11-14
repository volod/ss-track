"""Minimal recording and corpus declarations, and a writer for altered copies of them."""

from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.declaration import load_recording_declaration

SHA256 = "a" * 64
RECORDING = """\
schema_version: 3
source: {path: clip.mkv}
rights: {holder: Owner, basis: owned, retention: one year, sharing: restricted, retain_until: null, derived_frames: true}
sensitivity: {level: low}
"""
CORPUS = f"""\
schema_version: 3
corpus_id: pilot-v1
scenario_rights: {{sharing: restricted, max_sensitivity: moderate}}
groups:
  - group_id: site-a
    split: development
    encounters:
      - encounter_id: enc01
        streams:
          - {{stream_id: one, source_sha256: "{SHA256}"}}
"""


def writer_in(tmp_path: Path) -> Callable[[str], Path]:
    """Return a function that writes one declaration's text and gives its path."""

    def write(text: str) -> Path:
        path = tmp_path / "declaration.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    return write


def refused_recording(path: Path) -> str:
    with pytest.raises(CorpusRefusal) as caught:
        load_recording_declaration(path)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    return caught.value.message
