"""One staged corpus and its hash record, for the host-hash and comparison tests."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ss_track.core.canonical import SEAL_FIELD
from ss_track.corpus import (
    CorpusRefusal,
    build_corpus,
    compare_staged_hashes,
    import_source,
    record_staged_hashes,
    stage_corpus,
)
from ss_track.corpus.hosts.host_hashes import STAGED_HASHES_NAME
from tests._sealing import self_sealed
from tests.corpus.conftest import WriteCorpus, WriteRecording, case_of, stream_of

CORPUS = "pilot-v1"
RUN = "run-one"
BLUR = case_of("one-blur", "blur", 7, {"max_radius": 2})


def declare_and_stage(
    write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> tuple[Path, Path]:
    """Declare one source with one generated case, and stage them on the first host."""
    recording = write_recording()
    result = import_source(recording, data_root)
    corpus = write_corpus([stream_of(result, generated_cases=[BLUR])])
    build_corpus(corpus, data_root)
    stage_corpus(CORPUS, data_root)
    return recording, corpus


def bundle_line(record: dict[str, Any], stream_id: str) -> dict[str, Any]:
    return next(line for line in record["bundles"] if line["stream_id"] == stream_id)


OTHER_HASH = "f" * 64
type Change = Callable[[dict[str, Any]], None]


def stage_on_other_host(declared: tuple[Path, Path], tmp_path: Path) -> Path:
    """The same corpus staged on another data root, standing for the other host."""
    other_root = tmp_path / "other-host"
    recording, corpus = declared
    import_source(recording, other_root)
    build_corpus(corpus, other_root)
    stage_corpus(CORPUS, other_root)
    return record_staged_hashes(CORPUS, RUN, other_root).record_path


def other_host(path: Path, target_root: Path, change: Change) -> Path:
    """Change a copy of a record as another host's would differ, keeping its seal whole."""
    target = target_root / "changed" / STAGED_HASHES_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    record = json.loads(path.read_text(encoding="ascii"))
    record.pop(SEAL_FIELD)
    change(record)
    target.write_text(json.dumps(self_sealed(record)), encoding="ascii")
    return target


def compare_refusal(left: Path, right: Path, data_root: Path) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        compare_staged_hashes(left, right, RUN, data_root)
    return caught.value
