"""Paths, records and refusal checks that the frame-set tests share."""

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus, stage_corpus
from ss_track.corpus.bundles.stage_report import FramesResult
from tests.corpus.conftest import (
    WriteCorpus,
    case_of,
    reseal,
    stream_of,
)

CORPUS = "pilot-v1"
SHAKE = {"amplitude": 2}

type Refused = Callable[[RefusalCode], CorpusRefusal]


def frame_set_path(data_root: Path, corpus: str = CORPUS) -> Path:
    return data_root / "corpus" / corpus / "frame-set.json"


def bundle_path(data_root: Path, name: str) -> Path:
    return data_root / "corpus" / CORPUS / "frames" / name


def remove_bundle(data_root: Path, name: str) -> None:
    directory = bundle_path(data_root, name)
    directory.chmod(0o755)
    shutil.rmtree(directory)


def replace_bundle(data_root: Path, name: str, donor: str) -> None:
    """Put another stream's frames under a name, in a record consistent with itself."""
    remove_bundle(data_root, name)
    shutil.copytree(bundle_path(data_root, donor), bundle_path(data_root, name))
    reseal(bundle_path(data_root, name) / "manifest.json", stream_id=name)


def read_record(path: Path) -> dict[str, object]:
    record: dict[str, object] = json.loads(path.read_text(encoding="ascii"))
    return record


def bundle_hashes(result: FramesResult) -> dict[str, str]:
    return {bundle.stream_id: bundle.bundle_sha256 for bundle in result.bundles}


def refused_by(action: Callable[[str, Path], FramesResult], root: Path) -> Refused:
    def refused(code: RefusalCode) -> CorpusRefusal:
        with pytest.raises(CorpusRefusal) as caught:
            action(CORPUS, root)
        assert caught.value.code is code
        return caught.value

    return refused


def stage_two_streams(
    first: ImportResult, second: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> FramesResult:
    """Stage two streams, the first with a generated case, as most frame-set tests need."""
    streams = [
        stream_of(
            first,
            stream_id="one",
            generated_cases=[case_of("shaken", "camera_shake", 1, SHAKE)],
        ),
        stream_of(second, stream_id="two"),
    ]
    build_corpus(write_corpus(streams), data_root)
    return stage_corpus(CORPUS, data_root)
