"""Shared corpus fixtures: a clean data root and written operator declarations."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from ss_track.corpus import import_source
from ss_track.corpus.importer import ImportResult
from ss_track.corpus.sealed import seal, sha256_file
from tests.corpus._media import WIDTH, write_clip

type Recording = dict[str, object]
type WriteRecording = Callable[..., Path]
type WriteCorpus = Callable[..., Path]


def recording_declaration(source: str = "clip.mkv") -> Recording:
    """Return a complete recording declaration that a test may then damage."""
    return {
        "schema_version": 2,
        "source": {"path": source},
        "rights": {
            "holder": "Project Contributors",
            "basis": "owned",
            "retention": "project duration",
            "retain_until": None,
            "derived_frames": True,
            "sharing": "restricted",
        },
        "sensitivity": {"level": "low"},
    }


def stream_of(result: ImportResult, **fields: object) -> dict[str, object]:
    """Return one corpus stream entry naming an imported source."""
    return {"stream_id": "one", "source_sha256": result.source_sha256} | fields


def encounter_of(encounter_id: str, *streams: dict[str, object]) -> dict[str, object]:
    """Return one encounter holding the given streams."""
    return {"encounter_id": encounter_id, "streams": list(streams)}


def group_of(
    group_id: str, split: str, *encounters: dict[str, object], **fields: object
) -> dict[str, object]:
    """Return one encounter group in one split."""
    return {"group_id": group_id, "split": split, "encounters": list(encounters)} | fields


def case_of(
    case_id: str, transform: str, seed: int, parameters: dict[str, object], **fields: object
) -> dict[str, object]:
    """Return one generated-case recipe for a stream's `generated_cases` list."""
    recipe = {"case_id": case_id, "transform": transform, "seed": seed, "parameters": parameters}
    return recipe | fields


def corpus_declaration(groups: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    """Return a complete corpus declaration whose scenario asks nothing of its sources."""
    return {
        "schema_version": 3,
        "corpus_id": "pilot-v1",
        "scenario_rights": {"sharing": "restricted", "max_sensitivity": "high"},
        "groups": groups,
    } | overrides


def write_groups(media: Path, groups: list[dict[str, object]], **overrides: object) -> Path:
    """Write a corpus declaration and return its path."""
    path = media / "corpus.yaml"
    declaration = corpus_declaration(groups, **overrides)
    path.write_text(yaml.safe_dump(declaration), encoding="utf-8")
    return path


def place_of(corpus_id: str, group_id: str, split: str) -> dict[str, str]:
    """Return one side of a move, as a lineage refusal states it."""
    return {"corpus_id": corpus_id, "group_id": group_id, "split": split}


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
    def write(streams: list[dict[str, object]], **overrides: object) -> Path:
        """Declare each stream as its own encounter in one development group."""
        encounters = [encounter_of(f"enc-{item['stream_id']}", item) for item in streams]
        groups = [group_of("group-one", "development", *encounters)]
        return write_groups(media, groups, **overrides)

    return write


@pytest.fixture
def write_grouped_corpus(media: Path) -> WriteCorpus:
    def write(groups: list[dict[str, object]], **overrides: object) -> Path:
        return write_groups(media, groups, **overrides)

    return write


@pytest.fixture
def imported(clip: Path, write_recording: WriteRecording, data_root: Path) -> ImportResult:
    result = import_source(write_recording(), data_root)
    assert result.source_sha256 == sha256_file(clip)
    return result


def import_clip(
    media: Path,
    write_recording: WriteRecording,
    data_root: Path,
    extra_width: int,
    **rights: object,
) -> ImportResult:
    """Import a clip that differs from every other by its width, so its hash differs too."""
    name = f"clip-{extra_width}.mkv"
    write_clip(media / name, width=WIDTH + extra_width)
    return import_source(write_recording(name, **rights), data_root)


@pytest.fixture
def first(media: Path, write_recording: WriteRecording, data_root: Path) -> ImportResult:
    return import_clip(media, write_recording, data_root, 2)


@pytest.fixture
def second(media: Path, write_recording: WriteRecording, data_root: Path) -> ImportResult:
    return import_clip(media, write_recording, data_root, 4)


@pytest.fixture
def third(media: Path, write_recording: WriteRecording, data_root: Path) -> ImportResult:
    return import_clip(media, write_recording, data_root, 6)
