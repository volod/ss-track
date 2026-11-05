"""Staging one stream with generated cases, for the case-frame and case-refusal tests."""

from pathlib import Path

from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from tests.corpus.conftest import (
    WriteCorpus,
    stream_of,
)

CORPUS = "pilot-v1"
SHAKE = {"amplitude": 2}


def case_frames_root(data_root: Path) -> Path:
    return data_root / "corpus" / CORPUS / "frames"


def stage_cases(
    imported: ImportResult, write: WriteCorpus, data_root: Path, *cases: dict[str, object]
) -> Path:
    build_corpus(write([stream_of(imported, generated_cases=list(cases))]), data_root)
    stage_corpus(CORPUS, data_root)
    return case_frames_root(data_root)
