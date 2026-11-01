"""Shared corpus fixtures: a clean data root and written operator declarations."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from ss_track.corpus import import_source
from ss_track.corpus.importer import ImportResult
from ss_track.corpus.sealed import seal, sha256_file
from tests.corpus._media import write_clip

type Recording = dict[str, object]
type WriteRecording = Callable[..., Path]
type WriteCorpus = Callable[..., Path]


def recording_declaration(source: str = "clip.mkv") -> Recording:
    """Return a complete recording declaration that a test may then damage."""
    return {
        "schema_version": 1,
        "source": {"path": source},
        "rights": {
            "holder": "Project Contributors",
            "basis": "owned",
            "retention": "project duration",
            "sharing": "restricted",
        },
        "sensitivity": {"level": "low"},
    }


def sequence_of(result: ImportResult, **fields: object) -> dict[str, object]:
    """Return one corpus sequence entry naming an imported source."""
    return {"sequence_id": "one", "source_sha256": result.source_sha256} | fields


def reseal(path: Path, **changes: object) -> None:
    """Change a record and repair its seal, as a wrong but self-consistent record would be."""
    record = json.loads(path.read_text(encoding="ascii"))
    record.pop("manifest_sha256")
    path.chmod(0o644)
    path.write_text(json.dumps(seal(record | changes)), encoding="ascii")


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def media(tmp_path: Path) -> Path:
    directory = tmp_path / "media"
    directory.mkdir()
    return directory


@pytest.fixture
def clip(media: Path) -> Path:
    return write_clip(media / "clip.mkv")


@pytest.fixture
def write_recording(media: Path) -> WriteRecording:
    def write(source: str = "clip.mkv", sha256: str | None = None, **overrides: object) -> Path:
        declaration = recording_declaration(source) | overrides
        if sha256 is not None:
            declaration["source"] = {"path": source, "sha256": sha256}
        path = media / "recording.yaml"
        path.write_text(yaml.safe_dump(declaration), encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_corpus(media: Path) -> WriteCorpus:
    def write(sequences: list[dict[str, object]], **overrides: object) -> Path:
        declaration = {"schema_version": 1, "corpus_id": "pilot-v1", "sequences": sequences}
        path = media / "corpus.yaml"
        path.write_text(yaml.safe_dump(declaration | overrides), encoding="utf-8")
        return path

    return write


@pytest.fixture
def imported(clip: Path, write_recording: WriteRecording, data_root: Path) -> ImportResult:
    result = import_source(write_recording(), data_root)
    assert result.source_sha256 == sha256_file(clip)
    return result
