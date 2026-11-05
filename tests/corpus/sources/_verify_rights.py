"""Dates, a staged corpus and the refusal of `corpus verify`, for the verification tests."""

from datetime import date
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus.conftest import (
    WriteCorpus,
    stream_of,
)

CORPUS = "pilot-v1"
BEFORE = date(1999, 12, 31)
UNTIL = date(2000, 1, 1)
AFTER = date(2000, 1, 2)


def refused_verify(data_root: Path, code: RefusalCode, today: date | None = None) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(CORPUS, data_root, today=today)
    assert caught.value.code is code
    return caught.value


def stage_before(source: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> None:
    build_corpus(write_corpus([stream_of(source)]), data_root, today=BEFORE)
    stage_corpus(CORPUS, data_root, today=BEFORE)
