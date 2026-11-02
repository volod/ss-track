"""Shared steps of the amendment tests."""

from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.corpus import (
    AmendmentResult,
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
)
from tests.corpus.conftest import WriteCorpus, recording_declaration, stream_of

SOURCE_KIND = "ss-track.source-manifest"
CORPUS = "pilot-v1"


def rights_with(**changes: object) -> dict[str, object]:
    rights = recording_declaration()["rights"]
    assert isinstance(rights, dict)
    return rights | changes


def refused(run: Callable[[], object], code: RefusalCode) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        run()
    assert caught.value.code is code
    return caught.value


def stored_source(source: ImportResult | AmendmentResult) -> Path:
    return next(source.manifest_path.parent.glob("source.*"))


def evidence(directory: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def staged(source: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> None:
    build_corpus(write_corpus([stream_of(source)]), data_root)
    stage_corpus(CORPUS, data_root)
