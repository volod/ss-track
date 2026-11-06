"""Shared steps of the amendment tests."""

from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.core.refusal import JsonValue
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    ReplacementResult,
    build_corpus,
    stage_corpus,
)
from ss_track.corpus.records.kinds import SOURCE_MANIFEST
from ss_track.corpus.records.sealed import read_stated
from tests.corpus.conftest import WriteCorpus, recording_declaration, stream_of

CORPUS = "pilot-v1"


def rights_with(**changes: object) -> dict[str, object]:
    rights = recording_declaration()["rights"]
    assert isinstance(rights, dict)
    return rights | changes


def read_source(path: Path) -> dict[str, JsonValue]:
    """Read a source record of either major an amendment handles, as the command itself does."""
    return read_stated(path, SOURCE_MANIFEST).record


def refused(run: Callable[[], object], code: RefusalCode) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        run()
    assert caught.value.code is code
    return caught.value


def stored_source(source: ImportResult | ReplacementResult) -> Path:
    return next(source.manifest_path.parent.glob("source.*"))


def evidence(directory: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def staged(source: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> None:
    build_corpus(write_corpus([stream_of(source)]), data_root)
    stage_corpus(CORPUS, data_root)
