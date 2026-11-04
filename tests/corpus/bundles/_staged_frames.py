"""Two staged streams and ways to damage their files, for the frame and bundle tests."""

from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus._media import WIDTH, write_clip
from tests.corpus.conftest import WriteCorpus, WriteRecording, stream_of

CORPUS = "pilot-v1"


def stage_two_streams(
    imported: ImportResult,
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
) -> Path:
    """Return the directory of one staged bundle, writable so a test can damage it."""
    write_clip(media / "other.mkv", width=WIDTH + 2)
    other = import_source(write_recording("other.mkv"), data_root)
    streams = [stream_of(imported), stream_of(other, stream_id="two")]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus(CORPUS, data_root)
    directory = data_root / "corpus" / CORPUS / "frames" / "one"
    directory.chmod(0o755)
    return directory


def make_writable(path: Path) -> Path:
    path.chmod(0o644)
    return path


def flip_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    make_writable(path).write_bytes(data)


def delete_frame(path: Path) -> None:
    path.unlink()


def frames_refusal(data_root: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(CORPUS, data_root)
    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    return caught.value
